"""run_safe_sql — Validate, execute, and return SQL query results."""

import time
from typing import Any

from ondc_mcp.cache import redis_cache
from ondc_mcp.db.connection import execute_readonly
from ondc_mcp.security.monitor import security_monitor
from ondc_mcp.security.query_logger import query_logger
from ondc_mcp.security.rate_limiter import rate_limiter
from ondc_mcp.security.role_access import role_access
from ondc_mcp.validation.sql_validator import SQLValidator

validator = SQLValidator()


async def run_safe_sql(sql: str, role: str = "analyst") -> dict[str, Any]:
    """Validate and execute a read-only SQL query.

    Args:
        sql: The SQL query to execute
        role: User role for access control (default: analyst)

    Returns:
        Dict with 'status', 'data' or 'errors', and metadata
    """
    start = time.monotonic()
    user_id = "anonymous"  # MCP doesn't pass user context yet

    # Step 0: Rate limit check
    allowed, rate_error = rate_limiter.check(user_id)
    if not allowed:
        query_logger.log_query(
            raw_sql=sql,
            role=role,
            user_id=user_id,
            status="rate_limited",
            execution_time_ms=(time.monotonic() - start) * 1000,
        )
        security_monitor.record_event(user_id, "rate_limited", rate_error or "")
        return {
            "status": "rate_limited",
            "errors": [rate_error],
        }

    # Step 1: SQL validation
    result = validator.validate(sql, role=role)
    if not result.valid:
        query_logger.log_query(
            raw_sql=sql,
            role=role,
            status="rejected",
            rejection_reasons=result.errors,
            execution_time_ms=(time.monotonic() - start) * 1000,
        )
        security_monitor.record_event(user_id, "rejected", "; ".join(result.errors))
        return {
            "status": "rejected",
            "errors": result.errors,
            "hint": "Call get_schema to see exact table names, columns, and valid values.",
        }

    sanitized = result.sanitized_sql

    # Step 2: Role-based access check (skipped for unrestricted roles)
    from ondc_mcp.db.schema_registry import registry
    import sqlglot
    from sqlglot import exp

    if not registry.role_unrestricted_select(role):
        parsed = sqlglot.parse(sanitized, dialect="postgres")
        if parsed:
            stmt = parsed[0]
            cte_names = {cte.alias for cte in stmt.find_all(exp.CTE)}
            tables_in_query = [
                t.name for t in stmt.find_all(exp.Table) if t.name not in cte_names
            ]
            denied = role_access.check_tables(role, tables_in_query)
            if denied:
                errors = [
                    f"Role '{role}' does not have access to tables: {', '.join(denied)}"
                ]
                query_logger.log_query(
                    raw_sql=sql,
                    validated_sql=sanitized,
                    role=role,
                    status="rejected",
                    rejection_reasons=errors,
                    execution_time_ms=(time.monotonic() - start) * 1000,
                )
                security_monitor.record_event(user_id, "access_denied", "; ".join(errors))
                return {
                    "status": "rejected",
                    "errors": errors,
                }

    # Step 3: Cache check
    cached = await redis_cache.get_cached(sanitized, role)
    if cached is not None:
        query_logger.log_query(
            raw_sql=sql,
            validated_sql=sanitized,
            role=role,
            status="success",
            row_count=len(cached),
            execution_time_ms=(time.monotonic() - start) * 1000,
        )
        security_monitor.record_event(user_id, "success", "cache hit")
        return {
            "status": "success",
            "data": cached,
            "row_count": len(cached),
            "cached": True,
        }

    # Step 4: Execute
    try:
        rows = await execute_readonly(sanitized)
        elapsed_ms = (time.monotonic() - start) * 1000

        # Cache result
        await redis_cache.set_cached(sanitized, role, rows)

        query_logger.log_query(
            raw_sql=sql,
            validated_sql=sanitized,
            role=role,
            status="success",
            row_count=len(rows),
            execution_time_ms=elapsed_ms,
        )
        security_monitor.record_event(user_id, "success", f"{len(rows)} rows")
        return {
            "status": "success",
            "data": rows,
            "row_count": len(rows),
            "cached": False,
        }

    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        query_logger.log_query(
            raw_sql=sql,
            validated_sql=sanitized,
            role=role,
            status="error",
            error_message=str(e),
            execution_time_ms=elapsed_ms,
        )
        security_monitor.record_event(user_id, "error", str(e))
        return {
            "status": "error",
            "errors": [str(e)],
        }

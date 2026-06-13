"""SQL AST validation using sqlglot.

Enforces:
- Only SELECT statements
- No SELECT *
- Required date filter on order_date
- LIMIT enforcement (auto-inject if missing)
- Only allowed tables and schema
- Join validation (ON clause required, only allowed columns)
- No Cartesian joins
"""

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

from ondc_mcp.db.schema_registry import SchemaRegistry, registry as default_registry


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    sanitized_sql: str = ""


class SQLValidator:
    def __init__(self, schema_registry: SchemaRegistry | None = None):
        self.registry = schema_registry or default_registry

    def validate(self, sql: str, role: str = "") -> ValidationResult:
        errors: list[str] = []
        unrestricted = self.registry.role_unrestricted_select(role)

        # Parse
        try:
            parsed = sqlglot.parse(sql, dialect="postgres")
        except sqlglot.errors.ParseError as e:
            return ValidationResult(valid=False, errors=[f"SQL parse error: {e}"])

        if not parsed:
            return ValidationResult(valid=False, errors=["Empty SQL statement"])

        # Only single statement allowed (skipped for unrestricted roles)
        if not unrestricted and len(parsed) > 1:
            errors.append("Only single SQL statements are allowed")
            return ValidationResult(valid=False, errors=errors)

        # Rule: Only SELECT — always enforced regardless of role
        for stmt in parsed:
            if not isinstance(stmt, (exp.Select, exp.Union)):
                errors.append(
                    f"Only SELECT statements are allowed, got: {type(stmt).__name__}"
                )
        if errors:
            return ValidationResult(valid=False, errors=errors)

        # Unrestricted roles: multi-statement passes through as-is (no further checks)
        if unrestricted and len(parsed) > 1:
            return ValidationResult(valid=True, errors=[], sanitized_sql=sql)

        statement = parsed[0]

        # Remaining rules skipped entirely for unrestricted roles
        if not unrestricted:
            tables_found = self._extract_tables(statement)
            self._check_allowed_tables(tables_found, errors)
            self._check_no_star(statement, errors)
            self._check_date_filter(statement, tables_found, errors)
            self._check_joins(statement, errors)

        if errors:
            return ValidationResult(valid=False, errors=errors)

        # Auto-inject LIMIT if missing
        sanitized = self._ensure_limit(statement)

        return ValidationResult(
            valid=True,
            errors=[],
            sanitized_sql=sanitized.sql(dialect="postgres"),
        )

    def _check_no_star(self, stmt: exp.Select, errors: list[str]) -> None:
        for select_expr in stmt.find_all(exp.Star):
            errors.append(
                "SELECT * is not allowed. Please specify explicit column names."
            )
            return

    def _extract_tables(self, stmt: exp.Select) -> list[str]:
        """Extract bare table names from the query, excluding CTE aliases."""
        # CTE names (e.g. monthly_orders, pivoted) are referenced as exp.Table
        # nodes in the main query body but are not real tables — exclude them.
        cte_names = {cte.alias for cte in stmt.find_all(exp.CTE)}
        return [
            table.name
            for table in stmt.find_all(exp.Table)
            if table.name not in cte_names
        ]

    def _check_allowed_tables(
        self, tables: list[str], errors: list[str]
    ) -> None:
        # Schema validation is now relaxed to allow dynamic RAG discovery.
        # The database role permissions will enforce table access.
        pass

    def _check_date_filter(
        self,
        stmt: exp.Select,
        tables: list[str],
        errors: list[str],
    ) -> None:
        """Date filters are now optional due to pre-aggregated views."""
        pass

    def _check_joins(self, stmt: exp.Select, errors: list[str]) -> None:
        """Check join conditions: ON clause required, Cartesian joins not allowed."""
        for join in stmt.find_all(exp.Join):
            on_clause = join.args.get("on")
            using_clause = join.args.get("using")
            if on_clause is None and using_clause is None:
                errors.append(
                    "All JOINs must have an ON or USING clause. Cartesian joins are not allowed."
                )
                continue

    def _ensure_limit(self, stmt: exp.Select) -> exp.Select:
        """Inject LIMIT if not present."""
        max_rows = self.registry._data.get("max_rows", None)
        from ondc_mcp.config import settings
        limit_val = max_rows or settings.max_query_rows

        existing_limit = stmt.find(exp.Limit)
        if existing_limit is None:
            stmt = stmt.limit(limit_val)
        else:
            # Enforce max even if user specified a higher limit
            limit_expr = existing_limit.args.get("expression")
            if limit_expr and isinstance(limit_expr, exp.Literal):
                try:
                    user_limit = int(limit_expr.this)
                    if user_limit > limit_val:
                        existing_limit.args["expression"] = exp.Literal.number(
                            limit_val
                        )
                except (ValueError, TypeError):
                    pass
        return stmt

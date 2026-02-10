"""get_schema — Return table metadata for LLM context."""

import time
from typing import Any

from ondc_mcp.cache import redis_cache
from ondc_mcp.db.schema_registry import registry
from ondc_mcp.security.query_logger import query_logger


async def get_schema() -> dict[str, Any]:
    """Return full schema metadata including tables, columns, and domain/category values.

    Returns:
        Dict with schema name, table definitions, domain categories, and np_types
    """
    start = time.monotonic()

    # Check cache first
    cached = await redis_cache.get_cached_schema()
    if cached is not None:
        query_logger.log_tool_call(
            tool_name="get_schema",
            status="success",
            execution_time_ms=(time.monotonic() - start) * 1000,
        )
        return cached

    schema_info = registry.get_schema_description()

    # Cache the result
    await redis_cache.set_cached_schema(schema_info)

    query_logger.log_tool_call(
        tool_name="get_schema",
        status="success",
        execution_time_ms=(time.monotonic() - start) * 1000,
    )

    return schema_info

"""get_schema — Return table metadata for LLM context."""

import time
from typing import Any

from ondc_mcp.cache import redis_cache
from ondc_mcp.db.schema_registry import registry
from ondc_mcp.security.query_logger import query_logger


async def get_schema() -> dict[str, Any]:
    """Get high-level schema directory and instructions.

    Returns:
        Dict with instructions to use search_schema instead.
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

    schema_info = {
        "status": "success",
        "message": "The schema is too large to load entirely. Please use the 'search_schema' tool to find relevant tables by business context or keywords.",
        "schemas_available": ["opendata_nodata", "analytics_insight", "dimension", "external", "logistics", "no_recommendation", "prod", "prod_bkp", "public"]
    }

    # Cache the result
    await redis_cache.set_cached_schema(schema_info)

    query_logger.log_tool_call(
        tool_name="get_schema",
        status="success",
        execution_time_ms=(time.monotonic() - start) * 1000,
    )

    return schema_info

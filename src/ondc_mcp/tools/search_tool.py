"""search_schema — RAG-based database schema search."""

import time
from typing import Any

from ondc_mcp.security.query_logger import query_logger
from ondc_mcp.rag.search import search_schema as _do_search

async def search_schema(query: str, top_k: int = 5) -> dict[str, Any]:
    """Search the database schema metadata for relevant tables and views.

    Args:
        query: Natural language search query describing the data needed.
        top_k: Number of schema matches to return.

    Returns:
        Dict with search results including Table Name, DDL, and Columns.
    """
    start = time.monotonic()
    
    try:
        results = _do_search(query, top_k)
        
        query_logger.log_tool_call(
            tool_name="search_schema",
            status="success",
            execution_time_ms=(time.monotonic() - start) * 1000,
        )
        return {
            "status": "success",
            "results": results,
            "query": query
        }
    except Exception as e:
        query_logger.log_tool_call(
            tool_name="search_schema",
            status="error",
            execution_time_ms=(time.monotonic() - start) * 1000,
        )
        return {
            "status": "error",
            "message": str(e),
            "query": query
        }

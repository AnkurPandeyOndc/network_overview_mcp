"""FastMCP server entry point — registers tools and manages lifecycle."""

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from ondc_mcp.config import settings
from ondc_mcp.db.connection import close_pool, get_pool
from ondc_mcp.cache.redis_cache import close_redis, get_redis
from ondc_mcp.db.schema_registry import registry

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """Initialize DB pool and Redis on startup, close on shutdown."""
    logger.info("Starting ONDC Analytics MCP server...")

    # Load schema registry
    registry.load()
    logger.info(
        f"Schema loaded: {len(registry.get_table_names())} tables in '{registry.schema_name}'"
    )

    # Init DB pool
    pool = await get_pool()
    logger.info("Database connection pool initialized")

    # Init Redis (graceful if unavailable)
    redis_client = await get_redis()
    if redis_client:
        logger.info("Redis cache connected")
    else:
        logger.warning("Redis unavailable — caching disabled")

    yield

    # Cleanup
    await close_pool()
    await close_redis()
    logger.info("Server shut down cleanly")


mcp = FastMCP(
    "ONDC Analytics",
    lifespan=app_lifespan,
    host=settings.host,
    port=settings.port,
)


# --- Tool: run_safe_sql ---
@mcp.tool()
async def run_safe_sql(sql: str, role: str = "analyst") -> str:
    """Execute a validated, read-only SQL query against ONDC analytics data.

    IMPORTANT — you MUST call get_schema first to discover exact table names,
    column names, and valid domain/category values before writing any SQL.

    Available tables (schema: opendata_nodata):
      - opendata_nodata.model_for_all_domain: order counts by domain, category,
        buyer_np, seller_np, np_type.  Columns: order_date, domain, category,
        buyer_np, seller_np, np_type, orders.
      - opendata_nodata.model_for_all_domain_pincode: order counts by domain,
        delivery_city, seller_city.  Columns: order_date, domain, delivery_city,
        seller_city, orders.

    There are NO other tables — do NOT invent table names.

    Validation rules enforced:
      - SELECT only (no INSERT/UPDATE/DELETE/DDL)
      - No SELECT *  — list columns explicitly
      - WHERE must include an order_date filter
      - LIMIT is auto-added (max 1000)

    Args:
        sql: SQL SELECT query using only the tables listed above
        role: User role for access control (default: analyst)

    Returns:
        JSON string with query results or validation errors
    """
    from ondc_mcp.tools.sql_tool import run_safe_sql as _run
    result = await _run(sql, role)
    return json.dumps(result, default=str, indent=2)


# --- Tool: get_schema ---
@mcp.tool()
async def get_schema() -> str:
    """Get the database schema metadata for ONDC analytics tables.

    ALWAYS call this tool before writing any SQL query. It returns the exact
    table names, column names and types, valid domain/category values, and
    network participant types. Using table or column names not present in this
    output will cause query validation to fail.

    Returns:
        JSON string with full schema information
    """
    from ondc_mcp.tools.schema_tool import get_schema as _get
    result = await _get()
    return json.dumps(result, default=str, indent=2)


# --- Tool: get_data_freshness ---
@mcp.tool()
async def get_data_freshness() -> str:
    """Check the latest available data date for each analytics table.

    Queries MAX(order_date) from each table to show data freshness.

    Returns:
        JSON string with latest date per table
    """
    from ondc_mcp.tools.freshness_tool import get_data_freshness as _get
    result = await _get()
    return json.dumps(result, default=str, indent=2)


# --- Tool: search_docs ---
@mcp.tool()
async def search_docs(query: str) -> str:
    """Search indexed ONDC business documents for relevant context.

    Currently a skeleton — no documents are indexed yet.

    Args:
        query: Natural language search query

    Returns:
        JSON string with search results
    """
    from ondc_mcp.tools.rag_tool import search_docs as _search
    result = await _search(query)
    return json.dumps(result, default=str, indent=2)


def main():
    """Run the MCP server with configured transport."""
    # transport = settings.transport.lower()
    # if transport == "http":
    #     mcp.run(transport="streamable-http")
    # else:
    #     mcp.run(transport="stdio")
    mcp.run(transport="stdio")



if __name__ == "__main__":
    main()

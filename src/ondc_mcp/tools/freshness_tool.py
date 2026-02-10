"""get_data_freshness — Report the latest data date in each table."""

import time
from typing import Any

from ondc_mcp.db.connection import execute_readonly
from ondc_mcp.db.schema_registry import registry
from ondc_mcp.security.query_logger import query_logger


async def get_data_freshness() -> dict[str, Any]:
    """Query MAX(order_date) from each registered table.

    Returns:
        Dict mapping table names to their latest order_date
    """
    start = time.monotonic()
    freshness: dict[str, Any] = {}

    for table_name in registry.get_table_names():
        date_col = registry.get_date_column(table_name)
        if date_col is None:
            continue

        full_name = registry.get_full_table_name(table_name)
        sql = f"SELECT MAX({date_col}) AS latest_date FROM {full_name}"

        try:
            rows = await execute_readonly(sql)
            if rows and rows[0].get("latest_date") is not None:
                freshness[table_name] = str(rows[0]["latest_date"])
            else:
                freshness[table_name] = None
        except Exception as e:
            freshness[table_name] = f"error: {e}"

    query_logger.log_tool_call(
        tool_name="get_data_freshness",
        status="success",
        execution_time_ms=(time.monotonic() - start) * 1000,
    )

    return {
        "status": "success",
        "freshness": freshness,
    }

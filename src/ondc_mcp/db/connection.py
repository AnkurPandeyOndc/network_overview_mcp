"""asyncpg connection pool management and read-only query execution."""

import asyncpg

from ondc_mcp.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def execute_readonly(
    sql: str,
    timeout: float | None = None,
) -> list[dict]:
    """Execute a read-only SQL query and return rows as dicts."""
    pool = await get_pool()
    effective_timeout = timeout or settings.query_timeout_seconds

    async with pool.acquire() as conn:
        # Set read-only transaction and statement timeout
        await conn.execute("SET TRANSACTION READ ONLY")
        await conn.execute(
            f"SET statement_timeout = '{int(effective_timeout * 1000)}'"
        )
        rows = await conn.fetch(sql)
        return [dict(row) for row in rows]

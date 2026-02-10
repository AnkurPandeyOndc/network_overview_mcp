"""Redis-based query result caching with graceful degradation."""

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as redis

from ondc_mcp.config import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


async def get_redis() -> redis.Redis | None:
    """Get or create Redis client. Returns None if disabled or connection fails."""
    global _client
    if not settings.redis_enabled:
        return None
    if _client is None:
        try:
            _client = redis.from_url(settings.redis_url, decode_responses=True)
            await _client.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable, caching disabled: {e}")
            _client = None
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def _cache_key(sql: str, role: str) -> str:
    """Generate a cache key from SQL and role."""
    content = f"{role}:{sql}"
    h = hashlib.sha256(content.encode()).hexdigest()[:16]
    return f"ondc_mcp:query:{h}"


async def get_cached(sql: str, role: str) -> list[dict] | None:
    """Retrieve cached query result. Returns None on miss or error."""
    client = await get_redis()
    if client is None:
        return None
    try:
        key = _cache_key(sql, role)
        data = await client.get(key)
        if data is not None:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
    return None


async def set_cached(
    sql: str, role: str, result: list[dict], ttl: int | None = None
) -> None:
    """Cache query result. Silently fails on error."""
    client = await get_redis()
    if client is None:
        return
    try:
        key = _cache_key(sql, role)
        effective_ttl = ttl or settings.cache_query_ttl
        await client.set(key, json.dumps(result, default=str), ex=effective_ttl)
    except Exception as e:
        logger.warning(f"Cache write error: {e}")


async def get_cached_schema() -> dict[str, Any] | None:
    """Retrieve cached schema info."""
    client = await get_redis()
    if client is None:
        return None
    try:
        data = await client.get("ondc_mcp:schema")
        if data is not None:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
    return None


async def set_cached_schema(schema: dict[str, Any]) -> None:
    """Cache schema info."""
    client = await get_redis()
    if client is None:
        return
    try:
        await client.set(
            "ondc_mcp:schema",
            json.dumps(schema, default=str),
            ex=settings.cache_schema_ttl,
        )
    except Exception as e:
        logger.warning(f"Cache write error: {e}")

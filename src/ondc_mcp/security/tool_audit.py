"""Universal tool audit decorator for MCP tool logging."""

import functools
import time
from typing import Any, Callable

from ondc_mcp.security.query_logger import query_logger


def audit_tool(tool_name: str) -> Callable:
    """Decorator that wraps any async MCP tool with timing and audit logging.

    Usage:
        @mcp.tool()
        @audit_tool("search_docs")
        async def search_docs(query: str) -> str:
            ...

    Every call — success or error — is written to the audit JSONL log.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            from ondc_mcp.security.query_logger import query_logger

            start = time.perf_counter()
            status = "success"
            error_msg: str | None = None
            result: Any = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as exc:
                status = "error"
                error_msg = str(exc)
                raise
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                # Truncate large values to keep the log readable
                inputs = {k: str(v)[:500] for k, v in kwargs.items()}
                query_logger.log_tool_call(  # type: ignore[attr-defined]
                    tool_name=tool_name,
                    args=inputs,
                    status=status,
                    execution_time_ms=round(elapsed_ms, 2),
                    error=error_msg,
                )

        return wrapper

    return decorator

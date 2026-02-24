"""Tests for the @audit_tool decorator."""

import pytest
from unittest.mock import patch

from ondc_mcp.security.tool_audit import audit_tool
from ondc_mcp.security.query_logger import query_logger as real_query_logger


class TestAuditToolDecorator:
    @pytest.mark.asyncio
    async def test_success_is_logged(self):
        log_entries = []

        with patch.object(
            real_query_logger,
            "log_tool_call",
            side_effect=lambda **kw: log_entries.append(kw),
        ):

            @audit_tool("my_tool")
            async def my_tool(query: str = "hello") -> str:
                return "result"

            result = await my_tool(query="test input")

        assert result == "result"
        assert len(log_entries) == 1
        entry = log_entries[0]
        assert entry["tool_name"] == "my_tool"
        assert entry["status"] == "success"
        assert entry["error"] is None

    @pytest.mark.asyncio
    async def test_error_is_logged_and_reraised(self):
        log_entries = []

        with patch.object(
            real_query_logger,
            "log_tool_call",
            side_effect=lambda **kw: log_entries.append(kw),
        ):

            @audit_tool("failing_tool")
            async def failing_tool() -> str:
                raise ValueError("something broke")

            with pytest.raises(ValueError, match="something broke"):
                await failing_tool()

        assert len(log_entries) == 1
        entry = log_entries[0]
        assert entry["tool_name"] == "failing_tool"
        assert entry["status"] == "error"
        assert "something broke" in entry["error"]

    @pytest.mark.asyncio
    async def test_execution_time_recorded(self):
        log_entries = []

        with patch.object(
            real_query_logger,
            "log_tool_call",
            side_effect=lambda **kw: log_entries.append(kw),
        ):

            @audit_tool("timed_tool")
            async def timed_tool() -> None:
                pass

            await timed_tool()

        assert log_entries[0]["execution_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_return_value_preserved(self):
        with patch.object(real_query_logger, "log_tool_call"):

            @audit_tool("return_tool")
            async def return_tool() -> dict:
                return {"status": "ok", "data": [1, 2, 3]}

            result = await return_tool()

        assert result == {"status": "ok", "data": [1, 2, 3]}

    def test_function_name_preserved(self):
        @audit_tool("named_tool")
        async def my_named_function():
            pass

        assert my_named_function.__name__ == "my_named_function"

    @pytest.mark.asyncio
    async def test_kwargs_captured_in_inputs(self):
        log_entries = []

        with patch.object(
            real_query_logger,
            "log_tool_call",
            side_effect=lambda **kw: log_entries.append(kw),
        ):

            @audit_tool("kwargs_tool")
            async def kwargs_tool(session_id: str = "", limit: int = 20) -> None:
                pass

            await kwargs_tool(session_id="abc123", limit=10)

        inputs = log_entries[0]["args"]
        assert "session_id" in inputs
        assert "limit" in inputs

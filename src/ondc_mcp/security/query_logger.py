"""Structured JSON audit logging for all query attempts."""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class QueryLogger:
    """Logs every query attempt to a JSONL file."""

    def __init__(self, log_path: str | None = None):
        from ondc_mcp.config import settings

        self._log_path = log_path or settings.audit_log_path
        self._logger = logging.getLogger("ondc_mcp.audit")

        # Ensure log directory exists; fall back to stderr on read-only fs
        try:
            Path(self._log_path).parent.mkdir(parents=True, exist_ok=True)
            if not self._logger.handlers:
                handler = logging.FileHandler(self._log_path)
                handler.setFormatter(logging.Formatter("%(message)s"))
                self._logger.addHandler(handler)
                self._logger.setLevel(logging.INFO)
        except OSError as e:
            logging.getLogger(__name__).warning(
                f"Audit file logging unavailable ({e}), logging to stderr only"
            )
            if not self._logger.handlers:
                self._logger.addHandler(logging.StreamHandler())
                self._logger.setLevel(logging.INFO)

    def log_query(
        self,
        *,
        user_id: str = "anonymous",
        role: str = "analyst",
        raw_sql: str,
        validated_sql: str = "",
        status: str,  # "success", "rejected", "error"
        rejection_reasons: list[str] | None = None,
        execution_time_ms: float | None = None,
        row_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "role": role,
            "raw_sql": raw_sql,
            "validated_sql": validated_sql,
            "status": status,
            "rejection_reasons": rejection_reasons or [],
            "execution_time_ms": execution_time_ms,
            "row_count": row_count,
            "error_message": error_message,
        }
        self._logger.info(json.dumps(entry, default=str))

    def log_tool_call(
        self,
        *,
        tool_name: str,
        user_id: str = "anonymous",
        args: dict[str, Any] | None = None,
        status: str = "success",
        execution_time_ms: float | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "tool_call",
            "tool_name": tool_name,
            "user_id": user_id,
            "args": args or {},
            "status": status,
            "execution_time_ms": execution_time_ms,
        }
        self._logger.info(json.dumps(entry, default=str))


# Module-level singleton
query_logger = QueryLogger()

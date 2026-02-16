"""Security monitor — detects anomalous query patterns and logs alerts."""

import json
import logging
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SecurityAlert:
    timestamp: str
    severity: str  # "low", "medium", "high"
    alert_type: str
    user_id: str
    details: str


class SecurityMonitor:
    """Tracks query events in-memory and flags anomalous patterns."""

    def __init__(
        self,
        alert_log_path: str | None = None,
        enabled: bool | None = None,
        burst_threshold: int = 30,
        rejection_window: int = 20,
        rejection_rate: float = 0.5,
        rbac_denial_threshold: int = 3,
        rbac_denial_window: float = 300.0,
    ):
        from ondc_mcp.config import settings

        self.enabled = enabled if enabled is not None else settings.security_monitor_enabled
        self._alert_log_path = alert_log_path or settings.security_alert_log_path

        self.burst_threshold = burst_threshold
        self.rejection_window = rejection_window
        self.rejection_rate = rejection_rate
        self.rbac_denial_threshold = rbac_denial_threshold
        self.rbac_denial_window = rbac_denial_window

        # Per-user event tracking
        self._events: dict[str, list[dict]] = defaultdict(list)
        self._alerts: list[SecurityAlert] = []

        # Set up alert logger
        self._logger = logging.getLogger("ondc_mcp.security_alerts")
        if not self._logger.handlers:
            try:
                Path(self._alert_log_path).parent.mkdir(parents=True, exist_ok=True)
                handler = logging.FileHandler(self._alert_log_path)
                handler.setFormatter(logging.Formatter("%(message)s"))
                self._logger.addHandler(handler)
            except OSError:
                self._logger.addHandler(logging.StreamHandler())
            self._logger.setLevel(logging.INFO)

    def record_event(
        self,
        user_id: str = "anonymous",
        event_type: str = "query",
        details: str = "",
    ) -> list[SecurityAlert]:
        """Record an event and return any alerts triggered."""
        if not self.enabled:
            return []

        now = time.monotonic()
        self._events[user_id].append(
            {"time": now, "event_type": event_type, "details": details}
        )

        return self._check_anomalies(user_id)

    def _check_anomalies(self, user_id: str) -> list[SecurityAlert]:
        alerts: list[SecurityAlert] = []
        events = self._events[user_id]
        now = time.monotonic()

        # 1. Burst detection — too many requests in 60 seconds
        recent = [e for e in events if now - e["time"] < 60.0]
        if len(recent) > self.burst_threshold:
            alerts.append(
                self._create_alert(
                    severity="high",
                    alert_type="burst_requests",
                    user_id=user_id,
                    details=f"{len(recent)} requests in the last 60 seconds",
                )
            )

        # 2. High rejection rate over the last N events
        last_n = events[-self.rejection_window :]
        if len(last_n) >= self.rejection_window:
            rejected = sum(
                1 for e in last_n if e["event_type"] in ("rejected", "rate_limited")
            )
            if rejected / len(last_n) > self.rejection_rate:
                alerts.append(
                    self._create_alert(
                        severity="medium",
                        alert_type="high_rejection_rate",
                        user_id=user_id,
                        details=f"{rejected}/{len(last_n)} recent queries rejected",
                    )
                )

        # 3. Repeated RBAC denials
        rbac_window_start = now - self.rbac_denial_window
        rbac_denials = [
            e
            for e in events
            if e["time"] > rbac_window_start and e["event_type"] == "access_denied"
        ]
        if len(rbac_denials) > self.rbac_denial_threshold:
            alerts.append(
                self._create_alert(
                    severity="high",
                    alert_type="repeated_access_denied",
                    user_id=user_id,
                    details=f"{len(rbac_denials)} access denials in {self.rbac_denial_window}s",
                )
            )

        # Prune old events (keep last 5 minutes)
        cutoff = now - 300.0
        self._events[user_id] = [e for e in events if e["time"] > cutoff]

        return alerts

    def _create_alert(
        self, *, severity: str, alert_type: str, user_id: str, details: str
    ) -> SecurityAlert:
        alert = SecurityAlert(
            timestamp=datetime.now(timezone.utc).isoformat(),
            severity=severity,
            alert_type=alert_type,
            user_id=user_id,
            details=details,
        )
        self._alerts.append(alert)
        self._logger.info(json.dumps(asdict(alert)))
        return alert

    @property
    def alerts(self) -> list[SecurityAlert]:
        return list(self._alerts)


# Module-level singleton
security_monitor = SecurityMonitor()

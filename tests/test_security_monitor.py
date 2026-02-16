"""Tests for the security monitor."""

import time

import pytest

from ondc_mcp.security.monitor import SecurityMonitor


@pytest.fixture
def monitor(tmp_path):
    """Create a security monitor with low thresholds for testing."""
    return SecurityMonitor(
        alert_log_path=str(tmp_path / "alerts.jsonl"),
        enabled=True,
        burst_threshold=5,
        rejection_window=5,
        rejection_rate=0.5,
        rbac_denial_threshold=2,
        rbac_denial_window=300.0,
    )


def test_normal_activity_no_alerts(monitor):
    for _ in range(3):
        alerts = monitor.record_event("user1", "success", "ok")
    assert alerts == []


def test_burst_detection_triggers_alert(monitor):
    # Send 6 events (threshold is 5) in quick succession
    alerts_collected = []
    for _ in range(6):
        alerts = monitor.record_event("user1", "success", "ok")
        alerts_collected.extend(alerts)

    assert len(alerts_collected) > 0
    burst_alerts = [a for a in alerts_collected if a.alert_type == "burst_requests"]
    assert len(burst_alerts) >= 1
    assert burst_alerts[0].severity == "high"


def test_high_rejection_rate_triggers_alert(monitor):
    # Send 5 events where > 50% are rejected (rejection_window=5)
    for _ in range(4):
        monitor.record_event("user1", "rejected", "bad query")

    alerts = monitor.record_event("user1", "success", "ok")
    rejection_alerts = [a for a in alerts if a.alert_type == "high_rejection_rate"]
    assert len(rejection_alerts) >= 1
    assert rejection_alerts[0].severity == "medium"


def test_repeated_access_denied_triggers_alert(monitor):
    # Send 3 access_denied events (threshold is 2)
    alerts_collected = []
    for _ in range(3):
        alerts = monitor.record_event("user1", "access_denied", "no access")
        alerts_collected.extend(alerts)

    access_alerts = [
        a for a in alerts_collected if a.alert_type == "repeated_access_denied"
    ]
    assert len(access_alerts) >= 1
    assert access_alerts[0].severity == "high"


def test_disabled_monitor_produces_no_alerts(tmp_path):
    monitor = SecurityMonitor(
        alert_log_path=str(tmp_path / "alerts.jsonl"),
        enabled=False,
        burst_threshold=2,
    )
    for _ in range(10):
        alerts = monitor.record_event("user1", "rejected", "bad")
        assert alerts == []


def test_different_users_tracked_separately(monitor):
    # Fill user1 past burst threshold
    for _ in range(6):
        monitor.record_event("user1", "success", "ok")

    # user2 should not trigger burst
    alerts = monitor.record_event("user2", "success", "ok")
    burst_alerts = [a for a in alerts if a.alert_type == "burst_requests"]
    assert len(burst_alerts) == 0


def test_alerts_written_to_log_file(tmp_path):
    import logging

    # Clear any existing handlers on the shared logger
    logger = logging.getLogger("ondc_mcp.security_alerts")
    logger.handlers.clear()

    log_file = tmp_path / "alerts.jsonl"
    mon = SecurityMonitor(
        alert_log_path=str(log_file),
        enabled=True,
        burst_threshold=5,
    )
    for _ in range(6):
        mon.record_event("user1", "success", "ok")

    # Flush handlers
    for h in logger.handlers:
        h.flush()

    assert log_file.exists()
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) >= 1
    assert "burst_requests" in lines[0]

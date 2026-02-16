"""Tests for the in-memory rate limiter."""

import time
from unittest.mock import patch

import pytest

from ondc_mcp.security.rate_limiter import RateLimiter


@pytest.fixture
def limiter():
    """Create a rate limiter with a low threshold for testing."""
    return RateLimiter(max_requests_per_minute=5)


def test_allows_requests_under_limit(limiter):
    for _ in range(5):
        allowed, error = limiter.check("user1")
        assert allowed is True
        assert error is None


def test_blocks_requests_over_limit(limiter):
    for _ in range(5):
        limiter.check("user1")

    allowed, error = limiter.check("user1")
    assert allowed is False
    assert "Rate limit exceeded" in error


def test_different_users_tracked_independently(limiter):
    # Fill up user1's quota
    for _ in range(5):
        limiter.check("user1")

    # user2 should still be allowed
    allowed, error = limiter.check("user2")
    assert allowed is True
    assert error is None


def test_window_cleanup_allows_after_expiry(limiter):
    # Fill up the quota
    for _ in range(5):
        limiter.check("user1")

    allowed, _ = limiter.check("user1")
    assert allowed is False

    # Simulate time passing: manually age the timestamps
    limiter._requests["user1"] = [time.monotonic() - 61.0] * 5

    # Now should be allowed again
    allowed, error = limiter.check("user1")
    assert allowed is True
    assert error is None


def test_default_user_id(limiter):
    allowed, error = limiter.check()
    assert allowed is True
    assert error is None

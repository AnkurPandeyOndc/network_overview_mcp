"""In-memory per-user rate limiter."""

import time
from collections import defaultdict


class RateLimiter:
    """Sliding-window rate limiter that caps requests per minute per user."""

    def __init__(self, max_requests_per_minute: int | None = None):
        from ondc_mcp.config import settings

        self.max_rpm = max_requests_per_minute or settings.rate_limit_per_minute
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(self, user_id: str = "anonymous") -> tuple[bool, str | None]:
        """Check whether a request from *user_id* is allowed.

        Returns:
            (allowed, error_message | None)
        """
        now = time.monotonic()
        window_start = now - 60.0

        # Prune timestamps older than the 60-second window
        timestamps = self._requests[user_id]
        self._requests[user_id] = [ts for ts in timestamps if ts > window_start]

        if len(self._requests[user_id]) >= self.max_rpm:
            return False, (
                f"Rate limit exceeded: {self.max_rpm} requests per minute. "
                "Please wait before retrying."
            )

        self._requests[user_id].append(now)
        return True, None


# Module-level singleton
rate_limiter = RateLimiter()

"""A thread-safe, continuously refilled token bucket."""

import math
import threading
import time


class TokenBucketRateLimiter:
    """Limit consumption to ``rate`` tokens/second with a bounded burst.

    Waiting callers compete for tokens without a FIFO guarantee. Requests
    larger than capacity can never succeed and return False immediately.
    """

    def __init__(self, rate: float, capacity: float):
        self.rate = self._positive_finite(rate, "rate")
        self.capacity = self._positive_finite(capacity, "capacity")
        self._tokens = self.capacity
        self._updated_at = time.monotonic()
        self._condition = threading.Condition()

    @staticmethod
    def _positive_finite(value: float, name: str) -> float:
        value = float(value)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and greater than zero")
        return value

    def _refill(self, now: float) -> None:
        """Update the balance while holding the condition lock."""
        self._tokens = min(
            self.capacity, self._tokens + (now - self._updated_at) * self.rate
        )
        self._updated_at = now

    def acquire(self, tokens: float = 1.0) -> bool:
        tokens = self._positive_finite(tokens, "tokens")
        with self._condition:
            self._refill(time.monotonic())
            if self._tokens < tokens:
                return False
            self._tokens -= tokens
            return True

    def available_tokens(self) -> float:
        with self._condition:
            self._refill(time.monotonic())
            return self._tokens

    def wait_and_acquire(
        self, tokens: float = 1.0, timeout: float | None = None
    ) -> bool:
        tokens = self._positive_finite(tokens, "tokens")
        if timeout is not None:
            timeout = float(timeout)
            if not math.isfinite(timeout) or timeout < 0:
                raise ValueError("timeout must be finite and nonnegative")
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            if tokens > self.capacity:
                return False
            waited = False
            while True:
                now = time.monotonic()
                self._refill(now)
                if waited and deadline is not None and now > deadline:
                    return False
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True
                delay = (tokens - self._tokens) / self.rate
                if deadline is not None:
                    remaining = deadline - now
                    if remaining <= 0:
                        return False
                    delay = min(delay, remaining)
                # Condition.wait releases the lock; recheck after every wakeup,
                # including spurious wakeups and resets.
                self._condition.wait(min(delay, threading.TIMEOUT_MAX))
                waited = True

    def reset(self) -> None:
        with self._condition:
            self._tokens = self.capacity
            self._updated_at = time.monotonic()
            self._condition.notify_all()

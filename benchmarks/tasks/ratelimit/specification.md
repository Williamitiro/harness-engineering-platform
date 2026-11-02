# Task Specification: Thread-Safe Token Bucket Rate Limiter

## Goal
Implement a thread-safe token bucket rate limiter in `ratelimit.py`.

## Requirements
1. Class `TokenBucketRateLimiter`:
   - `__init__(self, rate: float, capacity: float)`
     - `rate`: tokens added per second (must be > 0, otherwise raise `ValueError`).
     - `capacity`: maximum burst capacity (must be > 0, otherwise raise `ValueError`).
     - Initial state starts with full capacity.
   - `acquire(self, tokens: float = 1.0) -> bool`:
     - If at least `tokens` are available in the bucket, consume them and return `True`.
     - Otherwise, return `False` immediately without waiting.
     - `tokens` must be > 0 (otherwise raise `ValueError`).
   - `available_tokens(self) -> float`:
     - Returns the current number of tokens available (capped at `capacity`), taking into account time elapsed since the last update.
   - `wait_and_acquire(self, tokens: float = 1.0, timeout: float | None = None) -> bool`:
     - Blocks until enough tokens have accumulated, then consumes them and returns `True`.
     - If `timeout` (in seconds) is provided and expires before tokens are available, returns `False`.
     - Must be thread-safe when multiple threads are waiting.
   - `reset(self) -> None`:
     - Resets the bucket to full `capacity`.

2. Technology:
   - Pure Python 3.12+ stdlib (`time`, `threading`).
   - Thread safety: all methods must be safe under concurrent access from multiple threads.

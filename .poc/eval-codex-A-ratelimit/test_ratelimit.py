import threading
import time
import unittest
from unittest.mock import patch

from ratelimit import TokenBucketRateLimiter


class TokenBucketTests(unittest.TestCase):
    def test_refill_fractional_consumption_and_cap(self):
        with patch("ratelimit.time.monotonic") as clock:
            clock.return_value = 10.0
            bucket = TokenBucketRateLimiter(2, 3)
            self.assertEqual(bucket.available_tokens(), 3)
            self.assertTrue(bucket.acquire(2.5))
            self.assertFalse(bucket.acquire())
            clock.return_value = 10.5
            self.assertEqual(bucket.available_tokens(), 1.5)
            self.assertTrue(bucket.acquire(1.5))
            clock.return_value = 100
            self.assertEqual(bucket.available_tokens(), 3)

    def test_invalid_values(self):
        for value in (0, -1, float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    TokenBucketRateLimiter(value, 1)
                with self.assertRaises(ValueError):
                    TokenBucketRateLimiter(1, value)
                bucket = TokenBucketRateLimiter(1, 1)
                for method in (bucket.acquire, bucket.wait_and_acquire):
                    with self.assertRaises(ValueError):
                        method(value)

    def test_timeout_validation(self):
        bucket = TokenBucketRateLimiter(1, 1)
        for timeout in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                bucket.wait_and_acquire(timeout=timeout)

    def test_zero_timeout_and_impossible_request(self):
        bucket = TokenBucketRateLimiter(1, 1)
        self.assertTrue(bucket.wait_and_acquire(timeout=0))
        self.assertFalse(bucket.wait_and_acquire(timeout=0))
        self.assertFalse(bucket.wait_and_acquire(2))
        self.assertFalse(bucket.acquire(2))

    def test_wait_for_refill(self):
        bucket = TokenBucketRateLimiter(20, 1)
        self.assertTrue(bucket.acquire())
        start = time.monotonic()
        self.assertTrue(bucket.wait_and_acquire(timeout=1))
        self.assertGreaterEqual(time.monotonic() - start, 0.04)

    def test_timeout_does_not_consume(self):
        bucket = TokenBucketRateLimiter(1, 1)
        bucket.acquire()
        start = time.monotonic()
        self.assertFalse(bucket.wait_and_acquire(timeout=0.03))
        self.assertGreaterEqual(time.monotonic() - start, 0.025)
        self.assertGreater(bucket.available_tokens(), 0.025)

    def test_reset_restarts_refill_clock(self):
        with patch("ratelimit.time.monotonic") as clock:
            clock.return_value = 0
            bucket = TokenBucketRateLimiter(1, 2)
            bucket.acquire(2)
            clock.return_value = 10
            bucket.reset()
            self.assertEqual(bucket.available_tokens(), 2)
            bucket.acquire(2)
            clock.return_value = 10.5
            self.assertEqual(bucket.available_tokens(), 0.5)

    def test_delayed_wakeup_respects_deadline(self):
        with patch("ratelimit.time.monotonic") as clock:
            clock.return_value = 0
            bucket = TokenBucketRateLimiter(1, 1)
            bucket.acquire()

            def delayed_wakeup(delay):
                clock.return_value = 2

            with patch.object(bucket._condition, "wait", side_effect=delayed_wakeup):
                self.assertFalse(bucket.wait_and_acquire(timeout=0.5))
            self.assertEqual(bucket.available_tokens(), 1)

    def test_concurrent_acquisition_cannot_overspend(self):
        with patch("ratelimit.time.monotonic", return_value=0):
            bucket = TokenBucketRateLimiter(1, 7)
            barrier = threading.Barrier(25)
            results = []

            def consume():
                barrier.wait(timeout=5)
                results.append(bucket.acquire())

            threads = [threading.Thread(target=consume) for _ in range(25)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())
            self.assertEqual(sum(results), 7)
            self.assertEqual(bucket.available_tokens(), 0)

    def test_multiple_waiters_refill(self):
        bucket = TokenBucketRateLimiter(50, 1)
        bucket.acquire()
        results = []
        threads = [
            threading.Thread(
                target=lambda: results.append(bucket.wait_and_acquire(timeout=2))
            )
            for _ in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
        self.assertEqual(results, [True] * 8)

    def test_reset_wakes_all_waiters(self):
        bucket = TokenBucketRateLimiter(0.001, 4)
        bucket.acquire(4)
        results = []
        threads = [
            threading.Thread(
                target=lambda: results.append(bucket.wait_and_acquire(timeout=2))
            )
            for _ in range(4)
        ]
        for thread in threads:
            thread.start()
        time.sleep(0.03)
        bucket.reset()
        for thread in threads:
            thread.join(timeout=1)
            self.assertFalse(thread.is_alive())
        self.assertEqual(results, [True] * 4)


if __name__ == "__main__":
    unittest.main()

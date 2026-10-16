from collections import defaultdict, deque
from threading import RLock
from time import time


class RateLimitExceeded(Exception):
    pass


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def check(self, key: str, limit: int, window_seconds: int = 3600) -> None:
        now = time()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= limit:
                raise RateLimitExceeded
            events.append(now)


limiter = SlidingWindowLimiter()

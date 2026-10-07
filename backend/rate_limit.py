import math
import threading
import time


class FixedWindowRateLimiter:
    """Small process-local limiter with a fixed, caller-controlled key set."""

    def __init__(self, limit, window_seconds=60, clock=time.monotonic, max_keys=4):
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self.max_keys = max_keys
        self._lock = threading.Lock()
        self._windows = {}

    def allow(self, key):
        now = self.clock()
        with self._lock:
            if key not in self._windows and len(self._windows) >= self.max_keys:
                oldest = min(self._windows, key=lambda existing: self._windows[existing][0])
                del self._windows[oldest]
            started, count = self._windows.get(key, (now, 0))
            if now - started >= self.window_seconds:
                started, count = now, 0
            if count >= self.limit:
                return False, max(1, math.ceil(self.window_seconds - (now - started)))
            self._windows[key] = (started, count + 1)
            return True, 0

    @property
    def key_count(self):
        return len(self._windows)

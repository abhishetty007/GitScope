"""Process-local in-flight request coalescing.

This module shares only the result of an identical request while its leader is
already running. It is not a cache or a rate-limit store: the leader still
charges the PostgreSQL-backed limiter before every GitHub request, and a
failure is shared only with callers waiting on that same in-flight operation.
"""

from concurrent.futures import Future
import threading


_lock = threading.Lock()
_inflight: dict[object, Future] = {}


def coalesce(key, operation, *, timeout_seconds=None):
    """Run ``operation`` once for a key while concurrent callers wait for it."""
    with _lock:
        future = _inflight.get(key)
        leader = future is None
        if leader:
            future = Future()
            _inflight[key] = future

    if not leader:
        return future.result(timeout=timeout_seconds)

    try:
        result = operation()
    except BaseException as error:
        future.set_exception(error)
        raise
    else:
        future.set_result(result)
        return result
    finally:
        with _lock:
            if _inflight.get(key) is future:
                del _inflight[key]

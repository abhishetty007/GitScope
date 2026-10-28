"""Shared PostgreSQL fixed-window rate limiting for public GitHub reads."""

from __future__ import annotations

import os
import threading
import time

from psycopg_pool import ConnectionPool

from github_errors import GitHubUpstreamBudgetExceeded
from runtime_config import bounded_integer, github_upstream_budget_profile


GITHUB_UPSTREAM_BUDGET_BUCKET = "github_upstream_hourly"
GITHUB_UPSTREAM_MINUTE_BUCKET = "github_upstream_minute"
GITHUB_UPSTREAM_PER_MINUTE_LIMIT = 300


class RateLimitStoreUnavailable(RuntimeError):
    """The shared limiter store could not enforce a request limit."""


class PostgresRateLimitStore:
    """Atomically increment fixed-window counters in a shared PostgreSQL DB."""

    def __init__(self, connection_string, *, pool=None):
        self._pool = pool or ConnectionPool(
            conninfo=connection_string,
            min_size=0,
            max_size=2,
            timeout=2,
            # Neon pooler transaction mode supports unnamed parameters. Avoid
            # named server-side prepared statements across pooled sessions.
            kwargs={"connect_timeout": 2, "prepare_threshold": None},
            open=False,
        )
        self._pool_lock = threading.Lock()
        self._opened = False

    def _ensure_open(self):
        if self._opened:
            return
        with self._pool_lock:
            if not self._opened:
                self._pool.open(wait=True, timeout=2)
                self._opened = True

    def consume(self, bucket, *, global_limit, window_seconds, cost=1):
        """Consume weighted service-wide units atomically across instances."""
        try:
            if not isinstance(cost, int) or isinstance(cost, bool) or cost < 1:
                raise ValueError("cost must be a positive integer")
            self._ensure_open()
            with self._pool.connection(timeout=2) as connection:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        count, retry_after = _consume_sql(cursor, bucket, window_seconds, cost)
                    if self._should_prune():
                        with connection.cursor() as cursor:
                            cursor.execute(
                                """
                                WITH expired AS (
                                    SELECT ctid FROM gitscope_rate_limit_windows
                                    WHERE window_start < clock_timestamp() - interval '1 day'
                                    LIMIT 500
                                )
                                DELETE FROM gitscope_rate_limit_windows AS counters
                                USING expired WHERE counters.ctid = expired.ctid
                                """
                            )
            return count <= global_limit, retry_after
        except Exception as error:
            # Don't propagate DSNs, server messages, or database details to the
            # HTTP handler. The caller logs only this stable exception class.
            raise RateLimitStoreUnavailable from error

    def _should_prune(self):
        now = time.monotonic()
        if now - getattr(self, "_last_prune", 0) < 60:
            return False
        lock = getattr(self, "_prune_lock", None)
        if lock is None:
            lock = self._prune_lock = threading.Lock()
        with lock:
            if now - getattr(self, "_last_prune", 0) < 60:
                return False
            self._last_prune = now
            return True

    def close(self):
        self._pool.close()


def _consume_sql(cursor, bucket, window_seconds, cost=1):
    # Use the database clock to keep window boundaries consistent across hosts.
    cursor.execute(
        """
        WITH current_window AS (
            SELECT to_timestamp(
                floor(extract(epoch FROM clock_timestamp()) / %s) * %s
            ) AS starts_at
        ), consumed AS (
            INSERT INTO gitscope_rate_limit_windows
                (bucket, client_key, window_start, request_count)
            SELECT %s, 'global', current_window.starts_at, %s
            FROM current_window
            ON CONFLICT (bucket, client_key, window_start)
            DO UPDATE SET request_count =
                gitscope_rate_limit_windows.request_count + EXCLUDED.request_count
            RETURNING client_key, request_count, window_start
        )
        SELECT
            max(request_count),
            greatest(1, ceil(%s - extract(epoch FROM
                (clock_timestamp() - min(window_start)))))::integer
        FROM consumed
        """,
        (
            window_seconds,
            window_seconds,
            bucket,
            cost,
            window_seconds,
        ),
    )
    count, retry_after = cursor.fetchone()
    return int(count), int(retry_after)


class DistributedRateLimiter:
    """Policy wrapper; the store owns the cross-worker atomicity."""

    def __init__(self, store, *, window_seconds=60):
        self.store = store
        self.window_seconds = window_seconds

    def allow(self, bucket, *, global_limit, cost=1, window_seconds=None):
        return self.store.consume(
            bucket,
            global_limit=global_limit,
            window_seconds=self.window_seconds if window_seconds is None else window_seconds,
            cost=cost,
        )


_store = None
_store_lock = threading.Lock()


def get_default_rate_limiter(environ=None):
    global _store
    environ = os.environ if environ is None else environ
    connection_string = environ.get("GITSCOPE_RATE_LIMIT_DATABASE_URL", "").strip()
    if not connection_string:
        raise RateLimitStoreUnavailable
    with _store_lock:
        if _store is None:
            _store = PostgresRateLimitStore(connection_string)
    return DistributedRateLimiter(_store)


def github_upstream_budget_per_hour(environ=None):
    environ = os.environ if environ is None else environ
    default, maximum, _ = github_upstream_budget_profile(environ)
    return bounded_integer(
        environ,
        "GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR",
        default,
        1,
        maximum,
    )


def consume_github_upstream_call():
    """Account for one attempted GitHub HTTP request in the shared budget."""
    limiter = get_default_rate_limiter()
    for bucket, limit, window in (
        (GITHUB_UPSTREAM_MINUTE_BUCKET, GITHUB_UPSTREAM_PER_MINUTE_LIMIT, 60),
        (GITHUB_UPSTREAM_BUDGET_BUCKET, github_upstream_budget_per_hour(), 3600),
    ):
        allowed, retry_after = limiter.allow(
            bucket,
            global_limit=limit,
            window_seconds=window,
        )
        if not allowed:
            raise GitHubUpstreamBudgetExceeded(retry_after)

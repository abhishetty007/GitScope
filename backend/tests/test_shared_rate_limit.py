import os
import sys
import threading
import unittest
import multiprocessing
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rate_limit import DistributedRateLimiter, PostgresRateLimitStore


class TestRateLimitConfiguration(unittest.TestCase):
    def test_missing_database_url_fails_closed_before_pool_creation(self):
        from rate_limit import RateLimitStoreUnavailable, get_default_rate_limiter

        with patch.dict(os.environ, {}, clear=True):
            with patch("rate_limit.PostgresRateLimitStore") as store_factory:
                with self.assertRaises(RateLimitStoreUnavailable):
                    get_default_rate_limiter()

        store_factory.assert_not_called()


def _multiprocess_limiter_batch(database_url, bucket, barrier, result_queue):
    store = PostgresRateLimitStore(database_url)
    limiter = DistributedRateLimiter(store)
    try:
        barrier.wait(timeout=15)
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(
                    lambda _index: limiter.allow(bucket, global_limit=7, window_seconds=3600)[0], range(16)
                )
            )
        result_queue.put(sum(results))
    finally:
        store.close()


class TestForwardedHeadersDoNotAffectRateLimit(unittest.TestCase):
    def test_caller_supplied_forwarding_headers_do_not_select_a_counter(self):
        from app import app
        import app as app_module

        class RecordingLimiter:
            def __init__(self):
                self.calls = []

            def allow(self, bucket, *, global_limit, cost=1, window_seconds=None):
                self.calls.append((bucket, global_limit, cost, window_seconds))
                return True, 0

        original = app_module._rate_limiter
        limiter = RecordingLimiter()
        app_module._rate_limiter = limiter
        try:
            with patch("app.get_user", return_value={"login": "alice"}):
                client = app.test_client()
                self.assertEqual(client.get(
                    "/api/github/user/alice",
                    headers={"X-Forwarded-For": "203.0.113.9", "CF-Connecting-IP": "203.0.113.10"},
                ).status_code, 200)
                self.assertEqual(client.get(
                    "/api/github/user/alice",
                    headers={"X-Forwarded-For": "192.0.2.99", "CF-Connecting-IP": "192.0.2.100"},
                ).status_code, 200)
            self.assertEqual(
                limiter.calls,
                [
                    ("github_metadata", 60, 1, None),
                ] * 2,
            )
        finally:
            app_module._rate_limiter = original


class TestLimiterFailureIsClosed(unittest.TestCase):
    def test_database_outage_blocks_before_github_operation(self):
        from app import app
        import app as app_module

        class FailedLimiter:
            def allow(self, *args, **kwargs):
                raise RuntimeError("private database diagnostic")

        old_limiter = app_module._rate_limiter
        app_module._rate_limiter = FailedLimiter()
        try:
            with patch("app.get_user", side_effect=AssertionError("must not reach GitHub")):
                with self.assertLogs("app", level="ERROR") as logs:
                    response = app.test_client().get("/api/github/user/alice")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                response.get_json(),
                {"error": "Service temporarily unavailable. Try again shortly."},
            )
            self.assertEqual(response.headers["Retry-After"], "5")
            self.assertNotIn("private database diagnostic", response.get_data(as_text=True))
            self.assertNotIn("private database diagnostic", "\n".join(logs.output))
        finally:
            app_module._rate_limiter = old_limiter

    def test_upstream_budget_denial_is_safe_429_before_github(self):
        from github_errors import GitHubUpstreamBudgetExceeded
        from app import app

        with patch("app._public_rate_limit", return_value=None):
            with patch("app.get_user", side_effect=GitHubUpstreamBudgetExceeded(123)):
                response = app.test_client().get("/api/github/user/alice")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(
            response.get_json(),
            {"error": "GitHub request budget temporarily exhausted. Try again later."},
        )
        self.assertEqual(response.headers["Retry-After"], "123")

    def test_mid_request_limiter_database_failure_is_safe_503(self):
        from app import app
        from rate_limit import RateLimitStoreUnavailable

        with patch("app._public_rate_limit", return_value=None):
            with patch("app.get_user", side_effect=RateLimitStoreUnavailable()):
                response = app.test_client().get("/api/github/user/alice")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "5")
        self.assertNotIn("database", response.get_data(as_text=True).lower())

    def test_endpoint_limit_still_rejects_metadata_before_github(self):
        from app import app
        import app as app_module

        class EndpointFull:
            def __init__(self):
                self.calls = []

            def allow(self, bucket, *, global_limit, cost=1, window_seconds=None):
                self.calls.append(bucket)
                if bucket == "github_metadata":
                    return False, 9
                return True, 0

        old_limiter = app_module._rate_limiter
        limiter = EndpointFull()
        app_module._rate_limiter = limiter
        try:
            with patch("app.get_user", side_effect=AssertionError("must not reach GitHub")):
                response = app.test_client().get("/api/github/user/alice")
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers["Retry-After"], "9")
            self.assertEqual(
                response.get_json(),
                {"error": "Too many GitHub requests. Try again later."},
            )
            self.assertEqual(limiter.calls, ["github_metadata"])
        finally:
            app_module._rate_limiter = old_limiter


class TestRateLimitRouteCoverage(unittest.TestCase):
    def test_repository_analytics_has_no_separate_global_admission_quota(self):
        from app import app
        import cache as app_cache

        cached = {"repository": {"full_name": "alice/repo"}, "health": {"score": 81}}
        app_cache.clear_analysis("alice", "repo")
        app_cache.set_analysis("alice", "repo", cached)
        with patch("app._public_rate_limit", side_effect=AssertionError("analytics uses upstream call budgets")), \
             patch("app.get_repository", return_value={"private": False}):
            response = app.test_client().get("/api/github/repository/alice/repo/analytics")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), cached)

    def test_repository_analytics_preserves_actual_github_rate_limit_classification(self):
        from github_errors import GitHubRateLimitExceeded
        from app import app

        with patch("app._public_rate_limit", side_effect=AssertionError("no separate analytics quota")):
            with patch("app.get_repository", side_effect=GitHubRateLimitExceeded(37)):
                response = app.test_client().get(
                    "/api/github/repository/alice/repo/analytics"
                )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "37")
        self.assertEqual(
            response.get_json(),
            {"error": "GitHub rate limit exceeded. Try again later."},
        )

    def test_all_github_backed_routes_consume_the_endpoint_policy(self):
        from app import app

        calls = []
        public_repo = {
            "id": 123,
            "private": False,
            "name": "repo",
            "owner": {"login": "alice"},
            "full_name": "alice/repo",
        }
        requests = [
            ("/api/github/user/alice", "github_metadata"),
            ("/api/github/user/alice/repositories", "github_metadata"),
            ("/api/github/user/alice/analytics", "user_analytics"),
            ("/api/github/repository/alice/repo", "github_metadata"),
            ("/api/github/repository/alice/repo/identity", "github_metadata"),
            ("/api/github/repository/alice/repo/commits", "github_metadata"),
            ("/api/github/repository/alice/repo/contributors", "github_metadata"),
            ("/api/github/repository/alice/repo/evidence", "repository_evidence"),
        ]
        with ExitStack() as stack:
            stack.enter_context(patch("app._public_rate_limit", side_effect=lambda bucket: calls.append(bucket)))
            stack.enter_context(patch("app.get_user", return_value={"login": "alice"}))
            stack.enter_context(patch("app.get_user_repositories", return_value=[]))
            stack.enter_context(patch("app.get_repository", return_value=public_repo))
            stack.enter_context(patch("app.get_repository_commits", return_value=[]))
            stack.enter_context(patch("app.get_repository_contributors", return_value=[]))
            stack.enter_context(patch("app.get_repository_evidence", return_value={"evidence": True}))
            stack.enter_context(patch("app._cache.get_analysis", return_value={"cached": True}))
            client = app.test_client()
            for path, _bucket in requests:
                response = client.get(path)
                self.assertNotEqual(response.status_code, 503, path)

        self.assertEqual(calls, [bucket for _, bucket in requests])

    def test_upstream_github_rate_limit_is_distinct_and_has_retry_after(self):
        from github_errors import GitHubRateLimitExceeded
        from app import app

        with patch("app._public_rate_limit", return_value=None):
            with patch("app.get_user", side_effect=GitHubRateLimitExceeded(37)):
                response = app.test_client().get("/api/github/user/alice")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json(), {"error": "GitHub rate limit exceeded. Try again later."})
        self.assertEqual(response.headers["Retry-After"], "37")


class TestGitHubLimitClassification(unittest.TestCase):
    def test_sync_client_distinguishes_upstream_limit_from_other_forbidden(self):
        from github_errors import GitHubRateLimitExceeded
        from services import github_service

        class Response:
            status_code = 429
            headers = {"Retry-After": "37"}

            def raise_for_status(self):
                raise AssertionError("rate limits are classified before generic status handling")

            def json(self):
                return {}

        with patch("services.github_service.consume_github_upstream_call"), patch(
            "services.github_service.requests.Session"
        ) as session_factory:
            session_factory.return_value.__enter__.return_value.get.return_value = Response()
            with self.assertRaises(GitHubRateLimitExceeded) as error:
                github_service.github_get("/users/alice")
            self.assertEqual(
                session_factory.return_value.__enter__.return_value.max_redirects,
                1,
            )
        self.assertEqual(error.exception.retry_after, 37)

        class Forbidden(Response):
            status_code = 403
            headers = {}

            def raise_for_status(self):
                raise github_service.requests.HTTPError("forbidden")

        with patch("services.github_service.consume_github_upstream_call"), patch(
            "services.github_service.requests.Session"
        ) as session_factory:
            session_factory.return_value.__enter__.return_value.get.return_value = Forbidden()
            with self.assertRaises(github_service.requests.HTTPError):
                github_service.github_get("/users/alice")


@unittest.skipUnless(
    os.environ.get("GITSCOPE_RATE_LIMIT_TEST_DATABASE_URL"),
    "set GITSCOPE_RATE_LIMIT_TEST_DATABASE_URL to an isolated migrated PostgreSQL test database",
)
class TestPostgresSharedRateLimit(unittest.TestCase):
    def test_weighted_cost_is_atomic_across_independent_pools(self):
        url = os.environ["GITSCOPE_RATE_LIMIT_TEST_DATABASE_URL"]
        bucket = "test_" + uuid4().hex[:24]
        stores = [PostgresRateLimitStore(url), PostgresRateLimitStore(url)]
        limiters = [DistributedRateLimiter(store) for store in stores]
        barrier = threading.Barrier(8)

        def consume(index):
            barrier.wait()
            return limiters[index % 2].allow(
                bucket,
                global_limit=10,
                cost=3,
                window_seconds=3600,
            )[0]

        try:
            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(consume, range(8)))
            self.assertEqual(sum(results), 3)
        finally:
            for store in stores:
                with store._pool.connection(timeout=3) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "DELETE FROM gitscope_rate_limit_windows WHERE bucket = %s",
                            (bucket,),
                        )
                store.close()

    def test_separate_processes_share_the_same_atomic_counter(self):
        url = os.environ["GITSCOPE_RATE_LIMIT_TEST_DATABASE_URL"]
        bucket = "test_" + uuid4().hex[:24]
        context = multiprocessing.get_context("spawn")
        barrier = context.Barrier(2)
        result_queue = context.Queue()
        processes = [
            context.Process(
                target=_multiprocess_limiter_batch,
                args=(url, bucket, barrier, result_queue),
            )
            for _ in range(2)
        ]
        try:
            for process in processes:
                process.start()
            for process in processes:
                process.join(timeout=30)
            self.assertTrue(all(process.exitcode == 0 for process in processes))
            self.assertEqual(sum(result_queue.get(timeout=2) for _ in processes), 7)
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
            store = PostgresRateLimitStore(url)
            try:
                store._ensure_open()
                with store._pool.connection(timeout=3) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "DELETE FROM gitscope_rate_limit_windows WHERE bucket = %s",
                            (bucket,),
                        )
            finally:
                store.close()
            result_queue.close()

    def test_two_independent_pools_share_atomic_global_limit(self):
        url = os.environ["GITSCOPE_RATE_LIMIT_TEST_DATABASE_URL"]
        stores = [PostgresRateLimitStore(url), PostgresRateLimitStore(url)]
        limiters = [DistributedRateLimiter(store) for store in stores]
        bucket = "test_" + uuid4().hex[:24]
        barrier = threading.Barrier(32)

        def consume(index):
            barrier.wait()
            return limiters[index % 2].allow(
                bucket,
                global_limit=7,
                window_seconds=3600,
            )[0]

        try:
            with ThreadPoolExecutor(max_workers=32) as executor:
                results = list(executor.map(consume, range(32)))
            self.assertEqual(sum(results), 7)
        finally:
            for store in stores:
                with store._pool.connection(timeout=3) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "DELETE FROM gitscope_rate_limit_windows WHERE bucket = %s",
                            (bucket,),
                        )
                store.close()

    def test_service_wide_cap_is_shared_and_fixed_window_resets(self):
        url = os.environ["GITSCOPE_RATE_LIMIT_TEST_DATABASE_URL"]
        stores = [PostgresRateLimitStore(url), PostgresRateLimitStore(url)]
        limiters = [DistributedRateLimiter(store) for store in stores]
        bucket = "test_" + uuid4().hex[:24]
        try:
            allowed = [
                limiters[index % 2].allow(
                    bucket, global_limit=5, window_seconds=3600
                )[0]
                for index in range(12)
            ]
            self.assertEqual(sum(allowed), 5)
            with stores[0]._pool.connection(timeout=3) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE gitscope_rate_limit_windows
                        SET window_start = clock_timestamp() - interval '2 hours'
                        WHERE bucket = %s AND client_key = 'global'
                        """,
                        (bucket,),
                    )
            self.assertTrue(
                limiters[0].allow(
                    bucket, global_limit=5, window_seconds=3600
                )[0]
            )
        finally:
            for store in stores:
                with store._pool.connection(timeout=3) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "DELETE FROM gitscope_rate_limit_windows WHERE bucket = %s",
                            (bucket,),
                        )
                store.close()


if __name__ == "__main__":
    unittest.main()

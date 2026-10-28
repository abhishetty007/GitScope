import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import sys
import threading
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rate_limit import DistributedRateLimiter, github_upstream_budget_per_hour
from runtime_config import validate_runtime_config
from services import github_async_client, github_service


def valid_production_settings():
    return {
        "GITSCOPE_ENV": "production",
        "GITSCOPE_CORS_ORIGINS": "",
        "GITSCOPE_RATE_LIMIT_DATABASE_URL": "postgresql://limiter:password@example.test/gitscope?sslmode=require",
        "GITHUB_TOKEN": "ghp_test-token",
        "GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR": "2000",
    }


class TestProductionBounds(unittest.TestCase):
    def test_async_collector_uses_shared_bounded_github_configuration(self):
        self.assertEqual(
            github_async_client._MAX_ANALYSIS_SECONDS,
            github_service._MAX_ANALYSIS_SECONDS,
        )
        self.assertEqual(
            github_async_client._MAX_GITHUB_PAGES,
            github_service._MAX_GITHUB_PAGES,
        )
        self.assertIs(
            github_async_client.GitHubCollectionLimitError,
            github_service.GitHubCollectionLimitError,
        )
        self.assertTrue(callable(github_service.bounded_evidence_paths))

    def test_production_numeric_bounds_reject_invalid_values(self):
        with self.assertRaisesRegex(RuntimeError, "GITSCOPE_GITHUB_MAX_PAGES"):
            validate_runtime_config({
                "GITSCOPE_ENV": "production",
                "GITSCOPE_CORS_ORIGINS": "",
                "GITSCOPE_GITHUB_MAX_PAGES": "0",
            })
        validate_runtime_config(valid_production_settings())

    def test_production_tls_uses_libpq_parsing_and_rejects_ambiguous_urls(self):
        from psycopg.conninfo import conninfo_to_dict

        from runtime_config import _validate_rate_limit_database_url

        valid = "postgresql://limiter:password@example.test/gitscope?sslmode=require"
        self.assertEqual(conninfo_to_dict(valid)["sslmode"], "require")
        _validate_rate_limit_database_url(valid)
        _validate_rate_limit_database_url(
            "postgresql://limiter:password@example.test/gitscope?sslmode=verify-full"
        )
        _validate_rate_limit_database_url(
            valid + "&application_name=gitscope-limiter&channel_binding=require"
        )

        for query in (
            "sslmode=disable",
            "sslmode=require&sslmode=disable",
            "sslmode=disable&sslmode=require",
            "sslmode=require&sslmode=require",
            "%73slmode=require&sslmode=disable",
            "sslmode=",
        ):
            url = f"postgresql://limiter:password@example.test/gitscope?{query}"
            if "&" in query:
                # Exercise the actual libpq parser for the ambiguous form;
                # it may reject duplicates or resolve a value, but application
                # validation must reject the ambiguity either way.
                try:
                    effective_sslmode = conninfo_to_dict(url).get("sslmode")
                except Exception:
                    effective_sslmode = "driver-rejected"
                self.assertIn(
                    effective_sslmode,
                    {"require", "disable", "driver-rejected"},
                )
            with self.subTest(query=query), self.assertRaises(RuntimeError):
                _validate_rate_limit_database_url(url)

        for url in (
            "not-a-postgres-url",
            "postgresql://limiter:password@example.test:bad/gitscope?sslmode=require",
            "postgresql://limiter:password@example.test/gitscope",
        ):
            with self.subTest(url=url), self.assertRaises(RuntimeError):
                _validate_rate_limit_database_url(url)

    def test_nonproduction_does_not_apply_production_tls_gate(self):
        validate_runtime_config({
            "GITSCOPE_ENV": "development",
            "GITSCOPE_RATE_LIMIT_DATABASE_URL": "postgresql://invalid",
        })

    def test_production_requires_an_explicit_upstream_hourly_budget(self):
        settings = valid_production_settings()
        settings.pop("GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR")
        with self.assertRaisesRegex(RuntimeError, "UPSTREAM_BUDGET_PER_HOUR"):
            validate_runtime_config(settings)

    def test_upstream_budget_defaults_and_bounds_follow_authentication_class(self):
        self.assertEqual(github_upstream_budget_per_hour({"GITHUB_TOKEN": "ghp_test"}), 2000)
        self.assertEqual(github_upstream_budget_per_hour({"GITHUB_TOKEN": "github_pat_test"}), 2000)
        self.assertEqual(github_upstream_budget_per_hour({"GITHUB_TOKEN": "ghs_test"}), 200)
        self.assertEqual(github_upstream_budget_per_hour({}), 20)
        self.assertEqual(
            github_upstream_budget_per_hour({
                "GITHUB_TOKEN": "ghp_test",
                "GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR": "2500",
            }),
            2500,
        )
        for environ in (
            {"GITHUB_TOKEN": "ghp_test", "GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR": "2501"},
            {"GITHUB_TOKEN": "ghs_test", "GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR": "401"},
            {"GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR": "31"},
        ):
            with self.subTest(authenticated=bool(environ.get("GITHUB_TOKEN"))), self.assertRaises(RuntimeError):
                github_upstream_budget_per_hour(environ)

    def test_production_rejects_budget_above_unauthenticated_ceiling(self):
        settings = valid_production_settings()
        settings.pop("GITHUB_TOKEN")
        settings["GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR"] = "31"
        with self.assertRaisesRegex(RuntimeError, "GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR"):
            validate_runtime_config(settings)

    def test_distributed_limiter_instances_share_atomic_store_under_concurrency(self):
        class SharedStore:
            def __init__(self):
                self.lock = threading.Lock()
                self.counts = {}

            def consume(self, bucket, *, global_limit, window_seconds, cost=1):
                with self.lock:
                    self.counts[bucket] = self.counts.get(bucket, 0) + cost
                    return self.counts[bucket] <= global_limit, 1

        store = SharedStore()
        limiters = [DistributedRateLimiter(store), DistributedRateLimiter(store)]
        barrier = threading.Barrier(40)

        def request_limit(index):
            barrier.wait()
            return limiters[index % 2].allow(
                "repository", global_limit=10
            )[0]

        with ThreadPoolExecutor(max_workers=40) as pool:
            allowed = list(pool.map(request_limit, range(40)))

        self.assertEqual(sum(allowed), 10)

    def test_weighted_rate_limit_charges_atomic_cost_units(self):
        class WeightedStore:
            def __init__(self):
                self.lock = threading.Lock()
                self.used = 0

            def consume(self, _bucket, *, global_limit, window_seconds, cost=1):
                with self.lock:
                    self.used += cost
                    return self.used <= global_limit, 60

        store = WeightedStore()
        limiter = DistributedRateLimiter(store)
        self.assertTrue(limiter.allow("upstream", global_limit=10, cost=4)[0])
        self.assertTrue(limiter.allow("upstream", global_limit=10, cost=4)[0])
        self.assertFalse(limiter.allow("upstream", global_limit=10, cost=4)[0])
        self.assertEqual(store.used, 12)

    def test_github_call_is_charged_to_shared_minute_and_hour_budgets(self):
        import rate_limit

        class RecordingLimiter:
            def __init__(self):
                self.calls = []

            def allow(self, bucket, *, global_limit, cost=1, window_seconds=60):
                self.calls.append((bucket, global_limit, cost, window_seconds))
                return True, 1

        limiter = RecordingLimiter()
        with patch.dict(os.environ, {
            "GITHUB_TOKEN": "ghp_test-token",
            "GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR": "37",
        }), patch.object(
            rate_limit, "get_default_rate_limiter", return_value=limiter
        ):
            rate_limit.consume_github_upstream_call()
        self.assertEqual(
            limiter.calls,
            [
                ("github_upstream_minute", 300, 1, 60),
                ("github_upstream_hourly", 37, 1, 3600),
            ],
        )

    def test_hour_budget_denial_stops_the_request_with_retry_interval(self):
        import rate_limit
        from github_errors import GitHubUpstreamBudgetExceeded

        class Limiter:
            def allow(self, bucket, *, global_limit, cost=1, window_seconds=60):
                if bucket == rate_limit.GITHUB_UPSTREAM_MINUTE_BUCKET:
                    return True, 1
                return False, 42

        with patch.object(rate_limit, "get_default_rate_limiter", return_value=Limiter()):
            with self.assertRaises(GitHubUpstreamBudgetExceeded) as error:
                rate_limit.consume_github_upstream_call()
        self.assertEqual(error.exception.retry_after, 42)

    def test_synchronous_github_pagination_stops_at_configured_bound(self):
        full_page = [{}] * 100
        for collector, endpoint in (
            (github_service.get_user_repositories, "/users/alice/repos"),
            (github_service.get_repository_commits, "/repos/alice/repo/commits"),
            (github_service.get_repository_contributors, "/repos/alice/repo/contributors"),
        ):
            with self.subTest(endpoint=endpoint), patch.object(github_service, "_MAX_GITHUB_PAGES", 2), patch.object(
                github_service, "github_get", return_value=full_page
            ) as get:
                with self.assertRaises(github_service.GitHubCollectionLimitError):
                    if "users/" in endpoint:
                        collector("alice")
                    else:
                        collector("alice", "repo")
                self.assertEqual(get.call_count, 2)

    def test_async_pagination_stops_at_configured_bound(self):
        async def run():
            with patch.object(github_async_client, "_MAX_GITHUB_PAGES", 2), patch.object(
                github_async_client, "_async_get", new=AsyncMock(return_value=[{}] * 100)
            ) as get:
                with self.assertRaises(github_service.GitHubCollectionLimitError):
                    await github_async_client._async_get_all_pages(object(), "/commits")
                self.assertEqual(get.await_count, 2)

        asyncio.run(run())

    def test_analysis_deadline_cancels_async_collection_safely(self):
        async def run():
            async def slow_collection(_owner, _repository):
                await asyncio.sleep(1)

            with patch.object(github_async_client, "_MAX_ANALYSIS_SECONDS", 0.01), patch.object(
                github_async_client, "_collect_evidence_async_impl", side_effect=slow_collection
            ):
                with self.assertRaisesRegex(TimeoutError, "deadline"):
                    await github_async_client._collect_evidence_async("alice", "repo")

        asyncio.run(run())

    def test_evidence_file_fetch_list_is_deterministic_and_bounded(self):
        with patch.object(github_service, "_MAX_FILE_FETCHES", 2):
            paths = github_service.bounded_evidence_paths(
                ["README.md", "LICENSE"],
                [".github/workflows/z.yml", ".github/workflows/a.yml", "README.md"],
            )
        self.assertEqual(paths, ["LICENSE", "README.md"])


class TestPublicAnalyticsRateLimit(unittest.TestCase):
    def test_analytics_route_returns_safe_429_after_limit_and_recovers_after_window(self):
        from app import app

        import app as app_module
        class Store:
            count = 0

            def consume(self, bucket, *, global_limit, window_seconds, cost=1):
                self.count += 1
                self.count += cost - 1
                allowed = self.count <= global_limit
                return allowed, 10

        original_limiter = app_module._rate_limiter
        store = Store()
        app_module._rate_limiter = DistributedRateLimiter(store, window_seconds=10)
        original_policy = app_module._RATE_LIMIT_POLICIES["user_analytics"]
        app_module._RATE_LIMIT_POLICIES["user_analytics"] = 1
        try:
            with patch("app.get_user_repositories", return_value=[]):
                client = app.test_client()
                self.assertEqual(client.get("/api/github/user/alice/analytics").status_code, 200)
                throttled = client.get("/api/github/user/alice/analytics")
                self.assertEqual(throttled.status_code, 429)
                self.assertEqual(throttled.get_json(), {
                    "error": "Too many GitHub requests. Try again later."
                })
                self.assertEqual(throttled.headers["Retry-After"], "10")
                store.count = 0
                self.assertEqual(client.get("/api/github/user/alice/analytics").status_code, 200)
        finally:
            app_module._rate_limiter = original_limiter
            app_module._RATE_LIMIT_POLICIES["user_analytics"] = original_policy


if __name__ == "__main__":
    unittest.main()

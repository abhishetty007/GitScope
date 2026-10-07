import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rate_limit import FixedWindowRateLimiter
from runtime_config import validate_runtime_config
from services import github_async_client, github_service


class TestProductionBounds(unittest.TestCase):
    def test_production_numeric_bounds_reject_invalid_values(self):
        with self.assertRaisesRegex(RuntimeError, "GITSCOPE_GITHUB_MAX_PAGES"):
            validate_runtime_config({
                "GITSCOPE_ENV": "production",
                "GITSCOPE_CORS_ORIGINS": "",
                "GITSCOPE_GITHUB_MAX_PAGES": "0",
            })
        validate_runtime_config({"GITSCOPE_ENV": "production", "GITSCOPE_CORS_ORIGINS": ""})

    def test_fixed_window_limiter_expires_and_retains_only_fixed_route_keys(self):
        now = [0]
        limiter = FixedWindowRateLimiter(1, window_seconds=10, clock=lambda: now[0])
        self.assertEqual(limiter.allow("user"), (True, 0))
        self.assertFalse(limiter.allow("user")[0])
        self.assertEqual(limiter.key_count, 1)
        now[0] = 10
        self.assertEqual(limiter.allow("user"), (True, 0))
        limiter.allow("repository")
        self.assertEqual(limiter.key_count, 2)
        bounded = FixedWindowRateLimiter(2, max_keys=3, clock=lambda: now[0])
        for index in range(20):
            bounded.allow(str(index))
        self.assertEqual(bounded.key_count, 3)

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

        now = [0]
        import app as app_module
        original_limiter = app_module._public_analytics_limiter
        app_module._public_analytics_limiter = FixedWindowRateLimiter(
            1, window_seconds=10, clock=lambda: now[0]
        )
        try:
            with patch("app.get_user_repositories", return_value=[]):
                client = app.test_client()
                self.assertEqual(client.get("/api/github/user/alice/analytics").status_code, 200)
                throttled = client.get("/api/github/user/alice/analytics")
                self.assertEqual(throttled.status_code, 429)
                self.assertEqual(throttled.get_json(), {
                    "error": "Too many analytics requests. Try again later."
                })
                self.assertEqual(throttled.headers["Retry-After"], "10")
                now[0] = 10
                self.assertEqual(client.get("/api/github/user/alice/analytics").status_code, 200)
            self.assertEqual(app_module._public_analytics_limiter.key_count, 1)
        finally:
            app_module._public_analytics_limiter = original_limiter


if __name__ == "__main__":
    unittest.main()

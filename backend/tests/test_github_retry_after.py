import os
import sys
import threading
import unittest
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
from github_errors import (
    DEFAULT_RETRY_AFTER_SECONDS,
    MAX_RETRY_AFTER_SECONDS,
    parse_retry_after,
)
from services import github_async_client, github_service


NOW = datetime(2030, 10, 21, 7, 26, 0, tzinfo=timezone.utc)


class TestRetryAfterParsing(unittest.TestCase):
    def test_delta_seconds_and_http_date(self):
        self.assertEqual(parse_retry_after("120", now=NOW), 120)
        self.assertEqual(
            parse_retry_after("Mon, 21 Oct 2030 07:28:00 GMT", now=NOW),
            120,
        )

    def test_past_malformed_missing_and_reset_fallback(self):
        self.assertEqual(
            parse_retry_after("Wed, 21 Oct 2030 07:25:00 GMT", now=NOW),
            1,
        )
        self.assertEqual(parse_retry_after("not-a-date", "bad-reset", now=NOW), DEFAULT_RETRY_AFTER_SECONDS)
        self.assertEqual(parse_retry_after(None, None, now=NOW), DEFAULT_RETRY_AFTER_SECONDS)
        self.assertEqual(parse_retry_after("bad", str(int(NOW.timestamp()) + 45), now=NOW), 45)

    def test_extreme_and_negative_values_are_clamped_safely(self):
        self.assertEqual(parse_retry_after("999999999999999999999", now=NOW), MAX_RETRY_AFTER_SECONDS)
        self.assertEqual(parse_retry_after("-10", now=NOW), 1)

    def test_sync_client_path_uses_shared_parser_and_reset_fallback(self):
        class Response:
            headers = {"Retry-After": "Mon, 21 Oct 2030 07:28:00 GMT"}

        self.assertEqual(github_service._github_retry_after(Response(), now=NOW), 120)
        Response.headers = {"Retry-After": "bad", "X-RateLimit-Reset": str(int(NOW.timestamp()) + 23)}
        self.assertEqual(github_service._github_retry_after(Response(), now=NOW), 23)

    def test_async_client_path_uses_shared_parser(self):
        response = httpx.Response(
            429,
            headers={"Retry-After": "Mon, 21 Oct 2030 07:28:00 GMT"},
            request=httpx.Request("GET", "https://api.github.com/test"),
        )
        with self.assertRaises(github_async_client.GitHubRateLimitExceeded) as error:
            github_async_client._check_rate_limit(response, str(response.request.url), now=NOW)
        self.assertEqual(error.exception.retry_after, 120)

    def test_primary_and_secondary_limits_use_reset_and_secondary_message(self):
        from github_errors import GitHubRateLimitExceeded

        primary = httpx.Response(
            403,
            headers={
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(NOW.timestamp()) + 45),
            },
            request=httpx.Request("GET", "https://api.github.com/test"),
        )
        with self.assertRaises(GitHubRateLimitExceeded) as primary_error:
            github_async_client._check_rate_limit(primary, str(primary.request.url), now=NOW)
        self.assertEqual(primary_error.exception.retry_after, 45)

        secondary = httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "17"},
            json={"message": "You have exceeded a secondary rate limit."},
            request=httpx.Request("GET", "https://api.github.com/test"),
        )
        with self.assertRaises(GitHubRateLimitExceeded) as secondary_error:
            github_async_client._check_rate_limit(secondary, str(secondary.request.url), now=NOW)
        self.assertEqual(secondary_error.exception.retry_after, DEFAULT_RETRY_AFTER_SECONDS)

        class SyncSecondary:
            status_code = 403
            headers = {"X-RateLimit-Remaining": "17"}

            @staticmethod
            def json():
                return {"message": "You have exceeded a secondary rate limit."}

        self.assertTrue(github_service._is_github_rate_limited(SyncSecondary()))
        self.assertEqual(github_service._github_retry_after(SyncSecondary(), now=NOW), DEFAULT_RETRY_AFTER_SECONDS)

    def test_clients_charge_shared_budget_before_network_io(self):
        from github_errors import GitHubUpstreamBudgetExceeded

        with patch.object(
            github_service,
            "consume_github_upstream_call",
            side_effect=GitHubUpstreamBudgetExceeded(17),
        ), patch.object(github_service.requests, "Session") as session:
            with self.assertRaises(GitHubUpstreamBudgetExceeded):
                github_service.github_get("/users/alice")
            session.assert_not_called()

        async def exercise_async():
            client = type("Client", (), {"get": None})()
            from unittest.mock import AsyncMock
            client.get = AsyncMock()
            with patch.object(
                github_async_client,
                "consume_github_upstream_call",
                side_effect=GitHubUpstreamBudgetExceeded(17),
            ):
                with self.assertRaises(GitHubUpstreamBudgetExceeded):
                    await github_async_client._async_get(client, "/users/alice")
            client.get.assert_not_awaited()

        import asyncio
        asyncio.run(exercise_async())

    def test_redirect_hops_are_charged_before_following(self):
        redirect = type("Redirect", (), {"is_redirect": True})()
        with patch.object(github_service, "consume_github_upstream_call") as consume:
            self.assertIs(github_service._charge_redirect(redirect), redirect)
            consume.assert_called_once_with()

        async def check_async():
            response = httpx.Response(
                302,
                headers={"Location": "https://api.github.com/next"},
                request=httpx.Request("GET", "https://api.github.com/start"),
            )
            with patch.object(github_async_client, "consume_github_upstream_call") as consume:
                await github_async_client._charge_redirect_async(response)
                consume.assert_called_once_with()

        import asyncio
        asyncio.run(check_async())

    def test_file_fetch_does_not_swallow_budget_or_database_failure(self):
        from github_errors import GitHubRateLimitExceeded, GitHubUpstreamBudgetExceeded
        from rate_limit import RateLimitStoreUnavailable

        async def run(error):
            with patch.object(
                github_async_client,
                "consume_github_upstream_call",
                side_effect=error,
            ):
                with self.assertRaises(type(error)):
                    await github_async_client._fetch_file(
                        object(), "alice", "repo", "README.md", "main"
                    )

        import asyncio
        asyncio.run(run(GitHubRateLimitExceeded(30)))
        asyncio.run(run(GitHubUpstreamBudgetExceeded(20)))
        asyncio.run(run(RateLimitStoreUnavailable()))


class TestSynchronousRequestDeduplication(unittest.TestCase):
    def test_concurrent_identical_github_gets_charge_only_once(self):
        import request_dedupe

        network_started = threading.Event()
        follower_waiting = threading.Event()
        release_network = threading.Event()

        class TrackingFuture(Future):
            def result(self, timeout=None):
                follower_waiting.set()
                return super().result(timeout=timeout)

        class Response:
            status_code = 200
            headers = {}

            @staticmethod
            def raise_for_status():
                return None

            @staticmethod
            def json():
                return {"login": "alice"}

        def network_call(*_args, **_kwargs):
            network_started.set()
            if not release_network.wait(timeout=5):
                raise TimeoutError("test did not release the mocked network call")
            return Response()

        with patch.object(request_dedupe, "Future", TrackingFuture), patch.object(
            github_service, "consume_github_upstream_call"
        ) as consume, patch.object(github_service.requests, "Session") as session_factory:
            session_factory.return_value.__enter__.return_value.get.side_effect = network_call
            barrier = threading.Barrier(2)

            def get_user():
                barrier.wait(timeout=3)
                return github_service.github_get("/users/alice")

            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(get_user)
                second = executor.submit(get_user)
                self.assertTrue(network_started.wait(timeout=3))
                self.assertTrue(follower_waiting.wait(timeout=3))
                release_network.set()
                results = [first.result(timeout=6), second.result(timeout=6)]

        self.assertEqual(results, [{"login": "alice"}, {"login": "alice"}])
        consume.assert_called_once_with()
        session_factory.return_value.__enter__.return_value.get.assert_called_once()


if __name__ == "__main__":
    unittest.main()

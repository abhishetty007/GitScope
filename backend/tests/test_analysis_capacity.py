import os
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class AtomicBudget:
    def __init__(self):
        self.lock = threading.Lock()
        self.counts = {}

    def allow(self, bucket, *, global_limit, cost=1, window_seconds=None):
        with self.lock:
            self.counts[bucket] = self.counts.get(bucket, 0) + cost
            return self.counts[bucket] <= global_limit, max(1, window_seconds or 1)


def _public_repo(owner, repository):
    return {
        "id": 123,
        "private": False,
        "name": repository,
        "full_name": f"{owner}/{repository}",
        "default_branch": "main",
    }


def _evidence(owner, repository):
    return {
        "repository": {"name": repository, "full_name": f"{owner}/{repository}"},
        "structure": {},
        "important_files": {},
        "workflows": [],
        "repository_flags": {},
        "file_contents": {},
        "_commits": [],
        "_commits_truncated": False,
        "_contributors": [],
        "_workflow_runs": [],
    }


class TestAnalysisCapacity(unittest.TestCase):
    def setUp(self):
        from app import app
        import cache

        self.app = app
        self.cache = cache
        self.cache.clear_analysis()
        self.cache.clear_raw()

    def test_consecutive_fresh_analyses_proceed_with_shared_upstream_capacity(self):
        import rate_limit

        owner = "capacity-regression"
        budget = AtomicBudget()
        collection_calls = []

        def guarded_repository(owner_name, repository):
            rate_limit.consume_github_upstream_call()
            return _public_repo(owner_name, repository)

        with patch.object(rate_limit, "get_default_rate_limiter", return_value=budget), patch.object(
            rate_limit, "github_upstream_budget_per_hour", return_value=2000
        ), patch("app._public_rate_limit", side_effect=AssertionError("no independent analytics quota")), patch(
            "app.get_repository", side_effect=guarded_repository
        ), patch(
            "app.collect_evidence",
            side_effect=lambda requested_owner, requested_repo, **_kwargs: (
                collection_calls.append((requested_owner, requested_repo))
                or _evidence(requested_owner, requested_repo)
            ),
        ), patch("app.analyze_engineering_health", return_value={"score": 85}), patch(
            "app.analyze_commits", return_value={"total": 0}
        ), patch("app.analyze_contributors", return_value={"total": 0}):
            client = self.app.test_client()
            responses = [
                client.get(f"/api/github/repository/{owner}/repo-{index}/analytics")
                for index in range(3)
            ]

        self.assertEqual([response.status_code for response in responses], [200, 200, 200])
        self.assertEqual(len(collection_calls), 3)
        self.assertEqual(budget.counts[rate_limit.GITHUB_UPSTREAM_BUDGET_BUCKET], 3)

    def test_concurrent_identical_analysis_is_coalesced_before_upstream_calls(self):
        import rate_limit
        import request_dedupe
        from concurrent.futures import Future

        owner, repository = "capacity-regression", "same-repo"
        self.cache.clear_analysis(owner, repository)
        budget = AtomicBudget()
        repo_started = threading.Event()
        follower_waiting = threading.Event()
        release_repo = threading.Event()
        repo_calls = []
        collection_calls = []

        def guarded_repository(owner_name, repository_name):
            repo_calls.append((owner_name, repository_name))
            rate_limit.consume_github_upstream_call()
            repo_started.set()
            if not release_repo.wait(timeout=5):
                raise TimeoutError("test did not release repository validation")
            return _public_repo(owner_name, repository_name)

        class TrackingFuture(Future):
            def result(self, timeout=None):
                follower_waiting.set()
                return super().result(timeout=timeout)

        with patch.object(request_dedupe, "Future", TrackingFuture), patch.object(
            rate_limit, "get_default_rate_limiter", return_value=budget
        ), patch.object(rate_limit, "github_upstream_budget_per_hour", return_value=2000), patch(
            "app._public_rate_limit", side_effect=AssertionError("no independent analytics quota")
        ), patch("app.get_repository", side_effect=guarded_repository), patch(
            "app.collect_evidence",
            side_effect=lambda requested_owner, requested_repo, **_kwargs: (
                collection_calls.append((requested_owner, requested_repo))
                or _evidence(requested_owner, requested_repo)
            ),
        ), patch("app.analyze_engineering_health", return_value={"score": 85}), patch(
            "app.analyze_commits", return_value={"total": 0}
        ), patch("app.analyze_contributors", return_value={"total": 0}):
            barrier = threading.Barrier(2)

            def fetch_analysis():
                barrier.wait(timeout=3)
                return self.app.test_client().get(
                    f"/api/github/repository/{owner}/{repository}/analytics"
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(fetch_analysis)
                second = executor.submit(fetch_analysis)
                self.assertTrue(repo_started.wait(timeout=3))
                self.assertTrue(follower_waiting.wait(timeout=3))
                release_repo.set()
                responses = [first.result(timeout=8), second.result(timeout=8)]

        self.assertEqual([response.status_code for response in responses], [200, 200])
        self.assertEqual(responses[0].get_json(), responses[1].get_json())
        self.assertEqual(repo_calls, [(owner, repository)])
        self.assertEqual(collection_calls, [(owner, repository)])
        self.assertEqual(budget.counts[rate_limit.GITHUB_UPSTREAM_BUDGET_BUCKET], 1)

    def test_analysis_fails_closed_when_the_shared_limiter_fails(self):
        from rate_limit import RateLimitStoreUnavailable

        with patch("app.get_repository", side_effect=RateLimitStoreUnavailable()):
            response = self.app.test_client().get(
                "/api/github/repository/alice/repo/analytics"
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "5")
        self.assertEqual(
            response.get_json(),
            {"error": "Service temporarily unavailable. Try again shortly."},
        )


if __name__ == "__main__":
    unittest.main()

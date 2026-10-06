"""
test_cache_and_async.py — Tests for Phase 2 cache and async collector.

Tests:
    1. Cache get/set/expiry (TTLCache behaviour)
    2. Cache hit — value returned without re-setting
    3. Cache clear — single entry and full clear
    4. Raw cache key builders are unique and deterministic
    5. Async collector returns correct evidence shape (mocked network)
    6. Async collector: 404 on repo returns None
    7. Async collector: file fetch failure is tolerated (partial degradation)
    8. Async collector: commits/contributors failures are tolerated
    9. collect_evidence integration — _commits/_contributors present

All GitHub HTTP calls are mocked with unittest.mock so no network
is required and no credentials are needed.
"""

import sys
import os
import asyncio
import time
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

# Ensure backend root is importable
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

import cache as _cache


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

def _make_repo(owner="alice", name="myrepo"):
    return {
        "name": name,
        "full_name": f"{owner}/{name}",
        "description": "test repo",
        "language": "Python",
        "topics": [],
        "license": None,
        "default_branch": "main",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-10-01T00:00:00Z",
        "pushed_at": "2024-10-01T00:00:00Z",
        "archived": False,
        "disabled": False,
        "fork": False,
        "stargazers_count": 10,
        "forks_count": 2,
        "open_issues_count": 0,
        "watchers_count": 10,
        "size": 500,
        "html_url": f"https://github.com/{owner}/{name}",
    }


def _make_tree():
    return {
        "truncated": False,
        "tree": [
            {"path": "README.md", "type": "blob", "size": 1000},
            {"path": "src/main.py", "type": "blob", "size": 500},
            {"path": "tests/test_main.py", "type": "blob", "size": 300},
            {"path": "src", "type": "tree", "size": 0},
            {"path": "tests", "type": "tree", "size": 0},
        ],
    }


def _make_commit(author="Alice", date="2024-09-01T12:00:00Z"):
    return {
        "sha": "abc123",
        "commit": {
            "author": {"name": author, "date": date},
            "message": "feat: initial commit",
        },
        "html_url": "https://github.com/alice/myrepo/commit/abc123",
    }


def _make_contributor(login="alice", contributions=50):
    return {"login": login, "contributions": contributions}


# -----------------------------------------------------------------
# 1-3: Cache unit tests
# -----------------------------------------------------------------

class TestCacheBasic(unittest.TestCase):

    def setUp(self):
        # Clear caches before each test
        _cache.clear_analysis()
        _cache.clear_raw()

    def test_analysis_cache_miss_returns_none(self):
        result = _cache.get_analysis("owner", "repo")
        self.assertIsNone(result)

    def test_analysis_cache_set_and_get(self):
        payload = {"score": 85, "grade": "B"}
        _cache.set_analysis("alice", "myrepo", payload)
        result = _cache.get_analysis("alice", "myrepo")
        self.assertEqual(result, payload)

    def test_analysis_cache_clear_single(self):
        _cache.set_analysis("alice", "myrepo", {"score": 90})
        _cache.set_analysis("bob", "otherrepo", {"score": 70})
        _cache.clear_analysis("alice", "myrepo")
        self.assertIsNone(_cache.get_analysis("alice", "myrepo"))
        self.assertIsNotNone(_cache.get_analysis("bob", "otherrepo"))

    def test_analysis_cache_clear_all(self):
        _cache.set_analysis("alice", "myrepo", {"score": 90})
        _cache.set_analysis("bob", "other", {"score": 70})
        _cache.clear_analysis()
        self.assertIsNone(_cache.get_analysis("alice", "myrepo"))
        self.assertIsNone(_cache.get_analysis("bob", "other"))

    def test_raw_cache_set_and_get(self):
        key = _cache.repo_key("alice", "myrepo")
        _cache.set_raw(key, {"name": "myrepo"})
        result = _cache.get_raw(key)
        self.assertEqual(result["name"], "myrepo")

    def test_raw_cache_miss_returns_none(self):
        key = _cache.repo_key("nobody", "nothing")
        self.assertIsNone(_cache.get_raw(key))

    def test_raw_cache_clear_single(self):
        key = _cache.repo_key("alice", "myrepo")
        _cache.set_raw(key, {"x": 1})
        _cache.clear_raw(key)
        self.assertIsNone(_cache.get_raw(key))

    def test_raw_cache_clear_all(self):
        k1 = _cache.repo_key("alice", "a")
        k2 = _cache.tree_key("alice", "a", "main")
        _cache.set_raw(k1, {"x": 1})
        _cache.set_raw(k2, {"y": 2})
        _cache.clear_raw()
        self.assertIsNone(_cache.get_raw(k1))
        self.assertIsNone(_cache.get_raw(k2))


class TestCacheKeys(unittest.TestCase):
    """Key builders must be unique and deterministic."""

    def test_repo_key_deterministic(self):
        k1 = _cache.repo_key("alice", "repo")
        k2 = _cache.repo_key("alice", "repo")
        self.assertEqual(k1, k2)

    def test_tree_key_includes_branch(self):
        k_main = _cache.tree_key("alice", "repo", "main")
        k_dev = _cache.tree_key("alice", "repo", "develop")
        self.assertNotEqual(k_main, k_dev)

    def test_file_key_includes_path(self):
        k1 = _cache.file_key("alice", "repo", "README.md", "main")
        k2 = _cache.file_key("alice", "repo", "LICENSE", "main")
        self.assertNotEqual(k1, k2)

    def test_commits_and_contributors_keys_differ(self):
        kc = _cache.commits_key("alice", "repo")
        kco = _cache.contributors_key("alice", "repo")
        self.assertNotEqual(kc, kco)

    def test_different_owners_produce_different_keys(self):
        k1 = _cache.repo_key("alice", "repo")
        k2 = _cache.repo_key("bob", "repo")
        self.assertNotEqual(k1, k2)


# -----------------------------------------------------------------
# 5-9: Async collector tests (mocked httpx)
# -----------------------------------------------------------------

def _make_mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    resp.headers = {}
    return resp


class TestAsyncCollector(unittest.IsolatedAsyncioTestCase):
    """Tests for _collect_evidence_async with mocked httpx.AsyncClient."""

    def setUp(self):
        _cache.clear_analysis()
        _cache.clear_raw()

    async def _run_with_mock(self, side_effects: list):
        """
        Patch httpx.AsyncClient.get to return side_effects in order,
        then run _collect_evidence_async.
        """
        from services.github_async_client import _collect_evidence_async

        mock_get = AsyncMock(side_effect=side_effects)
        with patch("httpx.AsyncClient.get", mock_get):
            return await _collect_evidence_async("alice", "myrepo")

    async def test_successful_collection_shape(self):
        """Collector returns correct top-level keys."""
        repo = _make_repo()
        tree = _make_tree()
        readme_content = {"content": __import__("base64").b64encode(b"# Hello").decode(), "path": "README.md", "name": "README.md", "size": 7, "sha": "abc", "type": "file"}
        commits = [_make_commit()]
        contributors = [_make_contributor()]

        side_effects = [
            _make_mock_response(repo),         # /repos/alice/myrepo
            _make_mock_response(tree),         # /git/trees/main
            # concurrent: README.md, commits (page 1), contributors (page 1)
            _make_mock_response(readme_content),
            _make_mock_response(commits),
            _make_mock_response([]),             # commits page 2 empty
            _make_mock_response(contributors),
            _make_mock_response([]),             # contributors page 2 empty
        ]

        result = await self._run_with_mock(side_effects)

        self.assertIsNotNone(result)
        self.assertIn("repository", result)
        self.assertIn("structure", result)
        self.assertIn("important_files", result)
        self.assertIn("workflows", result)
        self.assertIn("file_contents", result)
        self.assertIn("repository_flags", result)
        self.assertIn("_commits", result)
        self.assertIn("_contributors", result)

    async def test_repo_404_returns_none(self):
        """If the repo does not exist, collector returns None."""
        from services.github_async_client import _collect_evidence_async

        resp_404 = _make_mock_response(None, status_code=404)
        resp_404.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", AsyncMock(return_value=resp_404)):
            result = await _collect_evidence_async("alice", "nonexistent")

        self.assertIsNone(result)

    async def test_file_fetch_failure_is_tolerated(self):
        """
        If an individual file fetch raises an exception, the overall
        evidence collection must still succeed (partial degradation).
        """
        import base64
        from services.github_async_client import _collect_evidence_async

        repo = _make_repo()
        tree = _make_tree()
        commits = [_make_commit()]
        contributors = [_make_contributor()]

        call_count = 0

        async def mock_get(_self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "/contents/" in url:
                raise httpx.TimeoutException("timeout", request=MagicMock())
            if "/git/trees/" in url:
                return _make_mock_response(tree)
            if "/commits" in url:
                params = kwargs.get("params", {})
                if params.get("page", 1) == 1:
                    return _make_mock_response(commits)
                return _make_mock_response([])
            if "/contributors" in url:
                params = kwargs.get("params", {})
                if params.get("page", 1) == 1:
                    return _make_mock_response(contributors)
                return _make_mock_response([])
            return _make_mock_response(repo)

        import httpx
        with patch("httpx.AsyncClient.get", mock_get):
            result = await _collect_evidence_async("alice", "myrepo")

        self.assertIsNotNone(result)
        # File contents should be empty (all failed) but evidence is intact
        self.assertIn("structure", result)
        self.assertIn("repository_flags", result)

    async def test_commits_failure_returns_empty_list(self):
        """If commits endpoint fails, _commits defaults to []."""
        import base64
        from services.github_async_client import _collect_evidence_async

        repo = _make_repo()
        tree = {"truncated": False, "tree": []}  # empty tree, no files to fetch

        async def mock_get(_self, url, **kwargs):
            if "/git/trees/" in url:
                return _make_mock_response(tree)
            if "/commits" in url:
                raise Exception("network error")
            if "/contributors" in url:
                params = kwargs.get("params", {})
                if params.get("page", 1) == 1:
                    return _make_mock_response([_make_contributor()])
                return _make_mock_response([])
            return _make_mock_response(repo)

        with patch("httpx.AsyncClient.get", mock_get):
            result = await _collect_evidence_async("alice", "myrepo")

        self.assertIsNotNone(result)
        self.assertEqual(result["_commits"], [])


class TestCacheHitInCollector(unittest.TestCase):
    """
    Test that the outer analysis cache is hit by the Flask route.
    We test the cache module directly since route testing requires
    a full Flask test client setup.
    """

    def setUp(self):
        _cache.clear_analysis()
        _cache.clear_raw()

    def test_cache_hit_returns_same_object(self):
        payload = {"score": 92, "grade": "A"}
        _cache.set_analysis("alice", "myrepo", payload)
        result = _cache.get_analysis("alice", "myrepo")
        self.assertIs(result, payload)

    def test_different_repos_do_not_collide(self):
        _cache.set_analysis("alice", "repo1", {"score": 90})
        _cache.set_analysis("alice", "repo2", {"score": 70})
        self.assertEqual(_cache.get_analysis("alice", "repo1")["score"], 90)
        self.assertEqual(_cache.get_analysis("alice", "repo2")["score"], 70)

    def test_raw_cache_hit_skips_set(self):
        """Once a raw key is set, subsequent get returns same value."""
        key = _cache.commits_key("alice", "myrepo")
        commits = [{"sha": "abc"}]
        _cache.set_raw(key, commits)
        result = _cache.get_raw(key)
        self.assertEqual(result, commits)


class TestCollectEvidenceSyncWrapper(unittest.TestCase):
    """
    Test the public synchronous collect_evidence() wrapper.
    Verifies that _commits and _contributors are present in the output.
    """

    def setUp(self):
        _cache.clear_analysis()
        _cache.clear_raw()

    def test_sync_wrapper_returns_dict_with_private_keys(self):
        repo = _make_repo()
        tree = {"truncated": False, "tree": []}
        commits = [_make_commit()]
        contributors = [_make_contributor()]

        # ``httpx.AsyncClient.get`` is patched on the class, so the client
        # instance is passed as the first positional argument (bound method).
        async def mock_get(_self, url, **kwargs):
            if "/git/trees/" in url:
                return _make_mock_response(tree)
            if "/commits" in url:
                params = kwargs.get("params", {})
                if params.get("page", 1) == 1:
                    return _make_mock_response(commits)
                return _make_mock_response([])
            if "/contributors" in url:
                params = kwargs.get("params", {})
                if params.get("page", 1) == 1:
                    return _make_mock_response(contributors)
                return _make_mock_response([])
            return _make_mock_response(repo)

        with patch("httpx.AsyncClient.get", mock_get):
            from services.github_async_client import collect_evidence
            result = collect_evidence("alice", "myrepo")

        self.assertIsNotNone(result)
        self.assertIn("_commits", result)
        self.assertIn("_contributors", result)
        self.assertGreater(len(result["_commits"]), 0)
        self.assertGreater(len(result["_contributors"]), 0)

    def test_sync_wrapper_returns_none_for_missing_repo(self):
        resp_404 = _make_mock_response(None, status_code=404)
        resp_404.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", AsyncMock(return_value=resp_404)):
            from services.github_async_client import collect_evidence
            result = collect_evidence("nobody", "noexist")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

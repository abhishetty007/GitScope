import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cache
from services.analytics_service import analyze_commits, analyze_contributors, analyze_engineering_health, _ci_status
from services.monorepo_service import detect_monorepo


class TestPhase3Analytics(unittest.TestCase):
    def test_concentration_and_bus_factor(self):
        result = analyze_contributors([{"login": "a", "contributions": 50}, {"login": "b", "contributions": 30}, {"login": "c", "contributions": 20}])
        self.assertEqual(result["top_contributor_share"], .5)
        self.assertEqual(result["top3_share"], 1)
        self.assertEqual(result["bus_factor_50"], 1)
        self.assertEqual(result["bus_factor_80"], 2)
        self.assertAlmostEqual(result["herfindahl_index"], .38)
        self.assertEqual(analyze_contributors([])["bus_factor_80"], 0)

    def test_cadence_fields(self):
        now = datetime.now(timezone.utc)
        commits = [{"commit": {"author": {"name": "a", "date": (now - timedelta(days=n)).isoformat()}}} for n in (0, 10, 40, 400)]
        result = analyze_commits(commits)
        self.assertEqual(result["commits_last_30_days"], 2)
        self.assertEqual(result["commits_last_365_days"], 3)
        self.assertEqual(result["active_months"], 4)
        self.assertGreaterEqual(result["longest_gap_days"], 300)
        self.assertEqual(result["days_since_last_commit"], 0)

    def test_monorepo_signals_and_negative(self):
        cases = [
            ({"package.json": json.dumps({"workspaces": ["packages/*"]})}, "npm"),
            ({"pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n"}, "pnpm"),
            ({"lerna.json": '{"packages":["packages/*"]}'}, "lerna"),
            ({"Cargo.toml": "[workspace]\nmembers = [\"crates/*\"]"}, "cargo"),
            ({"go.work": "go 1.22\n\nuse ./a\n"}, "go.work"),
        ]
        for contents, _ in cases:
            structure = {"files": [{"path": name} for name in contents]}
            self.assertTrue(detect_monorepo(structure, contents)["is_monorepo"])
        self.assertFalse(detect_monorepo({"files": [{"path": "package.json"}]}, {"package.json": '{"name":"app"}'} )["is_monorepo"])

    def test_ci_cadence_archive_and_hardening_checks(self):
        evidence = {"repository": {"archived": True, "pushed_at": "2000-01-01T00:00:00Z"}, "structure": {"files": [], "source_files": 0}, "workflows": [".github/workflows/ci.yml"], "file_contents": {".github/workflows/ci.yml": "permissions:\n  contents: read\nuses: actions/checkout@v4"}, "repository_flags": {"has_ci": True}}
        runs = [{"status": "completed", "conclusion": "success", "updated_at": f"2026-10-0{i}T00:00:00Z"} for i in (1, 2, 3)]
        health = analyze_engineering_health(evidence, [{"commit": {"author": {"name": "a", "date": "2000-01-01T00:00:00Z"}}}], [{"login": "a", "contributions": 1}], runs)
        checks = {c["name"]: c["status"] for cat in health["categories"].values() for c in cat["checks"]}
        self.assertEqual(checks["CI passing (recent runs)"], "PASS")
        self.assertEqual(checks["Workflow hardening"], "PARTIAL")
        self.assertEqual(checks["Commit cadence consistency"], "N/A")
        self.assertEqual(checks["Recent repository activity"], "N/A")
        self.assertEqual(checks["Contributor concentration / bus factor"], "N/A")
        self.assertEqual([health["categories"][k]["max_score"] for k in ("code_structure", "testing_reliability", "documentation", "security_dependencies", "maintenance", "collaboration")], [25, 20, 15, 15, 15, 10])
        na = analyze_engineering_health(evidence, [], [], None)
        ci_check = next(c for c in na["categories"]["testing_reliability"]["checks"] if c["name"] == "CI passing (recent runs)")
        self.assertEqual(ci_check["status"], "N/A")
        self.assertEqual(_ci_status([{"status": "completed", "conclusion": "success"}] * 3, True), "PASS")
        self.assertEqual(_ci_status([{"status": "completed", "conclusion": "success"}, {"status": "completed", "conclusion": "failure"}, {"status": "completed", "conclusion": "failure"}], True), "NOT_DETECTED")
        self.assertEqual(_ci_status([{"status": "completed", "conclusion": "success"}, {"status": "completed", "conclusion": "success"}, {"status": "completed", "conclusion": "failure"}], True), "PARTIAL")

    def test_workflow_hardening_pass_and_na(self):
        workflow = {".github/workflows/ci.yml": "permissions:\n  contents: read\nsteps:\n  - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567"}
        health = analyze_engineering_health({"workflows": list(workflow), "file_contents": workflow})
        hardening = next(c for c in health["categories"]["security_dependencies"]["checks"] if c["name"] == "Workflow hardening")
        self.assertEqual(hardening["status"], "PASS")
        health = analyze_engineering_health({"workflows": [], "file_contents": {}})
        hardening = next(c for c in health["categories"]["security_dependencies"]["checks"] if c["name"] == "Workflow hardening")
        self.assertEqual(hardening["status"], "N/A")


class TestActionsCollection(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        cache.clear_raw()

    def test_runs_key_is_stable_and_case_normalized(self):
        self.assertEqual(cache.runs_key("Alice", "Repo"), cache.runs_key("alice", "repo"))

    async def test_actions_one_request_and_raw_cache_hit(self):
        from services import github_async_client as client_module
        calls = []
        async def mock_get(_self, url, **kwargs):
            calls.append((url, kwargs.get("params")))
            if url.endswith("/actions/runs"):
                return _response({"workflow_runs": [{"status": "completed", "conclusion": "success"}]})
            if "/git/trees/" in url: return _response({"tree": [], "truncated": False})
            if "/commits" in url or "/contributors" in url: return _response([])
            return _response({"default_branch": "main", "name": "repo"})
        with patch.object(client_module, "GITHUB_TOKEN", "token"), patch("httpx.AsyncClient.get", mock_get):
            first = await client_module._collect_evidence_async("alice", "repo")
            second = await client_module._collect_evidence_async("ALICE", "REPO")
        self.assertEqual(first["_workflow_runs"][0]["conclusion"], "success")
        self.assertEqual(second["_workflow_runs"], first["_workflow_runs"])
        action_calls = [(u, p) for u, p in calls if u.endswith("/actions/runs")]
        self.assertEqual(len(action_calls), 1)
        self.assertEqual(action_calls[0][1], {"per_page": 20})

    async def test_actions_403_classification_and_404(self):
        from services.github_async_client import _async_get
        client = MagicMock()
        ordinary = _response({}, 403)
        client.get = AsyncMock(return_value=ordinary)
        self.assertIsNone(await _async_get(client, "/actions/runs", optional=True))
        limited = _response({}, 403, {"X-RateLimit-Remaining": "0"})
        client.get = AsyncMock(return_value=limited)
        with self.assertRaises(RuntimeError):
            await _async_get(client, "/actions/runs", optional=True)
        missing = _response({}, 404)
        client.get = AsyncMock(return_value=missing)
        self.assertIsNone(await _async_get(client, "/actions/runs", optional=True))
        limited_429 = _response({}, 429)
        client.get = AsyncMock(return_value=limited_429)
        with self.assertRaises(RuntimeError):
            await _async_get(client, "/actions/runs", optional=True)


class TestPhase3ApiContract(unittest.TestCase):
    def test_existing_analytics_fields_preserved_and_runs_private(self):
        from app import app
        from unittest.mock import patch as mock_patch
        import cache as app_cache
        app_cache.clear_analysis()
        evidence = {
            "repository": {"name": "repo", "full_name": "alice/repo"},
            "structure": {}, "important_files": {}, "workflows": [],
            "repository_flags": {}, "file_contents": {},
            "_commits": [], "_contributors": [],
            "_workflow_runs": [{"status": "completed", "conclusion": "success"}],
        }
        with mock_patch("app.collect_evidence", return_value=evidence):
            response = app.test_client().get("/api/github/repository/alice/repo/analytics")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(set(payload) >= {"repository", "health", "activity", "evidence"}, True)
        self.assertNotIn("_workflow_runs", payload)
        self.assertIn("commits", payload["activity"])
        self.assertIn("contributors", payload["activity"])
def _response(payload, status=200, headers=None):
    response = MagicMock()
    response.status_code = status
    response.headers = headers or {}
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


if __name__ == "__main__":
    unittest.main()

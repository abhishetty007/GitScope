import os
import sys
import unittest
from unittest.mock import patch
from uuid import UUID

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from runtime_config import cors_origins, debug_enabled, validate_runtime_config


class TestProductionRuntimeConfig(unittest.TestCase):
    def test_local_cors_defaults_are_preserved_and_production_defaults_empty(self):
        self.assertEqual(
            cors_origins({}),
            ["http://localhost:3000", "http://127.0.0.1:3000"],
        )
        self.assertEqual(cors_origins({"GITSCOPE_ENV": "production"}), [])
        self.assertEqual(
            cors_origins({"GITSCOPE_CORS_ORIGINS": ""}),
            [],
        )

    def test_production_rejects_cors_and_debug_settings_by_name_only(self):
        with self.assertRaisesRegex(RuntimeError, "GITSCOPE_CORS_ORIGINS"):
            validate_runtime_config({
                "GITSCOPE_ENV": "production",
                "GITSCOPE_CORS_ORIGINS": "https://attacker.example",
            })
        with self.assertRaisesRegex(RuntimeError, "FLASK_DEBUG"):
            validate_runtime_config({
                "GITSCOPE_ENV": "production",
                "FLASK_DEBUG": "1",
                "GITSCOPE_CORS_ORIGINS": "",
            })
        validate_runtime_config({"FLASK_DEBUG": "1"})

    def test_debug_is_enabled_for_local_direct_run_and_disabled_in_production(self):
        self.assertTrue(debug_enabled({}))
        self.assertFalse(debug_enabled({"FLASK_DEBUG": "0"}))
        self.assertFalse(debug_enabled({"GITSCOPE_ENV": "production"}))


class TestFlaskSafeBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app
        cls.app = app
        cls.app.config.update(TESTING=True)

    def setUp(self):
        self.client = self.app.test_client()

    def test_unexpected_error_is_sanitized_and_request_id_is_server_generated(self):
        secret = "ghp_security_test_secret"
        internal_detail = "internal upstream failure"
        with patch.dict(os.environ, {"GITHUB_TOKEN": secret}):
            with patch("app.get_repository", side_effect=RuntimeError(f"{internal_detail}: {secret}")):
                with self.assertLogs("app", level="ERROR") as captured:
                    response = self.client.get(
                        "/api/github/repository/alice/repo/identity",
                        headers={
                            "X-Request-ID": "forged-request-id",
                            "Authorization": "Bearer auth-header-secret",
                            "Cookie": "session=cookie-secret",
                        },
                        data="request-body-secret",
                    )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "Internal server error"})
        request_id = response.headers["X-Request-ID"]
        UUID(request_id)
        self.assertNotEqual(request_id, "forged-request-id")
        logs = "\n".join(captured.output)
        self.assertIn(request_id, logs)
        self.assertIn("RuntimeError", logs)
        self.assertNotIn(internal_detail, logs)
        self.assertNotIn(secret, logs)
        self.assertNotIn("auth-header-secret", logs)
        self.assertNotIn("cookie-secret", logs)
        self.assertNotIn("request-body-secret", logs)

    def test_global_handler_sanitizes_unhandled_errors_and_preserves_http_exceptions(self):
        from flask import Flask
        from werkzeug.exceptions import NotFound
        from app import (
            _finish_request,
            _handle_unexpected_exception,
            _start_request_context,
        )

        sentinel = "global-handler-" + "internal-sentinel"

        def raise_unhandled():
            raise RuntimeError(sentinel)

        def raise_not_found():
            raise NotFound(description="The test resource is missing")

        test_app = Flask("isolated_security_boundary_test")
        test_app.config.update(TESTING=True)
        test_app.before_request(_start_request_context)
        test_app.after_request(_finish_request)
        test_app.register_error_handler(Exception, _handle_unexpected_exception)
        test_app.add_url_rule(
            "/__test/unhandled",
            endpoint="security_test_unhandled_exception",
            view_func=raise_unhandled,
        )
        test_app.add_url_rule(
            "/__test/not-found",
            endpoint="security_test_http_exception",
            view_func=raise_not_found,
        )
        client = test_app.test_client()

        with self.assertLogs("app", level="ERROR") as captured:
            response = client.get("/__test/unhandled")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "Internal server error"})
        self.assertNotIn(sentinel, response.get_data(as_text=True))
        request_id = response.headers["X-Request-ID"]
        UUID(request_id)
        logs = "\n".join(captured.output)
        self.assertIn(request_id, logs)
        self.assertIn("RuntimeError", logs)
        self.assertNotIn(sentinel, logs)

        not_found = client.get("/__test/not-found")
        self.assertEqual(not_found.status_code, 404)
        self.assertIn("The test resource is missing", not_found.get_data(as_text=True))
        self.assertNotEqual(not_found.get_json(silent=True), {"error": "Internal server error"})
        UUID(not_found.headers["X-Request-ID"])

    def test_not_found_contract_is_preserved_with_request_id_header(self):
        with patch("app.get_repository", return_value=None):
            response = self.client.get(
                "/api/github/repository/alice/missing/identity"
            )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "Repository not found"})
        UUID(response.headers["X-Request-ID"])

    def test_rate_limit_status_and_json_shape_are_preserved_without_details(self):
        internal_detail = "https://api.github.com/repos/alice/repo?token=upstream-secret"
        with patch("app.get_repository", side_effect=RuntimeError(internal_detail)):
            with self.assertLogs("app", level="WARNING") as captured:
                response = self.client.get(
                    "/api/github/repository/alice/repo/analytics"
                )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(
            response.get_json(),
            {"error": "GitHub rate limit exceeded. Try again later."},
        )
        self.assertNotIn("upstream-secret", response.get_data(as_text=True))
        self.assertNotIn("?token=upstream-secret", "\n".join(captured.output))
        UUID(response.headers["X-Request-ID"])

    def test_success_payload_is_unchanged_and_has_request_id_header(self):
        user = {"login": "alice", "name": "Alice", "public_repos": 3}
        with patch("app.get_user", return_value=user):
            response = self.client.get("/api/github/user/alice")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "login": "alice",
            "name": "Alice",
            "avatar_url": None,
            "bio": None,
            "public_repos": 3,
            "followers": None,
            "following": None,
            "html_url": None,
        })
        UUID(response.headers["X-Request-ID"])


if __name__ == "__main__":
    unittest.main()

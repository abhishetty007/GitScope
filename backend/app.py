from flask import Flask, g, jsonify, request
import logging
import os
import re
import sys
import threading
import time
import traceback
import uuid
from concurrent.futures import TimeoutError as FutureTimeoutError

from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from services.github_service import (
    get_user,
    get_user_repositories,
    get_repository,
    get_repository_commits,
    get_repository_contributors,
    get_repository_evidence,
    _MAX_ANALYSIS_SECONDS,
)

from services.github_async_client import collect_evidence
from github_errors import GitHubRateLimitExceeded, GitHubUpstreamBudgetExceeded

from services.analytics_service import (
    analyze_repositories,
    analyze_contributors,
    analyze_commits,
    analyze_engineering_health
)

import cache as _cache
from runtime_config import bounded_integer, cors_origins, debug_enabled, validate_runtime_config
from rate_limit import (
    RateLimitStoreUnavailable,
    get_default_rate_limiter,
)
from request_dedupe import coalesce as coalesce_inflight


validate_runtime_config()
app = Flask(__name__)

_GITHUB_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9_.\-\[\]]+")


def _valid_github_identifier(value, maximum_length):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= maximum_length
        and value not in {".", ".."}
        and _GITHUB_IDENTIFIER_PATTERN.fullmatch(value) is not None
    )

_cors_origins = cors_origins()
if _cors_origins:
    CORS(app, resources={r"/api/*": {"origins": _cors_origins}})

_rate_limiter = None
_rate_limiter_lock = threading.Lock()
_RATE_LIMIT_POLICIES = {
    # Service-wide requests per fixed minute window. These calls run server-side
    # on Vercel, so Render cannot safely infer the browser client IP.
    "repository_evidence": 10,
    "user_analytics": 30,
    "github_metadata": 60,
}


def _get_rate_limiter():
    global _rate_limiter
    if _rate_limiter is None:
        with _rate_limiter_lock:
            if _rate_limiter is None:
                _rate_limiter = get_default_rate_limiter()
    return _rate_limiter


def _public_rate_limit(bucket):
    global_limit = _RATE_LIMIT_POLICIES[bucket]
    if bucket == "github_metadata":
        global_limit = bounded_integer(
            os.environ, "GITSCOPE_GITHUB_METADATA_GLOBAL_LIMIT_PER_MINUTE", global_limit, 1, 100000
        )
    try:
        limiter = _get_rate_limiter()
        allowed, retry_after = limiter.allow(
            bucket,
            global_limit=global_limit,
        )
    except Exception as error:
        # A failed limiter must never turn expensive upstream requests into
        # unlimited work. Keep database details out of the response and logs.
        app.logger.error("shared_rate_limit_unavailable exception_type=%s", type(error).__name__)
        response = jsonify({"error": "Service temporarily unavailable. Try again shortly."})
        response.status_code = 503
        response.headers["Retry-After"] = "5"
        return response
    if allowed:
        return None
    response = jsonify({"error": "Too many GitHub requests. Try again later."})
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


def _log_exception(error, level=logging.ERROR):
    request_id = getattr(g, "request_id", "unavailable")
    # Keep actionable frames and exception type, but never format arbitrary
    # exception text, which can contain upstream response or request data.
    frames = "".join(traceback.format_list(traceback.extract_tb(error.__traceback__)))
    app.logger.log(
        level,
        "request_failure request_id=%s exception_type=%s stack=%s",
        request_id,
        type(error).__name__,
        frames,
    )


def _internal_server_error(error=None):
    if error is None:
        error = sys.exc_info()[1]
    if isinstance(error, GitHubRateLimitExceeded):
        response = jsonify({"error": "GitHub rate limit exceeded. Try again later."})
        response.status_code = 429
        response.headers["Retry-After"] = str(error.retry_after)
        return response
    if isinstance(error, GitHubUpstreamBudgetExceeded):
        response = jsonify({"error": "GitHub request budget temporarily exhausted. Try again later."})
        response.status_code = 429
        response.headers["Retry-After"] = str(error.retry_after)
        return response
    if isinstance(error, RateLimitStoreUnavailable):
        response = jsonify({"error": "Service temporarily unavailable. Try again shortly."})
        response.status_code = 503
        response.headers["Retry-After"] = "5"
        return response
    if error is not None:
        _log_exception(error)
    return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(Exception)
def _handle_unexpected_exception(error):
    if isinstance(error, HTTPException):
        return error
    return _internal_server_error(error)


@app.before_request
def _start_request_context():
    g.request_id = str(uuid.uuid4())
    g.request_started_at = time.perf_counter()


@app.before_request
def _validate_github_path_parameters():
    if not (request.endpoint or "").startswith("github_"):
        return None

    parameters = request.view_args or {}
    username = parameters.get("username")
    owner = parameters.get("owner")
    repository = parameters.get("repository")
    if (
        (username is not None and not _valid_github_identifier(username, 39))
        or (owner is not None and not _valid_github_identifier(owner, 39))
        or (repository is not None and not _valid_github_identifier(repository, 100))
    ):
        return jsonify({"error": "Invalid GitHub target"}), 400
    return None


@app.after_request
def _finish_request(response):
    request_id = getattr(g, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id
        duration_ms = (time.perf_counter() - g.request_started_at) * 1000
        route = request.url_rule.rule if request.url_rule else "unmatched"
        app.logger.info(
            "request_complete request_id=%s method=%s route=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            route,
            response.status_code,
            duration_ms,
        )
    return response


# =========================================================
# Basic routes
# =========================================================

@app.route("/")
def home():
    return {
        "message": "GitScope API is running"
    }


@app.route("/api/health")
def health():
    return {
        "status": "ok"
    }


# =========================================================
# GitHub user
# =========================================================

@app.route("/api/github/user/<username>")
def github_user(username):
    limited = _public_rate_limit("github_metadata")
    if limited:
        return limited
    try:
        user = get_user(username)

        if user is None:
            return jsonify({
                "error": "GitHub user not found"
            }), 404

        return jsonify({
            "login": user.get("login"),
            "name": user.get("name"),
            "avatar_url": user.get("avatar_url"),
            "bio": user.get("bio"),
            "public_repos": user.get("public_repos"),
            "followers": user.get("followers"),
            "following": user.get("following"),
            "html_url": user.get("html_url")
        })

    except Exception:
        return _internal_server_error()


# =========================================================
# User repositories
# =========================================================

@app.route("/api/github/user/<username>/repositories")
def github_repositories(username):
    limited = _public_rate_limit("github_metadata")
    if limited:
        return limited
    try:
        repositories = get_user_repositories(
            username
        )

        if repositories is None:
            return jsonify({
                "error": "GitHub user not found"
            }), 404

        # User-facing analytics pages are public. Do not reveal private
        # repositories visible only through the server's GitHub token.
        repositories = [
            repo for repo in repositories
            if not repo.get("private", False)
        ]

        result = []

        for repo in repositories:
            result.append({
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "description": repo.get("description"),
                "language": repo.get("language"),
                "topics": repo.get(
                    "topics",
                    []
                ),
                "stars": repo.get(
                    "stargazers_count"
                ),
                "forks": repo.get(
                    "forks_count"
                ),
                "open_issues": repo.get(
                    "open_issues_count"
                ),
                "updated_at": repo.get(
                    "updated_at"
                ),
                "html_url": repo.get(
                    "html_url"
                )
            })

        return jsonify(result)

    except Exception:
        return _internal_server_error()


# =========================================================
# User analytics
# =========================================================

@app.route("/api/github/user/<username>/analytics")
def github_analytics(username):
    limited = _public_rate_limit("user_analytics")
    if limited:
        return limited
    try:
        repositories = get_user_repositories(
            username
        )

        if repositories is None:
            return jsonify({
                "error": "GitHub user not found"
            }), 404

        repositories = [
            repo for repo in repositories
            if not repo.get("private", False)
        ]

        analytics = analyze_repositories(
            repositories
        )

        return jsonify(analytics)

    except Exception:
        return _internal_server_error()


# =========================================================
# Repository details
# =========================================================

@app.route(
    "/api/github/repository/<owner>/<repository>"
)
def github_repository(owner, repository):
    limited = _public_rate_limit("github_metadata")
    if limited:
        return limited
    try:
        repo = get_repository(
            owner,
            repository
        )

        if repo is None or repo.get("private", False):
            return jsonify({
                "error": "Repository not found"
            }), 404

        return jsonify({
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "description": repo.get("description"),
            "language": repo.get("language"),
            "topics": repo.get(
                "topics",
                []
            ),
            "stars": repo.get(
                "stargazers_count"
            ),
            "forks": repo.get(
                "forks_count"
            ),
            "open_issues": repo.get(
                "open_issues_count"
            ),
            "watchers": repo.get(
                "watchers_count"
            ),
            "created_at": repo.get(
                "created_at"
            ),
            "updated_at": repo.get(
                "updated_at"
            ),
            "default_branch": repo.get(
                "default_branch"
            ),
            "html_url": repo.get(
                "html_url"
            )
        })

    except Exception:
        return _internal_server_error()


@app.route("/api/github/repository/<owner>/<repository>/identity")
def github_repository_identity(owner, repository):
    """Return the stable public GitHub repository identity for Next.js persistence."""
    limited = _public_rate_limit("github_metadata")
    if limited:
        return limited
    try:
        repo = get_repository(owner, repository)
        if repo is None or repo.get("private", False):
            return jsonify({"error": "Repository not found"}), 404

        repo_id = repo.get("id")
        if repo_id is None:
            return jsonify({"error": "Repository not found"}), 404

        return jsonify({
            "provider": "github",
            "provider_repo_id": str(repo_id),
            "owner_login": repo.get("owner", {}).get("login") or owner,
            "name": repo.get("name") or repository,
            "visibility": "public",
            "html_url": repo.get("html_url"),
        })
    except Exception:
        return _internal_server_error()


# =========================================================
# Repository commits
# =========================================================

@app.route(
    "/api/github/repository/<owner>/<repository>/commits"
)
def github_commits(owner, repository):
    limited = _public_rate_limit("github_metadata")
    if limited:
        return limited
    try:
        repo = get_repository(owner, repository)
        if repo is None or repo.get("private", False):
            return jsonify({"error": "Repository not found"}), 404

        commits = get_repository_commits(
            owner,
            repository
        )

        if commits is None:
            return jsonify({
                "error": "Repository not found"
            }), 404

        result = []

        for commit in commits:
            commit_data = commit.get(
                "commit",
                {}
            )

            author_data = commit_data.get(
                "author",
                {}
            )

            result.append({
                "sha": commit.get(
                    "sha"
                ),
                "message": commit_data.get(
                    "message"
                ),
                "author": author_data.get(
                    "name"
                ),
                "date": author_data.get(
                    "date"
                ),
                "url": commit.get(
                    "html_url"
                )
            })

        return jsonify(result)

    except Exception:
        return _internal_server_error()


# =========================================================
# Repository contributors
# =========================================================

@app.route(
    "/api/github/repository/<owner>/<repository>/contributors"
)
def github_contributors(owner, repository):
    limited = _public_rate_limit("github_metadata")
    if limited:
        return limited
    try:
        repo = get_repository(owner, repository)
        if repo is None or repo.get("private", False):
            return jsonify({"error": "Repository not found"}), 404

        contributors = get_repository_contributors(
            owner,
            repository
        )

        if contributors is None:
            return jsonify({
                "error": "Repository not found"
            }), 404

        return jsonify(
            analyze_contributors(
                contributors
            )
        )

    except Exception:
        return _internal_server_error()


# =========================================================
# NEW: Repository evidence
# =========================================================

@app.route(
    "/api/github/repository/<owner>/<repository>/evidence"
)
def github_repository_evidence(
    owner,
    repository
):
    limited = _public_rate_limit("repository_evidence")
    if limited:
        return limited
    try:
        evidence = get_repository_evidence(
            owner,
            repository
        )

        if evidence is None:
            return jsonify({
                "error": "Repository not found"
            }), 404

        return jsonify(evidence)

    except Exception:
        return _internal_server_error()


# =========================================================
# NEW: Repository Engineering Health
# =========================================================

@app.route(
    "/api/github/repository/<owner>/<repository>/analytics"
)
def github_repository_analytics(
    owner,
    repository
):
    try:
        result = coalesce_inflight(
            ("repository_analysis", owner.lower(), repository.lower()),
            lambda: _github_repository_analytics_impl(owner, repository),
            timeout_seconds=_MAX_ANALYSIS_SECONDS + 5,
        )
    except FutureTimeoutError:
        response = jsonify({"error": "Repository analysis is still in progress. Try again shortly."})
        response.status_code = 503
        response.headers["Retry-After"] = "5"
        return response

    # Give each Flask request its own response object so request IDs and other
    # after_request headers cannot race between duplicate callers.
    shared_response = app.make_response(result)
    response = app.response_class(
        shared_response.get_data(),
        status=shared_response.status_code,
        content_type=shared_response.content_type,
    )
    for header, value in shared_response.headers:
        if header.lower() not in {"content-type", "content-length", "x-request-id"}:
            response.headers.add(header, value)
    return response


def _github_repository_analytics_impl(owner, repository):
    analysis_started = time.monotonic()
    try:
        # Always confirm current visibility before serving a cached public
        # analysis. Refresh the shared metadata entry so a cache miss can
        # reuse this request's GitHub response in the async collector.
        repo = get_repository(owner, repository)
        if repo is None or repo.get("private", False):
            return jsonify({
                "error": "Repository not found"
            }), 404

        _cache.set_raw(_cache.repo_key(owner, repository), repo)

        # -------------------------------------------------
        # Outer cache — serve a complete cached response
        # after confirming the repository is still public.
        # -------------------------------------------------

        cached_result = _cache.get_analysis(owner, repository)
        if cached_result is not None:
            return jsonify(cached_result)

        # -------------------------------------------------
        # Async concurrent evidence collection.
        #
        # collect_evidence() runs:
        #   repo metadata (seq)
        #     ↓
        #   repository tree (seq)
        #     ↓
        #   file contents + commits + contributors (concurrent)
        #
        # It also performs inner-layer (raw) caching so that
        # individual GitHub API payloads are reused on repeat
        # requests within the TTL window.
        # -------------------------------------------------

        remaining_seconds = _MAX_ANALYSIS_SECONDS - (time.monotonic() - analysis_started)
        if remaining_seconds <= 0:
            raise TimeoutError("GitHub analysis deadline exceeded")
        evidence = collect_evidence(owner, repository, timeout_seconds=remaining_seconds)

        if evidence is None:
            return jsonify({
                "error": "Repository not found"
            }), 404

        # Pull out the private keys that the collector already
        # fetched concurrently alongside file contents.
        commits = evidence.pop("_commits", []) or []
        commits_truncated = bool(evidence.pop("_commits_truncated", False))
        contributors = evidence.pop("_contributors", []) or []
        workflow_runs = evidence.pop("_workflow_runs", None)

        evidence["history_available"] = bool(commits)

        # -------------------------------------------------
        # Deterministic analysis — pure Python, ~0.4 ms
        # (scoring logic is unchanged)
        # -------------------------------------------------

        health = analyze_engineering_health(
            evidence,
            commits,
            contributors,
            workflow_runs,
        )

        commit_analysis = analyze_commits(commits)
        contributor_analysis = analyze_contributors(contributors, commits)

        # -------------------------------------------------
        # Build response — identical contract as before
        # -------------------------------------------------

        repo = evidence["repository"]

        result = {
            "repository": {
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "description": repo.get("description"),
                "language": repo.get("language"),
                "topics": repo.get("topics", []),
                "stars": repo.get("stars"),
                "forks": repo.get("forks"),
                "open_issues": repo.get("open_issues"),
                "watchers": repo.get("watchers"),
                "created_at": repo.get("created_at"),
                "updated_at": repo.get("updated_at"),
                "default_branch": repo.get("default_branch"),
                "html_url": repo.get("html_url"),
            },

            "health": health,

            "activity": {
                "commits": commit_analysis,
                "contributors": contributor_analysis,
            },

            "evidence": {
                "structure": evidence.get("structure", {}),
                "important_files": evidence.get("important_files", {}),
                "workflows": evidence.get("workflows", []),
                "repository_flags": evidence.get("repository_flags", {}),
                "commit_history_truncated": commits_truncated,
            },
        }

        # Store the complete result in the outer cache (1-hour TTL).
        _cache.set_analysis(owner, repository, result)

        return jsonify(result)

    except GitHubRateLimitExceeded as error:
        # Preserve the upstream rate limit distinctly from the local 429.
        return _internal_server_error(error)

    except Exception:
        return _internal_server_error()


# =========================================================
# Run server
# =========================================================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=debug_enabled(),
    )

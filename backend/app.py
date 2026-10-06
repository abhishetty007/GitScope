from flask import Flask, jsonify
import os

from flask_cors import CORS

from services.github_service import (
    get_user,
    get_user_repositories,
    get_repository,
    get_repository_commits,
    get_repository_contributors,
    get_repository_evidence
)

from services.github_async_client import collect_evidence

from services.analytics_service import (
    analyze_repositories,
    analyze_contributors,
    analyze_commits,
    analyze_engineering_health
)

import cache as _cache


app = Flask(__name__)

_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "GITSCOPE_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
if _cors_origins:
    CORS(app, resources={r"/api/*": {"origins": _cors_origins}})


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

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# User repositories
# =========================================================

@app.route("/api/github/user/<username>/repositories")
def github_repositories(username):
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

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# User analytics
# =========================================================

@app.route("/api/github/user/<username>/analytics")
def github_analytics(username):
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

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# Repository details
# =========================================================

@app.route(
    "/api/github/repository/<owner>/<repository>"
)
def github_repository(owner, repository):
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

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


@app.route("/api/github/repository/<owner>/<repository>/identity")
def github_repository_identity(owner, repository):
    """Return the stable public GitHub repository identity for Next.js persistence."""
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
    except Exception as error:
        return jsonify({"error": str(error)}), 500


# =========================================================
# Repository commits
# =========================================================

@app.route(
    "/api/github/repository/<owner>/<repository>/commits"
)
def github_commits(owner, repository):
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

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# Repository contributors
# =========================================================

@app.route(
    "/api/github/repository/<owner>/<repository>/contributors"
)
def github_contributors(owner, repository):
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

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


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

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


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

        evidence = collect_evidence(owner, repository)

        if evidence is None:
            return jsonify({
                "error": "Repository not found"
            }), 404

        # Pull out the private keys that the collector already
        # fetched concurrently alongside file contents.
        commits = evidence.pop("_commits", []) or []
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
            },
        }

        # Store the complete result in the outer cache (1-hour TTL).
        _cache.set_analysis(owner, repository, result)

        return jsonify(result)

    except RuntimeError as error:
        # Rate-limit errors from the async client
        return jsonify({
            "error": str(error)
        }), 429

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# Run server
# =========================================================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )

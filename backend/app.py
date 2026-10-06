from flask import Flask, jsonify
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

CORS(app)


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

        if repo is None:
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


# =========================================================
# Repository commits
# =========================================================

@app.route(
    "/api/github/repository/<owner>/<repository>/commits"
)
def github_commits(owner, repository):
    try:
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
        # -------------------------------------------------
        # Outer cache — serve a complete cached response
        # immediately if available.
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

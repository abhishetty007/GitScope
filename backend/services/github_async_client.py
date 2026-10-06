"""
github_async_client.py — Async concurrent GitHub evidence collector.

Execution order is:

    1. repo metadata          (sequential — needed for default_branch)
         ↓
    2. repository tree        (sequential — needed for file list)
         ↓
    3. ┌──────────────────────────────────────┐
       │ file contents  (concurrent)          │
       │ commits        (concurrent)          │
       │ contributors   (concurrent)          │
       └──────────────────────────────────────┘

This matches the dependency graph identified in Phase 2A audit.

Only file contents, commits, contributors and workflow runs can be
parallelised because they depend on the tree/repo metadata but not
on each other.

Session reuse:
- A single httpx.AsyncClient is used for all requests within one
  evidence collection, eliminating per-request TCP connection setup.

Error handling:
- Individual file fetch failures are logged and skipped (partial
  degradation, not total failure).
- GitHub 404 returns None, consistent with github_service.py.
- Only genuine rate exhaustion raises: a 429, or a 403 carrying
  X-RateLimit-Remaining: 0 or Retry-After. Ordinary 403 responses
  (missing scope, Actions disabled, blocked content) are not rate
  limits and must never be surfaced as such.
- Optional endpoints (workflow runs) degrade to empty evidence
  instead of failing the whole collection.
- Timeouts raise httpx.TimeoutException which propagates.

Credentials:
- GITHUB_TOKEN is loaded from the same .env as github_service.py.
- The token is injected as a Bearer header and never logged or
  returned in any response.
"""

import asyncio
import base64
import os
import sys

import httpx
from dotenv import load_dotenv

# Ensure the backend root is importable when tests run from any cwd
_BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

load_dotenv(os.path.join(_BACKEND_DIR, ".env"))

from services.github_service import (  # noqa: E402
    IMPORTANT_FILES,
    _classify_path,
    _is_test_path,
    _is_source_file,
)
import cache as _cache  # noqa: E402


GITHUB_API_URL = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Per-request timeout (seconds). Generous but bounded.
_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0)

# Maximum concurrent file-content fetches.
# Keeps us well under GitHub's secondary rate-limit heuristics.
_MAX_FILE_CONCURRENCY = 8

# Workflow runs are deliberately a single bounded page. Long paginated
# run history is not required for the CI signals GitScope scores.
_WORKFLOW_RUN_PAGE_SIZE = 20


def _build_headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def _is_rate_limited(response: httpx.Response) -> bool:
    """
    True only when the response represents GitHub rate exhaustion.

    GitHub uses 403 for several unrelated conditions — a token missing
    a scope, Actions disabled on the repository, blocked content. The
    old check treated every 403 as a rate limit, which turned ordinary
    permission failures into spurious 429s. The decision is therefore
    driven by the headers GitHub sets for primary and secondary limits.
    """

    if response.status_code == 429:
        return True

    if response.status_code != 403:
        return False

    if response.headers.get("X-RateLimit-Remaining") == "0":
        return True

    # Secondary rate limits are reported with a Retry-After hint and
    # may leave the primary remaining count untouched.
    if response.headers.get("Retry-After"):
        return True

    return False


def _check_rate_limit(response: httpx.Response, url: str) -> None:
    if not _is_rate_limited(response):
        return

    remaining = response.headers.get("X-RateLimit-Remaining", "?")
    reset = response.headers.get("X-RateLimit-Reset", "?")
    raise RuntimeError(
        f"GitHub rate limit hit on {url}. "
        f"Remaining={remaining}, Reset={reset}"
    )


# -----------------------------------------------------------------
# Low-level async GET — returns parsed JSON or None on 404
# -----------------------------------------------------------------

async def _async_get(
    client: httpx.AsyncClient,
    endpoint: str,
    params: dict = None,
    optional: bool = False,
) -> dict | list | None:
    """
    Fetch and decode a GitHub endpoint.

    Returns None on 404. When ``optional`` is True any other HTTP
    error also returns None, so callers can treat a restricted or
    unavailable endpoint as absent evidence rather than failing the
    entire evidence collection.
    """

    url = f"{GITHUB_API_URL}{endpoint}"
    response = await client.get(url, params=params or {})
    _check_rate_limit(response, url)

    if response.status_code == 404:
        return None

    if optional and response.status_code >= 400:
        return None

    response.raise_for_status()
    return response.json()


# -----------------------------------------------------------------
# Paginated async GET — fetches all pages into a flat list
# -----------------------------------------------------------------

async def _async_get_all_pages(
    client: httpx.AsyncClient,
    endpoint: str,
    per_page: int = 100,
) -> list | None:
    results = []
    page = 1
    while True:
        page_data = await _async_get(
            client,
            endpoint,
            params={"per_page": per_page, "page": page},
        )
        if page_data is None:
            return None
        if not page_data:
            break
        results.extend(page_data)
        if len(page_data) < per_page:
            break
        page += 1
    return results


# -----------------------------------------------------------------
# Single file fetch — returns decoded text or None
# -----------------------------------------------------------------

async def _fetch_file(
    client: httpx.AsyncClient,
    owner: str,
    repository: str,
    path: str,
    branch: str,
) -> tuple[str, str | None]:
    """
    Return (path, decoded_content_or_None).
    Never raises — individual file failures are silently skipped.
    """
    cache_key = _cache.file_key(owner, repository, path, branch)
    cached = _cache.get_raw(cache_key)
    if cached is not None:
        return path, cached

    try:
        data = await _async_get(
            client,
            f"/repos/{owner}/{repository}/contents/{path}",
            params={"ref": branch},
        )
    except Exception:
        return path, None

    if data is None or isinstance(data, list):
        return path, None

    raw_content = data.get("content")
    if not raw_content:
        return path, None

    try:
        decoded = base64.b64decode(raw_content).decode("utf-8", errors="replace")
    except Exception:
        return path, None

    # Cap at 50 000 chars — same limit as github_service.py
    result = decoded[:50000]
    _cache.set_raw(cache_key, result)
    return path, result


# -----------------------------------------------------------------
# Main async evidence collector
# -----------------------------------------------------------------

async def _collect_evidence_async(owner: str, repository: str) -> dict | None:
    """
    Collect all evidence for one repository using a single AsyncClient.

    Returns the same evidence dict shape as get_repository_evidence()
    in github_service.py, so it is a drop-in replacement.
    """
    headers = _build_headers()

    async with httpx.AsyncClient(
        headers=headers,
        timeout=_TIMEOUT,
        follow_redirects=True,
    ) as client:
        # ----------------------------------------------------------
        # Stage 1: repository metadata (sequential)
        # ----------------------------------------------------------
        repo_cache_key = _cache.repo_key(owner, repository)
        repo = _cache.get_raw(repo_cache_key)
        if repo is None:
            repo = await _async_get(client, f"/repos/{owner}/{repository}")
            if repo is None:
                return None
            _cache.set_raw(repo_cache_key, repo)

        default_branch = repo.get("default_branch", "main")

        # ----------------------------------------------------------
        # Stage 2: repository tree (sequential — needs branch)
        # ----------------------------------------------------------
        tree_cache_key = _cache.tree_key(owner, repository, default_branch)
        raw_tree = _cache.get_raw(tree_cache_key)
        if raw_tree is None:
            raw_tree = await _async_get(
                client,
                f"/repos/{owner}/{repository}/git/trees/{default_branch}",
                params={"recursive": "1"},
            )
            if raw_tree is None:
                raw_tree = {"tree": [], "truncated": False}
            _cache.set_raw(tree_cache_key, raw_tree)

        # Parse tree into categorised file list
        files = []
        directories = []
        for item in raw_tree.get("tree", []):
            path = item.get("path")
            if not path:
                continue
            if item.get("type") == "tree":
                directories.append(path)
            elif item.get("type") == "blob":
                files.append({
                    "path": path,
                    "size": item.get("size", 0),
                    "category": _classify_path(path),
                })

        file_paths = {f["path"] for f in files}
        lower_file_paths = {p.lower(): p for p in file_paths}

        # Detect important files (case-insensitive)
        detected_files: dict[str, str] = {}
        for important in IMPORTANT_FILES:
            exact = lower_file_paths.get(important.lower())
            if exact:
                detected_files[important] = exact

        workflow_files = [
            f["path"] for f in files
            if f["path"].lower().startswith(".github/workflows/")
            and f["path"].lower().endswith((".yml", ".yaml"))
        ]
        test_files = [f["path"] for f in files if f["category"] == "test"]
        source_files = [f["path"] for f in files if f["category"] == "source"]
        documentation_files = [f["path"] for f in files if f["category"] == "documentation"]

        # Files whose content we want to download
        files_to_read = set(detected_files.values()) | set(workflow_files)

        # ----------------------------------------------------------
        # Stage 3: concurrent fetches
        #   • file contents
        #   • commits
        #   • contributors
        # ----------------------------------------------------------
        semaphore = asyncio.Semaphore(_MAX_FILE_CONCURRENCY)

        async def bounded_fetch(path: str):
            async with semaphore:
                return await _fetch_file(
                    client, owner, repository, path, default_branch
                )

        commits_cache_key = _cache.commits_key(owner, repository)
        contributors_cache_key = _cache.contributors_key(owner, repository)
        runs_cache_key = _cache.runs_key(owner, repository)

        cached_commits = _cache.get_raw(commits_cache_key)
        cached_contributors = _cache.get_raw(contributors_cache_key)

        async def fetch_commits():
            if cached_commits is not None:
                return cached_commits
            result = await _async_get_all_pages(
                client,
                f"/repos/{owner}/{repository}/commits",
            )
            commits = result or []
            _cache.set_raw(commits_cache_key, commits)
            return commits

        async def fetch_contributors():
            if cached_contributors is not None:
                return cached_contributors
            result = await _async_get_all_pages(
                client,
                f"/repos/{owner}/{repository}/contributors",
            )
            contributors = result or []
            _cache.set_raw(contributors_cache_key, contributors)
            return contributors

        async def fetch_workflow_runs():
            """
            Newest workflow runs, one bounded page.

            Optional evidence: repositories with Actions disabled, or
            tokens lacking the actions scope, report an empty history
            rather than failing the whole collection. Run history is
            skipped entirely when no token is configured, because the
            unauthenticated quota is far too small to spend on it.
            """
            if not GITHUB_TOKEN:
                return []

            cached_runs = _cache.get_raw(runs_cache_key)
            if cached_runs is not None:
                return cached_runs

            data = await _async_get(
                client,
                f"/repos/{owner}/{repository}/actions/runs",
                params={"per_page": _WORKFLOW_RUN_PAGE_SIZE},
                optional=True,
            )

            runs = []
            if isinstance(data, dict):
                runs = data.get("workflow_runs") or []

            _cache.set_raw(runs_cache_key, runs)
            return runs

        # Launch all concurrent tasks at once
        file_tasks = [bounded_fetch(p) for p in files_to_read]
        all_tasks = file_tasks + [
            asyncio.ensure_future(fetch_commits()),
            asyncio.ensure_future(fetch_contributors()),
            asyncio.ensure_future(fetch_workflow_runs()),
        ]
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Separate file results from the repository-level tasks
        n_files = len(file_tasks)
        file_results = results[:n_files]
        commits_result = results[n_files]
        contributors_result = results[n_files + 1]
        workflow_runs_result = results[n_files + 2]

        # Preserve true Actions rate-limit failures so the existing API
        # handler can return 429. Other optional endpoint failures remain
        # unavailable evidence and do not fail repository analysis.
        if isinstance(workflow_runs_result, RuntimeError):
            raise workflow_runs_result

        # Build file_contents dict, skipping any failed fetches
        file_contents: dict[str, str] = {}
        for item in file_results:
            if isinstance(item, Exception):
                continue
            path, content = item
            if content is not None:
                file_contents[path] = content

        # Normalise commits/contributors (exceptions → empty list)
        commits = commits_result if isinstance(commits_result, list) else []
        contributors = contributors_result if isinstance(contributors_result, list) else []
        workflow_runs = (
            workflow_runs_result
            if isinstance(workflow_runs_result, list)
            else []
        )

    # ----------------------------------------------------------
    # Assemble evidence dict — identical shape to github_service.py
    # ----------------------------------------------------------
    evidence = {
        "repository": {
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "description": repo.get("description"),
            "language": repo.get("language"),
            "topics": repo.get("topics", []),
            "license": (repo.get("license") or {}).get("spdx_id"),
            "default_branch": default_branch,
            "created_at": repo.get("created_at"),
            "updated_at": repo.get("updated_at"),
            "pushed_at": repo.get("pushed_at"),
            "archived": repo.get("archived", False),
            "disabled": repo.get("disabled", False),
            "fork": repo.get("fork", False),
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "watchers": repo.get("watchers_count", 0),
            "size_kb": repo.get("size", 0),
            "html_url": repo.get("html_url"),
        },
        "structure": {
            "total_files": len(files),
            "total_directories": len(directories),
            "source_files": len(source_files),
            "test_files": len(test_files),
            "documentation_files": len(documentation_files),
            "workflow_files": len(workflow_files),
            "tree_truncated": raw_tree.get("truncated", False),
            "files": files,
        },
        "important_files": detected_files,
        "workflows": workflow_files,
        "file_contents": file_contents,
        "repository_flags": {
            "has_readme": any(
                k.lower().startswith("readme") for k in detected_files
            ),
            "has_license": any(
                k.lower() in {"license", "license.md", "licence", "licence.md"}
                for k in detected_files
            ),
            "has_contributing": any(
                k.lower().startswith("contributing") for k in detected_files
            ),
            "has_code_of_conduct": any(
                k.lower().startswith("code_of_conduct") for k in detected_files
            ),
            "has_security_policy": any(
                k.lower().startswith("security") for k in detected_files
            ),
            "has_changelog": any(
                k.lower().startswith("changelog") for k in detected_files
            ),
            "has_ci": len(workflow_files) > 0,
            "has_tests": len(test_files) > 0,
            "has_source_code": len(source_files) > 0,
            "has_docs": len(documentation_files) > 0,
        },
        # Include raw commits/contributors/runs so app.py can reuse
        # them without additional network calls.
        "_commits": commits,
        "_contributors": contributors,
        "_workflow_runs": workflow_runs,
    }

    return evidence


# -----------------------------------------------------------------
# Public sync wrapper — called from Flask (synchronous context)
# -----------------------------------------------------------------

def collect_evidence(owner: str, repository: str) -> dict | None:
    """
    Synchronous entry point for Flask route handlers.

    Runs the async collector on a dedicated event loop so it can be
    called from standard synchronous Flask routes.

    Returns the same evidence dict as get_repository_evidence() plus
    three private keys:
        _commits      — raw commits list (reused by app.py)
        _contributors — raw contributors list (reused by app.py)

    ``_workflow_runs`` holds the newest workflow runs, or an empty
    list when run history is unavailable (no token configured,
    Actions disabled, or the token lacking the actions scope).

    Returns None if the repository does not exist.
    """
    return asyncio.run(_collect_evidence_async(owner, repository))

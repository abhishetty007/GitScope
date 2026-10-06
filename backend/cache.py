"""
cache.py — Thread-safe in-memory TTL cache for GitScope.

Design decisions:
- Uses cachetools.TTLCache which is a bounded LRU+TTL cache.
- Wrapped in threading.Lock for thread safety (Flask dev server and
  production WSGI workers share memory within a process).
- Two separate cache tiers:
    analysis_cache  — completed repository analysis results (1 h TTL)
    raw_cache       — raw GitHub API payloads (15 min TTL)
- Keys are always fully-qualified strings to avoid collisions, e.g.
    "analysis:owner/repo"
    "raw:repo:owner/repo"
    "raw:tree:owner/repo:main"
    "raw:commits:owner/repo"
    "raw:contributors:owner/repo"
    "raw:file:owner/repo:path"
"""

import threading

from cachetools import TTLCache


# -----------------------------------------------------------------
# Cache configuration
# -----------------------------------------------------------------

# Completed analysis results: bounded to 256 entries, 1-hour TTL.
# A full analysis response is ~20–50 KB.
_ANALYSIS_MAX_SIZE = 256
_ANALYSIS_TTL = 3600  # seconds

# Raw GitHub API data: bounded to 512 entries, 15-minute TTL.
# Raw tree payloads can be large; keep TTL shorter so stale data
# does not accumulate between deploys.
_RAW_MAX_SIZE = 512
_RAW_TTL = 900  # seconds

_analysis_cache: TTLCache = TTLCache(
    maxsize=_ANALYSIS_MAX_SIZE,
    ttl=_ANALYSIS_TTL
)

_raw_cache: TTLCache = TTLCache(
    maxsize=_RAW_MAX_SIZE,
    ttl=_RAW_TTL
)

_analysis_lock = threading.Lock()
_raw_lock = threading.Lock()


# -----------------------------------------------------------------
# Key helpers
# -----------------------------------------------------------------

def _analysis_key(owner: str, repository: str) -> str:
    return f"analysis:{owner}/{repository}"


def _raw_key(*parts: str) -> str:
    return ":".join(parts)


# -----------------------------------------------------------------
# Analysis cache — outer layer (completed analysis results)
# -----------------------------------------------------------------

def get_analysis(owner: str, repository: str):
    """
    Return a cached completed analysis result, or None if absent / expired.
    """
    key = _analysis_key(owner, repository)
    with _analysis_lock:
        return _analysis_cache.get(key)


def set_analysis(owner: str, repository: str, value: dict) -> None:
    """
    Store a completed analysis result in the cache.
    """
    key = _analysis_key(owner, repository)
    with _analysis_lock:
        _analysis_cache[key] = value


def clear_analysis(owner: str = None, repository: str = None) -> None:
    """
    Clear one analysis entry (if owner+repository given) or the entire
    analysis cache (if called with no arguments).
    """
    with _analysis_lock:
        if owner and repository:
            key = _analysis_key(owner, repository)
            _analysis_cache.pop(key, None)
        else:
            _analysis_cache.clear()


# -----------------------------------------------------------------
# Raw cache — inner layer (individual GitHub API responses)
# -----------------------------------------------------------------

def get_raw(cache_key: str):
    """Return a raw-data cache entry, or None if absent / expired."""
    with _raw_lock:
        return _raw_cache.get(cache_key)


def set_raw(cache_key: str, value) -> None:
    """Store a raw-data cache entry."""
    with _raw_lock:
        _raw_cache[cache_key] = value


def clear_raw(cache_key: str = None) -> None:
    """
    Clear one raw entry (if cache_key given) or the entire raw cache.
    """
    with _raw_lock:
        if cache_key:
            _raw_cache.pop(cache_key, None)
        else:
            _raw_cache.clear()


# -----------------------------------------------------------------
# Convenience key builders for callers
# -----------------------------------------------------------------

def repo_key(owner: str, repository: str) -> str:
    return _raw_key("raw", "repo", f"{owner}/{repository}")


def tree_key(owner: str, repository: str, branch: str) -> str:
    return _raw_key("raw", "tree", f"{owner}/{repository}", branch)


def commits_key(owner: str, repository: str) -> str:
    return _raw_key("raw", "commits", f"{owner}/{repository}")


def contributors_key(owner: str, repository: str) -> str:
    return _raw_key("raw", "contributors", f"{owner}/{repository}")


def file_key(owner: str, repository: str, path: str, branch: str = "") -> str:
    return _raw_key("raw", "file", f"{owner}/{repository}", branch, path)


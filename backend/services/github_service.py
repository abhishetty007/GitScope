import os

import requests
from dotenv import load_dotenv


load_dotenv(
    os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        ".env"
    )
)


GITHUB_API_URL = "https://api.github.com"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


def github_get(endpoint, params=None):
    url = f"{GITHUB_API_URL}{endpoint}"

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=15
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    return response.json()


# ---------------------------------------------------------
# Basic repository/user data
# ---------------------------------------------------------

def get_user(username):
    return github_get(
        f"/users/{username}"
    )


def get_user_repositories(username):
    endpoint = f"/users/{username}/repos"

    repositories = []
    page = 1

    while True:
        params = {
            "per_page": 100,
            "page": page,
            "sort": "updated"
        }

        page_data = github_get(
            endpoint,
            params
        )

        if page_data is None:
            return None

        if not page_data:
            break

        repositories.extend(page_data)

        if len(page_data) < 100:
            break

        page += 1

    return repositories


def get_repository(owner, repository):
    return github_get(
        f"/repos/{owner}/{repository}"
    )


# ---------------------------------------------------------
# Commit / contributor data
# ---------------------------------------------------------

def get_repository_commits(owner, repository):
    endpoint = (
        f"/repos/{owner}/{repository}/commits"
    )

    commits = []
    page = 1

    while True:
        params = {
            "per_page": 100,
            "page": page
        }

        page_data = github_get(
            endpoint,
            params
        )

        if page_data is None:
            return None

        if not page_data:
            break

        commits.extend(page_data)

        if len(page_data) < 100:
            break

        page += 1

    return commits


def get_repository_contributors(owner, repository):
    endpoint = (
        f"/repos/{owner}/{repository}/contributors"
    )

    contributors = []
    page = 1

    while True:
        params = {
            "per_page": 100,
            "page": page
        }

        page_data = github_get(
            endpoint,
            params
        )

        if page_data is None:
            return None

        if not page_data:
            break

        contributors.extend(page_data)

        if len(page_data) < 100:
            break

        page += 1

    return contributors


# ---------------------------------------------------------
# Repository evidence collector
# ---------------------------------------------------------

IMPORTANT_FILES = {
    "README.md",
    "README",
    "README.txt",

    "LICENSE",
    "LICENSE.md",
    "LICENCE",
    "LICENCE.md",

    "CONTRIBUTING.md",
    "CONTRIBUTING",

    "CODE_OF_CONDUCT.md",
    "CODE_OF_CONDUCT",

    "SECURITY.md",
    "SECURITY",

    "CHANGELOG.md",
    "CHANGELOG",

    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",

    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "Pipfile",
    "Pipfile.lock",

    "pom.xml",
    "build.gradle",
    "build.gradle.kts",

    "Cargo.toml",
    "Cargo.lock",

    "go.mod",
    "go.sum",

    "composer.json",
    "Gemfile",

    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",

    ".gitignore"
}


def _is_test_path(path):
    path_lower = path.lower()

    filename = path_lower.split("/")[-1]

    return (
        "/test/" in path_lower
        or "/tests/" in path_lower
        or filename.startswith("test_")
        or filename.endswith("_test.py")
        or filename.endswith(".test.js")
        or filename.endswith(".test.jsx")
        or filename.endswith(".test.ts")
        or filename.endswith(".test.tsx")
        or filename.endswith(".spec.js")
        or filename.endswith(".spec.jsx")
        or filename.endswith(".spec.ts")
        or filename.endswith(".spec.tsx")
        or filename.endswith("_test.go")
    )


def _is_source_file(path):
    source_extensions = (
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".c",
        ".h",
        ".cpp",
        ".cc",
        ".cxx",
        ".cs",
        ".go",
        ".rs",
        ".php",
        ".rb",
        ".swift",
        ".kt",
        ".kts",
        ".scala",
        ".dart",
        ".vue",
        ".svelte"
    )

    return path.lower().endswith(source_extensions)


def _classify_path(path):
    path_lower = path.lower()

    if _is_test_path(path):
        return "test"

    if path_lower.startswith(".github/workflows/"):
        return "ci"

    if (
        path_lower.startswith("docs/")
        or "/docs/" in path_lower
    ):
        return "documentation"

    if _is_source_file(path):
        return "source"

    return "other"


def get_repository_tree(owner, repository, branch=None):
    repo = get_repository(
        owner,
        repository
    )

    if repo is None:
        return None

    branch = branch or repo.get(
        "default_branch",
        "main"
    )

    data = github_get(
        f"/repos/{owner}/{repository}/git/trees/{branch}",
        {
            "recursive": "1"
        }
    )

    if data is None:
        return None

    tree = data.get("tree", [])

    files = []
    directories = []

    for item in tree:
        path = item.get("path")

        if not path:
            continue

        item_type = item.get("type")

        if item_type == "tree":
            directories.append(path)

        elif item_type == "blob":
            files.append({
                "path": path,
                "size": item.get("size", 0),
                "category": _classify_path(path)
            })

    return {
        "branch": branch,
        "files": files,
        "directories": directories,
        "truncated": data.get("truncated", False)
    }


def get_repository_file(
    owner,
    repository,
    path,
    branch=None
):
    params = {}

    if branch:
        params["ref"] = branch

    data = github_get(
        f"/repos/{owner}/{repository}/contents/{path}",
        params
    )

    if data is None:
        return None

    if isinstance(data, list):
        return {
            "path": path,
            "type": "directory",
            "content": None
        }

    content = data.get("content")

    if content:
        import base64

        try:
            decoded = base64.b64decode(
                content
            ).decode(
                "utf-8",
                errors="replace"
            )
        except Exception:
            decoded = None
    else:
        decoded = None

    return {
        "path": data.get("path"),
        "name": data.get("name"),
        "size": data.get("size"),
        "sha": data.get("sha"),
        "type": data.get("type"),
        "content": decoded
    }


def get_repository_evidence(owner, repository):
    """
    Collect observable repository evidence.

    This function intentionally does NOT score the repository.

    It collects facts that the analysis engine can later evaluate.
    """

    repo = get_repository(
        owner,
        repository
    )

    if repo is None:
        return None

    default_branch = repo.get(
        "default_branch",
        "main"
    )

    tree = get_repository_tree(
        owner,
        repository,
        default_branch
    )

    if tree is None:
        tree = {
            "branch": default_branch,
            "files": [],
            "directories": [],
            "truncated": False
        }

    files = tree["files"]

    file_paths = {
        item["path"]
        for item in files
    }

    lower_file_paths = {
        path.lower(): path
        for path in file_paths
    }

    # -----------------------------------------------------
    # Detect important repository files
    # -----------------------------------------------------

    detected_files = {}

    for important_file in IMPORTANT_FILES:
        exact = lower_file_paths.get(
            important_file.lower()
        )

        if exact:
            detected_files[important_file] = exact

    workflow_files = [
        item["path"]
        for item in files
        if item["path"].lower().startswith(
            ".github/workflows/"
        )
        and item["path"].lower().endswith(
            (".yml", ".yaml")
        )
    ]

    test_files = [
        item["path"]
        for item in files
        if item["category"] == "test"
    ]

    source_files = [
        item["path"]
        for item in files
        if item["category"] == "source"
    ]

    documentation_files = [
        item["path"]
        for item in files
        if item["category"] == "documentation"
    ]

    # -----------------------------------------------------
    # Fetch only high-value text files.
    #
    # We deliberately do NOT download the entire repository.
    # -----------------------------------------------------

    files_to_read = set(
        detected_files.values()
    )

    files_to_read.update(
        workflow_files
    )

    file_contents = {}

    for path in files_to_read:
        file_data = get_repository_file(
            owner,
            repository,
            path,
            default_branch
        )

        if file_data is not None:
            content = file_data.get("content")

            if content is not None:
                # Avoid putting huge files into the analysis payload.
                file_contents[path] = content[:50000]

    # -----------------------------------------------------
    # Repository-level evidence
    # -----------------------------------------------------

    evidence = {
        "repository": {
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "description": repo.get("description"),
            "language": repo.get("language"),
            "topics": repo.get("topics", []),
            "license": (
                repo.get("license") or {}
            ).get("spdx_id"),
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
            "html_url": repo.get("html_url")
        },

        "structure": {
            "total_files": len(files),
            "total_directories": len(
                tree["directories"]
            ),
            "source_files": len(source_files),
            "test_files": len(test_files),
            "documentation_files": len(
                documentation_files
            ),
            "workflow_files": len(
                workflow_files
            ),
            "tree_truncated": tree.get(
                "truncated",
                False
            ),
            "files": files
        },

        "important_files": detected_files,

        "workflows": workflow_files,

        "file_contents": file_contents,

        "repository_flags": {
            "has_readme": any(
                key.lower().startswith("readme")
                for key in detected_files
            ),
            "has_license": any(
                key.lower() in {
                    "license",
                    "license.md",
                    "licence",
                    "licence.md"
                }
                for key in detected_files
            ),
            "has_contributing": any(
                key.lower().startswith(
                    "contributing"
                )
                for key in detected_files
            ),
            "has_code_of_conduct": any(
                key.lower().startswith(
                    "code_of_conduct"
                )
                for key in detected_files
            ),
            "has_security_policy": any(
                key.lower().startswith(
                    "security"
                )
                for key in detected_files
            ),
            "has_changelog": any(
                key.lower().startswith(
                    "changelog"
                )
                for key in detected_files
            ),
            "has_ci": len(
                workflow_files
            ) > 0,
            "has_tests": len(
                test_files
            ) > 0,
            "has_source_code": len(
                source_files
            ) > 0,
            "has_docs": len(
                documentation_files
            ) > 0
        }
    }

    return evidence
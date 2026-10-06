from datetime import datetime, timezone
import re
from services.project_type_service import detect_project_type
from services.monorepo_service import detect_monorepo


# ============================================================
# Evidence signal configuration
# ============================================================

# Files that declare a project's dependency surface.
DEPENDENCY_MANIFEST_FILES = (
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "pom.xml",
    "build.gradle",
    "Cargo.toml",
    "go.mod",
    "composer.json",
    "Gemfile",
)

# Source files above this size are treated as a structural risk signal.
LARGE_SOURCE_FILE_BYTES = 500000

# Directory holding GitHub Actions workflow definitions.
WORKFLOW_DIRECTORY = ".github/workflows/"

# Commands that indicate a workflow actually executes tests.
TEST_RUNNER_TERMS = (
    "pytest",
    "npm test",
    "npm run test",
    "yarn test",
    "jest",
    "vitest",
    "go test",
    "mvn test",
    "gradle test",
    "cargo test",
)

# Tools that indicate automated security / dependency scanning.
SECURITY_TOOL_TERMS = (
    "codeql",
    "dependency-review",
    "secret",
    "trivy",
    "snyk",
    "bandit",
    "npm audit",
)


# ============================================================
# Helpers
# ============================================================

def _parse_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    try:
        value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _days_since(value):
    date = _parse_date(value)

    if not date:
        return None

    now = datetime.now(timezone.utc)

    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)

    return max(0, (now - date).days)


def _status(passed, applicable=True):
    if not applicable:
        return "N/A"

    return "PASS" if passed else "NOT_DETECTED"


def _score_from_checks(checks, max_score):
    """
    Calculate a normalized category score.

    N/A checks are excluded from the denominator.
    """

    applicable = [
        check
        for check in checks
        if check.get("status") != "N/A"
    ]

    if not applicable:
        return {
            "score": None,
            "max_score": max_score,
            "percentage": None,
            "checks": checks,
        }

    earned = 0.0
    possible = 0.0

    for check in applicable:
        weight = float(check.get("weight", 0))
        status = check.get("status")

        possible += weight

        if status == "PASS":
            earned += weight

        elif status == "PARTIAL":
            earned += weight * 0.5

    if possible == 0:
        return {
            "score": None,
            "max_score": max_score,
            "percentage": None,
            "checks": checks,
        }

    percentage = (earned / possible) * 100
    score = (earned / possible) * max_score

    return {
        "score": round(score, 1),
        "max_score": max_score,
        "percentage": round(percentage, 1),
        "checks": checks,
    }


def _confidence(checks):
    applicable = [
        check
        for check in checks
        if check.get("status") != "N/A"
    ]

    if not applicable:
        return "LOW"

    unknown = sum(
        1
        for check in applicable
        if check.get("status") == "UNKNOWN"
    )

    if unknown >= len(applicable) * 0.5:
        return "LOW"

    if unknown > 0:
        return "MEDIUM"

    return "HIGH"


def _has_flag(flags, key):
    return bool(flags.get(key))


def _count_structure(structure, *keys):
    """
    Read a structure count while supporting the collector's
    current field names and reasonable compatibility aliases.
    """

    for key in keys:
        if key in structure:
            try:
                return int(structure.get(key, 0) or 0)
            except (TypeError, ValueError):
                return 0

    return 0


def _large_source_files(structure):
    """
    Identify unusually large source files.

    Prefers an explicit ``large_source_files`` list when the
    collector supplies one, and otherwise derives it from the
    per-file metadata in ``structure["files"]``.
    """

    reported = structure.get("large_source_files")

    if reported:
        return list(reported)

    large_files = []

    for item in structure.get("files", []) or []:
        if not isinstance(item, dict):
            continue

        if item.get("category") != "source":
            continue

        try:
            size = int(item.get("size", 0) or 0)
        except (TypeError, ValueError):
            continue

        if size > LARGE_SOURCE_FILE_BYTES:
            large_files.append(item)

    return large_files


def _workflow_contents(file_contents):
    """
    Yield (path, lowercased_text) for GitHub Actions workflow files.
    """

    for path, content in (file_contents or {}).items():
        if not path.lower().startswith(WORKFLOW_DIRECTORY):
            continue

        yield path, (content or "").lower()


def _workflow_runs_tests(file_contents):
    """
    True when a workflow appears to execute the project's test suite.
    """

    return any(
        term in text
        for _, text in _workflow_contents(file_contents)
        for term in TEST_RUNNER_TERMS
    )


def _workflow_has_security_signal(file_contents):
    """
    True when a workflow invokes a recognized security / dependency tool.
    """

    return any(
        term in text
        for _, text in _workflow_contents(file_contents)
        for term in SECURITY_TOOL_TERMS
    )


# ============================================================
# Repository Analytics
# ============================================================

def analyze_repositories(repositories):
    """
    Aggregate user-level repository metrics, language distribution,
    and top-starred repository list.
    """
    repositories = repositories or []

    if not repositories:
        return {
            "total": 0,
            "total_repositories": 0,
            "public": 0,
            "public_repositories": 0,
            "private": 0,
            "private_repositories": 0,
            "forks": 0,
            "total_forks": 0,
            "stars": 0,
            "total_stars": 0,
            "top_language": None,
            "languages": {},
            "top_repositories": [],
        }

    public = sum(
        1
        for repo in repositories
        if not repo.get("private", False)
    )

    private = len(repositories) - public

    forks = sum(
        int(repo.get("forks_count", 0) or 0)
        for repo in repositories
    )

    stars = sum(
        int(repo.get("stargazers_count", 0) or 0)
        for repo in repositories
    )

    languages = {}
    for repo in repositories:
        lang = repo.get("language")
        if lang:
            languages[lang] = languages.get(lang, 0) + 1

    top_language = (
        max(languages.items(), key=lambda item: item[1])[0]
        if languages
        else None
    )

    sorted_repos = sorted(
        repositories,
        key=lambda r: int(r.get("stargazers_count", 0) or 0),
        reverse=True,
    )

    top_repositories = []
    for repo in sorted_repos[:6]:
        top_repositories.append({
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "description": repo.get("description"),
            "stars": int(repo.get("stargazers_count", 0) or 0),
            "forks": int(repo.get("forks_count", 0) or 0),
            "language": repo.get("language"),
            "html_url": repo.get("html_url"),
        })

    return {
        "total": len(repositories),
        "total_repositories": len(repositories),
        "public": public,
        "public_repositories": public,
        "private": private,
        "private_repositories": private,
        "forks": forks,
        "total_forks": forks,
        "stars": stars,
        "total_stars": stars,
        "top_language": top_language,
        "languages": languages,
        "top_repositories": top_repositories,
    }


def analyze_contributors(contributors, commits=None):
    """
    Analyze repository contributors, contribution sums, and top contributor.
    """
    contributors = contributors or []

    if not contributors:
        return {
            "total": 0,
            "total_contributors": 0,
            "total_contributions": 0,
            "top": [],
            "top_contributor": None,
            "top_contributor_share": 0.0,
            "top3_share": 0.0,
            "bus_factor_50": 0,
            "bus_factor_80": 0,
            "herfindahl_index": 0.0,
            "recent_top_contributor_share_90d": 0.0,
        }

    top_contributors = []
    total_contributions = 0

    for contributor in contributors:
        count = int(contributor.get("contributions", 0) or 0)
        total_contributions += count

    for contributor in contributors[:10]:
        top_contributors.append({
            "login": contributor.get("login"),
            "contributions": int(contributor.get("contributions", 0) or 0),
        })

    top_contributor = (
        {
            "username": top_contributors[0]["login"],
            "contributions": top_contributors[0]["contributions"],
        }
        if top_contributors and top_contributors[0].get("login")
        else None
    )

    shares = sorted((int(c.get("contributions", 0) or 0) / total_contributions for c in contributors), reverse=True) if total_contributions else []
    recent = {}
    for commit in commits or []:
        author = (commit.get("commit", {}).get("author", {}) or {}).get("name") or "Unknown"
        age = _days_since((commit.get("commit", {}).get("author", {}) or {}).get("date"))
        if age is not None and age <= 90:
            recent[author] = recent.get(author, 0) + 1
    recent_total = sum(recent.values())
    recent_share = max(recent.values(), default=0) / recent_total if recent_total else 0.0
    def bus_factor(threshold):
        accumulated = 0.0
        for index, share in enumerate(sorted(shares, reverse=True), 1):
            accumulated += share
            if accumulated >= threshold:
                return index
        return 0

    return {
        "total": len(contributors),
        "total_contributors": len(contributors),
        "total_contributions": total_contributions,
        "top": top_contributors,
        "top_contributor": top_contributor,
        "top_contributor_share": round(shares[0], 4) if shares else 0.0,
        "top3_share": round(sum(sorted(shares, reverse=True)[:3]), 4),
        "bus_factor_50": bus_factor(0.50),
        "bus_factor_80": bus_factor(0.80),
        "herfindahl_index": round(sum(s * s for s in shares), 4),
        "recent_top_contributor_share_90d": round(recent_share, 4),
    }


def analyze_commits(commits):
    """
    Analyze commit history for recent activity, author breakdown,
    monthly timelines, and top commit author.
    """
    commits = commits or []

    if not commits:
        return {
            "total": 0,
            "total_commits": 0,
            "recent": 0,
            "authors": 0,
            "authors_count": 0,
            "commits_by_author": {},
            "commits_by_month": {},
            "top_commit_author": None,
            "commits_last_30_days": 0, "commits_last_365_days": 0,
            "active_months": 0, "longest_gap_days": 0, "days_since_last_commit": None,
        }

    recent = 0
    commits_by_author = {}
    commits_by_month = {}
    dated_commits = []
    commits_30 = commits_365 = 0

    for commit in commits:
        commit_data = commit.get("commit", {}) or {}
        author_data = (
            commit_data.get("author", {})
            or {}
        )

        author = author_data.get("name") or "Unknown"
        commits_by_author[author] = commits_by_author.get(author, 0) + 1

        date_str = author_data.get("date")
        parsed = _parse_date(date_str)

        if parsed:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            dated_commits.append(parsed)
            age_days = max(0, (datetime.now(timezone.utc) - parsed).days)
            commits_30 += age_days <= 30
            commits_365 += age_days <= 365
            month_key = parsed.strftime("%Y-%m")
            commits_by_month[month_key] = (
                commits_by_month.get(month_key, 0) + 1
            )

        age = _days_since(date_str)
        if age is not None and age <= 90:
            recent += 1

    sorted_months = dict(sorted(commits_by_month.items()))

    if commits_by_author:
        top_author_name, top_author_commits = max(
            commits_by_author.items(),
            key=lambda item: item[1],
        )
        top_commit_author = {
            "name": top_author_name,
            "commits": top_author_commits,
        }
    else:
        top_commit_author = None

    sorted_dates = sorted(dated_commits)
    gaps = [(b-a).total_seconds() / 86400 for a, b in zip(sorted_dates, sorted_dates[1:])]
    return {
        "total": len(commits),
        "total_commits": len(commits),
        "recent": recent,
        "authors": len(commits_by_author),
        "authors_count": len(commits_by_author),
        "commits_by_author": commits_by_author,
        "commits_by_month": sorted_months,
        "top_commit_author": top_commit_author,
        "commits_last_30_days": commits_30,
        "commits_last_365_days": commits_365,
        "active_months": len(commits_by_month),
        "longest_gap_days": round(max(gaps), 1) if gaps else 0,
        "days_since_last_commit": max(0, (datetime.now(timezone.utc) - max(dated_commits)).days) if dated_commits else None,
    }


def _ci_result(runs):
    completed = [r for r in (runs or []) if r.get("status") == "completed"]
    if not completed:
        return None
    completed.sort(key=lambda r: r.get("updated_at") or r.get("created_at") or "", reverse=True)
    successes = sum(1 for r in completed if r.get("conclusion") == "success")
    return {"completed_runs": len(completed), "success_rate": round(successes / len(completed), 4), "latest_conclusion": completed[0].get("conclusion")}


def _ci_status(runs, has_ci):
    if not has_ci or runs is None:
        return "N/A"
    result = _ci_result(runs)
    if not result or result["completed_runs"] < 3:
        return "N/A"
    if result["success_rate"] >= 0.80 and result["latest_conclusion"] != "failure":
        return "PASS"
    return "PARTIAL" if result["success_rate"] >= 0.50 else "NOT_DETECTED"


def _ci_evidence(runs, has_ci):
    result = _ci_result(runs or [])
    if not has_ci:
        return "CI workflows were not detected."
    if not result or result["completed_runs"] < 3:
        return "Recent completed run evidence is unavailable or insufficient."
    return f'{result["completed_runs"]} completed runs; success rate {result["success_rate"]:.0%}; latest conclusion {result["latest_conclusion"] or "unknown"}.'


def _workflow_hardening(file_contents):
    contents = [text for _, text in _workflow_contents(file_contents)]
    if not contents:
        return None
    uses = re.findall(r"(?im)^\s*-?\s*uses:\s*([^\s#]+)", "\n".join(contents))
    pinned = bool(uses) and all(re.search(r"@[0-9a-fA-F]{40}(?:\s|$)", use) for use in uses)
    permissions = any(re.search(r"(?m)^permissions\s*:", text) for text in contents)
    return pinned, permissions


def _workflow_hardening_status(file_contents):
    protections = _workflow_hardening(file_contents)
    if protections is None:
        return "N/A"
    count = sum(protections)
    return "PASS" if count == 2 else ("PARTIAL" if count == 1 else "NOT_DETECTED")


def _workflow_hardening_evidence(file_contents):
    protections = _workflow_hardening(file_contents)
    if protections is None:
        return "No workflow content was available."
    return f"SHA-pinned actions: {'yes' if protections[0] else 'no'}; top-level permissions block: {'yes' if protections[1] else 'no'}."


def _contributor_shares(contributors):
    counts = [max(0, int(c.get("contributions", 0) or 0)) for c in (contributors or [])]
    total = sum(counts)
    return sorted((c / total for c in counts), reverse=True) if total else []


def _concentration_status(contributors):
    if len(contributors or []) <= 1:
        return "N/A"
    shares = _contributor_shares(contributors)
    if not shares:
        return "N/A"
    return "PASS" if shares[0] <= 0.50 else ("PARTIAL" if shares[0] <= 0.75 else "NOT_DETECTED")


def _concentration_evidence(contributors):
    shares = _contributor_shares(contributors)
    if len(contributors or []) <= 1:
        return "Not applicable to a solo repository."
    if not shares:
        return "Contributor contribution totals were unavailable."
    return f"Top contributor holds {shares[0]:.0%} of recorded contributions."


# ============================================================
# Engineering Health
# ============================================================

def analyze_engineering_health(
    evidence,
    commits=None,
    contributors=None,
    workflow_runs=None,
):
    """
    Evidence-driven engineering health analysis.

    Principles:
    - Popularity does not affect the score.
    - Commit count does not dominate the score.
    - Missing optional evidence is not automatically a failure.
    - Project type affects applicability.
    - Every scored signal exposes its evidence.
    """

    evidence = evidence or {}
    commits = commits or []
    contributors = contributors or []

    structure = (
        evidence.get("structure", {})
        or {}
    )

    workflows = (
        evidence.get("workflows", [])
        or []
    )

    flags = (
        evidence.get("repository_flags", {})
        or {}
    )

    repository = (
        evidence.get("repository", {})
        or {}
    )

    important_files = (
        evidence.get("important_files", {})
        or {}
    )

    file_contents = (
        evidence.get("file_contents", {})
        or {}
    )

    workflow_runs = workflow_runs or []
    monorepo = detect_monorepo(structure, file_contents)

    # --------------------------------------------------------
    # Project type
    # --------------------------------------------------------

    project_type = detect_project_type(evidence)

    project_kind = project_type.get(
        "type",
        "unknown",
    )

    # --------------------------------------------------------
    # Structure evidence
    # --------------------------------------------------------

    source_files = _count_structure(
        structure,
        "source_files",
    )

    test_files = _count_structure(
        structure,
        "test_files",
    )

    documentation_files = _count_structure(
        structure,
        "documentation_files",
    )

    directories = _count_structure(
        structure,
        "total_directories",
        "directories",
    )

    total_files = _count_structure(
        structure,
        "total_files",
        "files_count",
        "files",
    )

    has_source = (
        source_files > 0
        or _has_flag(flags, "has_source_code")
    )

    has_tests = (
        test_files > 0
        or _has_flag(flags, "has_tests")
    )

    has_structure = (
        directories > 0
        or total_files > 1
    )

    has_docs = (
        documentation_files > 0
        or _has_flag(flags, "has_docs")
    )

    # --------------------------------------------------------
    # Repository flags
    # --------------------------------------------------------

    has_readme = _has_flag(
        flags,
        "has_readme",
    )

    has_license = _has_flag(
        flags,
        "has_license",
    )

    has_contributing = _has_flag(
        flags,
        "has_contributing",
    )

    has_code_of_conduct = _has_flag(
        flags,
        "has_code_of_conduct",
    )

    has_security = _has_flag(
        flags,
        "has_security_policy",
    )

    has_changelog = _has_flag(
        flags,
        "has_changelog",
    )

    has_gitignore = (
        _has_flag(
            flags,
            "has_gitignore",
        )
        or ".gitignore" in important_files
    )

    # The collector reports detected repository files rather than a
    # dedicated flag, so read the manifests out of ``important_files``
    # and keep the flag as an explicit override.
    has_dependency_manifest = (
        _has_flag(
            flags,
            "has_dependency_manifest",
        )
        or any(
            manifest in important_files
            for manifest in DEPENDENCY_MANIFEST_FILES
        )
    )

    has_ci = (
        bool(workflows)
        or _has_flag(
            flags,
            "has_ci",
        )
    )

    # --------------------------------------------------------
    # Applicability
    # --------------------------------------------------------

    readme_applicable = True

    license_applicable = True

    collaboration_docs_applicable = (
        project_kind != "unknown"
    )

    changelog_applicable = project_kind in {
        "web_application",
        "backend_api",
        "frontend_application",
        "library",
        "mobile_application",
        "desktop_application",
    }

    # The dependency-manifest check measures whether a manifest exists,
    # so it must always be scored instead of being gated on the very
    # fact it is testing for.
    dependency_applicable = True

    security_automation_applicable = (
        has_ci
        and (
            has_dependency_manifest
            or has_source
        )
    )

    # A single-contributor repository is not
    # automatically deficient in collaboration.
    collaboration_applicable = (
        len(contributors) > 1
    )

    # --------------------------------------------------------
    # CATEGORY 1 — CODE & STRUCTURE
    # --------------------------------------------------------

    large_source_files = _large_source_files(
        structure
    )

    code_checks = [
        {
            "name": "Source code detected",
            "status": _status(has_source),
            "weight": 6,
            "evidence": (
                f"{source_files} source files detected."
                if source_files > 0
                else (
                    "Source code was detected from repository "
                    "flags, but the source-file count was unavailable."
                    if has_source
                    else "No source files were detected."
                )
            ),
        },
        {
            "name": "Project structure detected",
            "status": _status(has_structure),
            "weight": 5,
            "evidence": (
                f"{directories} directories and "
                f"{total_files} files detected."
                if has_structure
                else "Very little repository structure was detected."
            ),
        },
        {
            "name": "Source organization",
            "status": _status(
                directories > 0,
                applicable=has_source,
            ),
            "weight": 5,
            "evidence": (
                "Source files are organized within repository "
                "directories."
                if has_source and directories > 0
                else (
                    "Source files were detected, but directory "
                    "organization was not detected."
                    if has_source
                    else (
                        "Not applicable because source code "
                        "was not detected."
                    )
                )
            ),
        },
        {
            "name": "Large-file risk signal",
            "status": _status(
                not large_source_files,
                applicable=has_source,
            ),
            "weight": 4,
            "evidence": (
                "No unusually large source files were detected."
                if not large_source_files
                else (
                    f"{len(large_source_files)} large source "
                    "file(s) were detected."
                )
            ),
        },
        {
            "name": "Workspace / monorepo layout",
            "status": ("PASS" if monorepo["explicit"] else "PARTIAL") if monorepo["is_monorepo"] else "N/A",
            "weight": 4,
            "evidence": "; ".join(monorepo["signals"]) if monorepo["signals"] else "No meaningful workspace or multi-package signals detected.",
        },
    ]

    code_result = _score_from_checks(
        code_checks,
        25,
    )

    # --------------------------------------------------------
    # CATEGORY 2 — TESTING & RELIABILITY
    # --------------------------------------------------------

    automated_test_execution_applicable = (
        has_tests and has_ci
    )

    workflow_runs_tests = _workflow_runs_tests(
        file_contents
    )

    testing_checks = [
        {
            "name": "Tests detected",
            "status": _status(has_tests),
            "weight": 8,
            "evidence": (
                f"{test_files} test files detected."
                if test_files > 0
                else "No test files were detected."
            ),
        },
        {
            "name": "Continuous integration",
            "status": _status(has_ci),
            "weight": 6,
            "evidence": (
                f"{len(workflows)} GitHub Actions workflow(s) detected."
                if workflows
                else (
                    "No GitHub Actions workflows were detected."
                )
            ),
        },
        {
            "name": "Automated test execution",
            "status": _status(
                workflow_runs_tests,
                applicable=automated_test_execution_applicable,
            ),
            "weight": 6,
            "evidence": (
                "A GitHub Actions workflow appears to execute "
                "the project's test suite."
                if workflow_runs_tests
                else (
                    "A workflow was available, but no recognizable "
                    "test command was found in it."
                    if automated_test_execution_applicable
                    else (
                        "Automated test execution cannot be evaluated "
                        "because tests or CI were not detected."
                    )
                )
            ),
        },
        {
            "name": "CI passing (recent runs)",
            "status": _ci_status(workflow_runs, has_ci),
            "weight": 4,
            "evidence": _ci_evidence(workflow_runs, has_ci),
        },
    ]

    testing_result = _score_from_checks(
        testing_checks,
        20,
    )

    # --------------------------------------------------------
    # CATEGORY 3 — DOCUMENTATION
    # --------------------------------------------------------

    documentation_checks = [
        {
            "name": "README",
            "status": _status(
                has_readme,
                applicable=readme_applicable,
            ),
            "weight": 5,
            "evidence": (
                "README.md detected."
                if has_readme
                else "README.md was not detected."
            ),
        },
        {
            "name": "License",
            "status": _status(
                has_license,
                applicable=license_applicable,
            ),
            "weight": 3,
            "evidence": (
                "License file detected."
                if has_license
                else "License file was not detected."
            ),
        },
        {
            "name": "Community documentation",
            "status": _status(
                (
                    has_contributing
                    or has_code_of_conduct
                ),
                applicable=collaboration_docs_applicable,
            ),
            "weight": 3,
            "evidence": (
                "CONTRIBUTING.md or CODE_OF_CONDUCT.md detected."
                if (
                    has_contributing
                    or has_code_of_conduct
                )
                else (
                    "Community contribution documentation "
                    "was not detected."
                )
            ),
        },
        {
            "name": "Changelog",
            "status": _status(
                has_changelog,
                applicable=changelog_applicable,
            ),
            "weight": 2,
            "evidence": (
                "Changelog detected."
                if has_changelog
                else "Changelog was not detected."
            ),
        },
    ]

    documentation_result = _score_from_checks(
        documentation_checks,
        15,
    )

    # --------------------------------------------------------
    # CATEGORY 4 — SECURITY & DEPENDENCIES
    # --------------------------------------------------------

    workflow_has_security_signal = _workflow_has_security_signal(
        file_contents
    )

    security_checks = [
        {
            "name": "Dependency manifest",
            "status": _status(
                has_dependency_manifest,
                applicable=dependency_applicable,
            ),
            "weight": 4,
            "evidence": (
                "Dependency manifest detected."
                if has_dependency_manifest
                else (
                    "No dependency manifest was detected."
                )
            ),
        },
        {
            "name": "Security policy",
            "status": _status(
                has_security,
                applicable=True,
            ),
            "weight": 3,
            "evidence": (
                "SECURITY.md detected."
                if has_security
                else "SECURITY.md was not detected."
            ),
        },
        {
            "name": ".gitignore",
            "status": _status(
                has_gitignore,
                applicable=has_source,
            ),
            "weight": 3,
            "evidence": (
                ".gitignore detected."
                if has_gitignore
                else ".gitignore was not detected."
            ),
        },
        {
            "name": "Security automation signal",
            "status": _status(
                workflow_has_security_signal,
                applicable=security_automation_applicable,
            ),
            "weight": 5,
            "evidence": (
                "A workflow invokes a recognized security or "
                "dependency scanning tool."
                if workflow_has_security_signal
                else (
                    "No security or dependency scanning tool was "
                    "found in the available workflows."
                    if security_automation_applicable
                    else (
                        "Security automation was not evaluated because "
                        "CI/dependency/source evidence was insufficient."
                    )
                )
            ),
        },
        {
            "name": "Workflow hardening",
            "status": _workflow_hardening_status(file_contents),
            "weight": 3,
            "evidence": _workflow_hardening_evidence(file_contents),
        },
    ]

    security_result = _score_from_checks(
        security_checks,
        15,
    )

    # --------------------------------------------------------
    # CATEGORY 5 — MAINTENANCE
    # --------------------------------------------------------

    activity_date = (
        repository.get("pushed_at")
        or repository.get("updated_at")
    )

    days_since_activity = _days_since(
        activity_date
    )

    if days_since_activity is None:
        maintenance_activity_status = "UNKNOWN"
        maintenance_activity_evidence = (
            "Repository activity date was unavailable."
        )

    elif days_since_activity <= 30:
        maintenance_activity_status = "PASS"
        maintenance_activity_evidence = (
            f"Repository activity detected "
            f"{days_since_activity} day(s) ago."
        )

    elif days_since_activity <= 90:
        maintenance_activity_status = "PARTIAL"
        maintenance_activity_evidence = (
            f"Repository activity detected "
            f"{days_since_activity} day(s) ago."
        )

    elif days_since_activity <= 365:
        maintenance_activity_status = "PARTIAL"
        maintenance_activity_evidence = (
            f"Repository activity detected "
            f"{days_since_activity} day(s) ago."
        )

    else:
        maintenance_activity_status = "NOT_DETECTED"
        maintenance_activity_evidence = (
            f"No recent repository activity detected; "
            f"last activity was {days_since_activity} day(s) ago."
        )

    intentionally_frozen = bool(repository.get("archived") or repository.get("disabled"))
    if intentionally_frozen:
        maintenance_activity_status = "N/A"
        maintenance_activity_evidence = "Recent activity is not scored because the repository is archived or disabled."

    history_available = bool(
        evidence.get(
            "history_available",
            commits,
        )
    )

    commit_count = len(commits)

    if not history_available:
        historical_status = "N/A"
        historical_evidence = (
            "Commit history was unavailable, so historical "
            "activity was not scored."
        )

    elif commit_count >= 2:
        historical_status = "PASS"
        historical_evidence = (
            f"{commit_count} commits were available for analysis."
        )

    elif commit_count == 1:
        historical_status = "PARTIAL"
        historical_evidence = (
            "Only one commit was available in the analyzed history."
        )

    else:
        historical_status = "NOT_DETECTED"
        historical_evidence = (
            "No commits were available in the analyzed history."
        )

    commit_stats = analyze_commits(commits)
    if not history_available:
        cadence_status, cadence_evidence = "N/A", "Commit history was unavailable."
    elif intentionally_frozen:
        cadence_status, cadence_evidence = "N/A", "Commit cadence is not scored for an archived or disabled repository."
    elif len(commits) < 2:
        cadence_status, cadence_evidence = "PARTIAL", "Too little commit history is available to assess cadence consistency."
    else:
        gap = commit_stats["longest_gap_days"]
        if commit_stats["active_months"] >= 6 and gap <= 120:
            cadence_status = "PASS"
        elif commit_stats["active_months"] >= 2 and gap <= 365:
            cadence_status = "PARTIAL"
        else:
            cadence_status = "NOT_DETECTED"
        cadence_evidence = f'{commit_stats["active_months"]} active month(s); longest observed gap {gap} day(s).'

    maintenance_checks = [
        {
            "name": "Recent repository activity",
            "status": maintenance_activity_status,
            "weight": 10,
            "evidence": maintenance_activity_evidence,
        },
        {
            "name": "Historical activity",
            "status": historical_status,
            "weight": 5,
            "evidence": historical_evidence,
        },
        {"name": "Commit cadence consistency", "status": cadence_status, "weight": 3, "evidence": cadence_evidence},
    ]

    maintenance_result = _score_from_checks(
        maintenance_checks,
        15,
    )

    # --------------------------------------------------------
    # CATEGORY 6 — COLLABORATION
    # --------------------------------------------------------

    contributor_count = len(contributors)

    if contributor_count >= 2:
        contributor_status = "PASS"
        contributor_evidence = (
            f"{contributor_count} contributors were detected."
        )

    elif contributor_count == 1:
        contributor_status = "PARTIAL"
        contributor_evidence = (
            "One contributor was detected. Solo development "
            "is not treated as a defect."
        )

    else:
        contributor_status = "UNKNOWN"
        contributor_evidence = (
            "Contributor information was unavailable."
        )

    collaboration_checks = [
        {
            "name": "Multiple contributors",
            "status": (
                contributor_status
                if collaboration_applicable
                else "N/A"
            ),
            "weight": 5,
            "evidence": contributor_evidence,
        },
        {
            "name": "Contribution guidance",
            "status": _status(
                has_contributing,
                applicable=collaboration_docs_applicable,
            ),
            "weight": 5,
            "evidence": (
                "CONTRIBUTING.md detected."
                if has_contributing
                else (
                    "CONTRIBUTING.md was not detected."
                )
            ),
        },
        {
            "name": "Contributor concentration / bus factor",
            "status": _concentration_status(contributors),
            "weight": 3,
            "evidence": _concentration_evidence(contributors),
        },
    ]

    collaboration_result = _score_from_checks(
        collaboration_checks,
        10,
    )

    # --------------------------------------------------------
    # Categories
    # --------------------------------------------------------

    categories = {
        "code_structure": {
            "label": "Code & Structure",
            **code_result,
            "confidence": _confidence(
                code_checks
            ),
        },
        "testing_reliability": {
            "label": "Testing & Reliability",
            **testing_result,
            "confidence": _confidence(
                testing_checks
            ),
        },
        "documentation": {
            "label": "Documentation",
            **documentation_result,
            "confidence": _confidence(
                documentation_checks
            ),
        },
        "security_dependencies": {
            "label": "Security & Dependencies",
            **security_result,
            "confidence": _confidence(
                security_checks
            ),
        },
        "maintenance": {
            "label": "Maintenance",
            **maintenance_result,
            "confidence": _confidence(
                maintenance_checks
            ),
        },
        "collaboration": {
            "label": "Collaboration",
            **collaboration_result,
            "confidence": _confidence(
                collaboration_checks
            ),
        },
    }

    # --------------------------------------------------------
    # Overall score
    # --------------------------------------------------------

    weighted_categories = [
        category
        for category in categories.values()
        if category.get("score") is not None
    ]

    total_possible_weight = sum(
        category["max_score"]
        for category in weighted_categories
    )

    total_score = sum(
        category["score"]
        for category in weighted_categories
    )

    if total_possible_weight > 0:
        normalized_score = round(
            (
                total_score
                / total_possible_weight
            ) * 100,
            1,
        )
    else:
        normalized_score = None

    # --------------------------------------------------------
    # Strengths / concerns
    # --------------------------------------------------------

    strengths = []
    concerns = []
    recommendations = []

    for category in categories.values():
        score = category.get("score")
        percentage = category.get("percentage")

        if score is None or percentage is None:
            continue

        if percentage >= 80:
            strengths.append(
                f"{category['label']} has strong detected evidence."
            )

        elif percentage < 50:
            concerns.append(
                f"{category['label']} has limited detected evidence."
            )

    # --------------------------------------------------------
    # Recommendations
    # --------------------------------------------------------

    if not has_readme:
        recommendations.append(
            "Add a clear README explaining the project, setup, "
            "usage, and major features."
        )

    if not has_tests:
        recommendations.append(
            "Add automated tests for important application behavior."
        )

    if not has_ci:
        recommendations.append(
            "Consider adding CI to automatically validate changes."
        )

    if has_source and not has_gitignore:
        recommendations.append(
            "Add a .gitignore appropriate for the project's ecosystem."
        )

    if (
        has_dependency_manifest
        and not has_security
    ):
        recommendations.append(
            "Consider adding a SECURITY.md file with vulnerability "
            "reporting guidance."
        )

    if (
        project_kind in {
            "library",
            "web_application",
            "backend_api",
            "frontend_application",
        }
        and not has_changelog
    ):
        recommendations.append(
            "Consider maintaining a changelog as the project evolves."
        )

    # --------------------------------------------------------
    # Overall confidence
    # --------------------------------------------------------

    all_checks = []

    for category in categories.values():
        all_checks.extend(
            category.get("checks", [])
        )

    overall_confidence = _confidence(
        all_checks
    )

    if project_type.get("confidence") == "LOW":
        if overall_confidence == "HIGH":
            overall_confidence = "MEDIUM"

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    if normalized_score is None:
        summary = (
            "GitScope could not calculate an engineering health "
            "score from the available repository evidence."
        )
    else:
        summary = (
            f"GitScope detected a "
            f"{project_type.get('label', 'repository')} "
            f"and calculated an engineering health score of "
            f"{normalized_score}/100 using repository evidence."
        )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {
        "score": normalized_score,
        "max_score": 100,

        "project_type": {
            "type": project_type.get("type"),
            "label": project_type.get("label"),
            "confidence": project_type.get("confidence"),
            "signals": project_type.get("signals", []),
        },

        "monorepo": monorepo,
        "ci": _ci_result(workflow_runs),

        "categories": categories,

        "confidence": overall_confidence,

        "strengths": strengths,
        "concerns": concerns,
        "recommendations": recommendations,

        "summary": summary,

        "methodology": {
            "type": "evidence_based",
            "ai_used": False,
            "popularity_in_score": False,
            "commit_count_dominates_score": False,
            "missing_optional_evidence_penalty": False,
            "project_type_context": True,
            "normalized_applicable_weights": True,
        },
    }


# ============================================================
# Backward compatibility
# ============================================================

def analyze_activity(
    commits=None,
    contributors=None,
):
    """
    Compatibility wrapper for older frontend/backend code.
    """

    return {
        "commits": analyze_commits(
            commits or []
        ),
        "contributors": analyze_contributors(
            contributors or []
        ),
    }

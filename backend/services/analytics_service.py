from collections import Counter
from datetime import datetime, timezone


# =========================================================
# Helpers
# =========================================================

def _parse_date(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        return None


def _days_since(value):
    date = _parse_date(value)

    if date is None:
        return None

    now = datetime.now(timezone.utc)

    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)

    return max(
        0,
        (now - date).days
    )


def _status(passed, partial=False):
    if passed:
        return "PASS"

    if partial:
        return "PARTIAL"

    return "NOT_DETECTED"


def _score_from_checks(checks, maximum):
    """
    Score only applicable checks.

    A missing optional signal does not automatically become
    a negative score.
    """

    applicable = [
        check
        for check in checks
        if check.get("applicable", True)
    ]

    if not applicable:
        return maximum

    earned = sum(
        check.get("points", 0)
        for check in applicable
    )

    possible = sum(
        check.get("max_points", 0)
        for check in applicable
    )

    if possible <= 0:
        return maximum

    return round(
        (earned / possible) * maximum
    )


def _confidence(evidence):
    """
    Confidence reflects how much observable evidence exists,
    not whether the repository is good or bad.
    """

    structure = evidence.get(
        "structure",
        {}
    )

    repository = evidence.get(
        "repository",
        {}
    )

    files = structure.get(
        "total_files",
        0
    )

    source_files = structure.get(
        "source_files",
        0
    )

    history_available = bool(
        evidence.get("history_available")
    )

    evidence_signals = 0

    if files > 0:
        evidence_signals += 1

    if source_files > 0:
        evidence_signals += 1

    if evidence.get(
        "important_files"
    ):
        evidence_signals += 1

    if evidence.get(
        "workflows"
    ):
        evidence_signals += 1

    if repository.get(
        "updated_at"
    ):
        evidence_signals += 1

    if history_available:
        evidence_signals += 2

    if structure.get(
        "tree_truncated"
    ):
        evidence_signals -= 2

    if evidence_signals >= 6:
        return "HIGH"

    if evidence_signals >= 3:
        return "MEDIUM"

    return "LOW"


# =========================================================
# Repository overview
# =========================================================

def analyze_repositories(repositories):
    if not repositories:
        return {
            "total_repositories": 0,
            "total_stars": 0,
            "total_forks": 0,
            "total_open_issues": 0,
            "languages": {},
            "top_language": None,
            "top_repositories": []
        }

    language_counter = Counter()

    for repo in repositories:
        language = repo.get("language")

        if language:
            language_counter[language] += 1

    top_repositories = sorted(
        repositories,
        key=lambda repo: (
            repo.get("stargazers_count", 0) or 0
        ),
        reverse=True
    )[:5]

    return {
        "total_repositories": len(
            repositories
        ),
        "total_stars": sum(
            repo.get(
                "stargazers_count",
                0
            ) or 0
            for repo in repositories
        ),
        "total_forks": sum(
            repo.get(
                "forks_count",
                0
            ) or 0
            for repo in repositories
        ),
        "total_open_issues": sum(
            repo.get(
                "open_issues_count",
                0
            ) or 0
            for repo in repositories
        ),
        "languages": dict(
            language_counter
        ),
        "top_language": (
            language_counter.most_common(1)[0][0]
            if language_counter
            else None
        ),
        "top_repositories": [
            {
                "name": repo.get("name"),
                "stars": repo.get(
                    "stargazers_count",
                    0
                ),
                "forks": repo.get(
                    "forks_count",
                    0
                ),
                "language": repo.get(
                    "language"
                )
            }
            for repo in top_repositories
        ]
    }


# =========================================================
# Contributor analysis
# =========================================================

def analyze_contributors(contributors):
    if not contributors:
        return {
            "total_contributors": 0,
            "total_contributions": 0,
            "top_contributor": None,
            "contribution_distribution": []
        }

    sorted_contributors = sorted(
        contributors,
        key=lambda contributor: (
            contributor.get(
                "contributions",
                0
            ) or 0
        ),
        reverse=True
    )

    total_contributions = sum(
        contributor.get(
            "contributions",
            0
        ) or 0
        for contributor in contributors
    )

    distribution = []

    for contributor in sorted_contributors[:10]:
        distribution.append({
            "login": contributor.get(
                "login"
            ),
            "contributions": contributor.get(
                "contributions",
                0
            )
        })

    top = (
        sorted_contributors[0]
        if sorted_contributors
        else None
    )

    return {
        "total_contributors": len(
            contributors
        ),
        "total_contributions": total_contributions,
        "top_contributor": (
            top.get("login")
            if top
            else None
        ),
        "contribution_distribution": distribution
    }


# =========================================================
# Commit analysis
# =========================================================

def analyze_commits(commits):
    if not commits:
        return {
            "total_commits": 0,
            "commits_by_author": {},
            "commits_by_month": {},
            "active_months": 0,
            "average_commits_per_active_month": 0,
            "top_author": None
        }

    author_counter = Counter()
    month_counter = Counter()

    for commit in commits:
        commit_data = commit.get(
            "commit",
            {}
        )

        author_data = commit_data.get(
            "author",
            {}
        )

        author = (
            author_data.get("name")
            or commit.get(
                "author",
                {}
            ).get("login")
            or "Unknown"
        )

        author_counter[author] += 1

        date = author_data.get("date")

        if date:
            parsed = _parse_date(date)

            if parsed:
                month_counter[
                    parsed.strftime("%Y-%m")
                ] += 1

    active_months = len(
        month_counter
    )

    average = (
        len(commits) / active_months
        if active_months
        else 0
    )

    return {
        "total_commits": len(commits),
        "commits_by_author": dict(
            author_counter
        ),
        "commits_by_month": dict(
            sorted(month_counter.items())
        ),
        "active_months": active_months,
        "average_commits_per_active_month": round(
            average,
            2
        ),
        "top_author": (
            author_counter.most_common(1)[0][0]
            if author_counter
            else None
        )
    }


# =========================================================
# Engineering Health
# =========================================================

def analyze_engineering_health(
    evidence,
    commits=None,
    contributors=None
):
    commits = commits or []
    contributors = contributors or []

    structure = evidence.get(
        "structure",
        {}
    )

    flags = evidence.get(
        "repository_flags",
        {}
    )

    important_files = evidence.get(
        "important_files",
        {}
    )

    repository = evidence.get(
        "repository",
        {}
    )

    # -----------------------------------------------------
    # 1. Code & Structure — 25
    # -----------------------------------------------------

    code_checks = []

    has_source = flags.get(
        "has_source_code",
        False
    )

    code_checks.append({
        "name": "Source code detected",
        "status": _status(has_source),
        "points": 6 if has_source else 0,
        "max_points": 6,
        "applicable": True,
        "evidence": (
            "Source files were found."
            if has_source
            else
            "No recognized source files were detected."
        )
    })

    has_structure = (
        structure.get(
            "total_directories",
            0
        ) > 0
    )

    code_checks.append({
        "name": "Project structure",
        "status": _status(
            has_structure,
            partial=(
                structure.get(
                    "total_files",
                    0
                ) > 0
            )
        ),
        "points": (
            5 if has_structure
            else 3 if structure.get(
                "total_files",
                0
            ) > 0
            else 0
        ),
        "max_points": 5,
        "applicable": True,
        "evidence": (
            f"{structure.get('total_directories', 0)} "
            "directories were detected."
        )
    })

    source_count = structure.get(
        "source_files",
        0
    )

    huge_file_count = sum(
        1
        for file in structure.get(
            "files",
            []
        )
        if (
            file.get("category") == "source"
            and file.get("size", 0) > 500000
        )
    )

    code_checks.append({
        "name": "Source organization",
        "status": _status(
            source_count > 1,
            partial=source_count == 1
        ),
        "points": (
            5 if source_count > 1
            else 3 if source_count == 1
            else 0
        ),
        "max_points": 5,
        "applicable": True,
        "evidence": (
            f"{source_count} source files detected."
        )
    })

    code_checks.append({
        "name": "Large source-file signal",
        "status": (
            "PASS"
            if huge_file_count == 0
            else "PARTIAL"
        ),
        "points": 4 if huge_file_count == 0 else 2,
        "max_points": 4,
        "applicable": True,
        "evidence": (
            "No source files larger than 500 KB detected."
            if huge_file_count == 0
            else
            f"{huge_file_count} very large source file(s) detected."
        )
    })

    code_score = _score_from_checks(
        code_checks,
        25
    )

    # -----------------------------------------------------
    # 2. Testing & Reliability — 20
    # -----------------------------------------------------

    testing_checks = []

    test_count = structure.get(
        "test_files",
        0
    )

    testing_checks.append({
        "name": "Tests detected",
        "status": _status(
            test_count > 0
        ),
        "points": 8 if test_count > 0 else 0,
        "max_points": 8,
        "applicable": True,
        "evidence": (
            f"{test_count} test file(s) detected."
        )
    })

    has_ci = flags.get(
        "has_ci",
        False
    )

    testing_checks.append({
        "name": "Continuous integration",
        "status": _status(has_ci),
        "points": 6 if has_ci else 0,
        "max_points": 6,
        "applicable": True,
        "evidence": (
            "GitHub Actions workflow(s) detected."
            if has_ci
            else
            "No GitHub Actions workflow was detected."
        )
    })

    workflow_contents = evidence.get(
        "file_contents",
        {}
    )

    runs_tests = False

    for path, content in workflow_contents.items():
        if not path.lower().startswith(
            ".github/workflows/"
        ):
            continue

        text = (content or "").lower()

        test_terms = [
            "pytest",
            "npm test",
            "npm run test",
            "yarn test",
            "jest",
            "vitest",
            "go test",
            "mvn test",
            "gradle test",
            "cargo test"
        ]

        if any(
            term in text
            for term in test_terms
        ):
            runs_tests = True
            break

    testing_checks.append({
        "name": "Automated test execution",
        "status": _status(runs_tests),
        "points": 6 if runs_tests else 0,
        "max_points": 6,
        "applicable": has_ci,
        "evidence": (
            "A workflow appears to execute tests."
            if runs_tests
            else
            "No recognizable test command was found in workflows."
        )
    })

    testing_score = _score_from_checks(
        testing_checks,
        20
    )

    # -----------------------------------------------------
    # 3. Documentation — 15
    # -----------------------------------------------------

    documentation_checks = []

    readme = flags.get(
        "has_readme",
        False
    )

    documentation_checks.append({
        "name": "README",
        "status": _status(readme),
        "points": 5 if readme else 0,
        "max_points": 5,
        "applicable": True,
        "evidence": (
            "README detected."
            if readme
            else
            "README was not detected."
        )
    })

    license_present = flags.get(
        "has_license",
        False
    )

    documentation_checks.append({
        "name": "License",
        "status": _status(
            license_present
        ),
        "points": 3 if license_present else 0,
        "max_points": 3,
        "applicable": True,
        "evidence": (
            "License file detected."
            if license_present
            else
            "No license file was detected."
        )
    })

    contributing = flags.get(
        "has_contributing",
        False
    )

    code_of_conduct = flags.get(
        "has_code_of_conduct",
        False
    )

    community_docs = (
        contributing
        or code_of_conduct
    )

    documentation_checks.append({
        "name": "Community documentation",
        "status": _status(
            community_docs,
            partial=(
                contributing
                or code_of_conduct
            )
        ),
        "points": (
            3 if contributing and code_of_conduct
            else 2 if community_docs
            else 0
        ),
        "max_points": 3,
        "applicable": True,
        "evidence": (
            "Contributor/community guidance detected."
            if community_docs
            else
            "No CONTRIBUTING.md or CODE_OF_CONDUCT.md detected."
        )
    })

    changelog = flags.get(
        "has_changelog",
        False
    )

    documentation_checks.append({
        "name": "Change documentation",
        "status": _status(changelog),
        "points": 2 if changelog else 0,
        "max_points": 2,
        "applicable": True,
        "evidence": (
            "CHANGELOG detected."
            if changelog
            else
            "No CHANGELOG detected."
        )
    })

    documentation_score = _score_from_checks(
        documentation_checks,
        15
    )

    # -----------------------------------------------------
    # 4. Security & Dependencies — 15
    # -----------------------------------------------------

    security_checks = []

    dependency_files = [
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "pom.xml",
        "build.gradle",
        "Cargo.toml",
        "go.mod",
        "composer.json",
        "Gemfile"
    ]

    dependency_present = any(
        key in important_files
        for key in dependency_files
    )

    security_checks.append({
        "name": "Dependency manifest",
        "status": _status(
            dependency_present
        ),
        "points": (
            4 if dependency_present else 0
        ),
        "max_points": 4,
        "applicable": True,
        "evidence": (
            "A dependency manifest was detected."
            if dependency_present
            else
            "No recognized dependency manifest was detected."
        )
    })

    security_policy = flags.get(
        "has_security_policy",
        False
    )

    security_checks.append({
        "name": "Security policy",
        "status": _status(
            security_policy
        ),
        "points": 3 if security_policy else 0,
        "max_points": 3,
        "applicable": True,
        "evidence": (
            "SECURITY.md detected."
            if security_policy
            else
            "No SECURITY.md detected."
        )
    })

    gitignore = ".gitignore" in important_files

    security_checks.append({
        "name": "Git ignore configuration",
        "status": _status(gitignore),
        "points": 3 if gitignore else 0,
        "max_points": 3,
        "applicable": True,
        "evidence": (
            ".gitignore detected."
            if gitignore
            else
            "No .gitignore detected."
        )
    })

    workflow_security = False

    for path, content in workflow_contents.items():
        text = (content or "").lower()

        security_terms = [
            "codeql",
            "dependency-review",
            "secret",
            "trivy",
            "snyk",
            "bandit",
            "npm audit"
        ]

        if any(
            term in text
            for term in security_terms
        ):
            workflow_security = True
            break

    security_checks.append({
        "name": "Automated security signal",
        "status": _status(
            workflow_security
        ),
        "points": (
            5 if workflow_security else 0
        ),
        "max_points": 5,
        "applicable": has_ci,
        "evidence": (
            "A recognizable security-related workflow signal was found."
            if workflow_security
            else
            "No recognizable security workflow was detected."
        )
    })

    security_score = _score_from_checks(
        security_checks,
        15
    )

    # -----------------------------------------------------
    # 5. Maintenance — 15
    # -----------------------------------------------------

    maintenance_checks = []

    updated_at = repository.get(
        "updated_at"
    )

    days_since_update = _days_since(
        updated_at
    )

    if days_since_update is None:
        maintenance_checks.append({
            "name": "Recent repository activity",
            "status": "UNKNOWN",
            "points": 0,
            "max_points": 10,
            "applicable": False,
            "evidence": "Update date unavailable."
        })
    else:
        if days_since_update <= 30:
            points = 10
            status = "PASS"
        elif days_since_update <= 90:
            points = 7
            status = "PARTIAL"
        elif days_since_update <= 365:
            points = 4
            status = "PARTIAL"
        else:
            points = 1
            status = "PARTIAL"

        maintenance_checks.append({
            "name": "Recent repository activity",
            "status": status,
            "points": points,
            "max_points": 10,
            "applicable": True,
            "evidence": (
                f"Repository was last updated "
                f"{days_since_update} day(s) ago."
            )
        })

    commit_count = len(commits)

    maintenance_checks.append({
        "name": "Historical activity evidence",
        "status": (
            "PASS"
            if commit_count >= 2
            else "PARTIAL"
            if commit_count == 1
            else "UNKNOWN"
        ),
        "points": (
            5 if commit_count >= 2
            else 3 if commit_count == 1
            else 0
        ),
        "max_points": 5,
        "applicable": bool(commits),
        "evidence": (
            f"{commit_count} commit(s) available for analysis."
        )
    })

    maintenance_score = _score_from_checks(
        maintenance_checks,
        15
    )

    # -----------------------------------------------------
    # 6. Collaboration — 10
    # -----------------------------------------------------

    collaboration_checks = []

    contributor_count = len(
        contributors
    )

    collaboration_checks.append({
        "name": "Contributor evidence",
        "status": (
            "PASS"
            if contributor_count >= 2
            else "PARTIAL"
            if contributor_count == 1
            else "UNKNOWN"
        ),
        "points": (
            5 if contributor_count >= 2
            else 3 if contributor_count == 1
            else 0
        ),
        "max_points": 5,
        "applicable": bool(contributors),
        "evidence": (
            f"{contributor_count} contributor(s) detected."
        )
    })

    has_contributing = flags.get(
        "has_contributing",
        False
    )

    collaboration_checks.append({
        "name": "Contribution guidance",
        "status": _status(
            has_contributing
        ),
        "points": (
            5 if has_contributing else 0
        ),
        "max_points": 5,
        "applicable": True,
        "evidence": (
            "CONTRIBUTING guidance detected."
            if has_contributing
            else
            "No CONTRIBUTING guidance detected."
        )
    })

    collaboration_score = _score_from_checks(
        collaboration_checks,
        10
    )

    # -----------------------------------------------------
    # Final score
    # -----------------------------------------------------

    categories = {
        "code_structure": {
            "label": "Code & Structure",
            "score": code_score,
            "maximum": 25,
            "checks": code_checks
        },
        "testing_reliability": {
            "label": "Testing & Reliability",
            "score": testing_score,
            "maximum": 20,
            "checks": testing_checks
        },
        "documentation": {
            "label": "Documentation",
            "score": documentation_score,
            "maximum": 15,
            "checks": documentation_checks
        },
        "security_dependencies": {
            "label": "Security & Dependencies",
            "score": security_score,
            "maximum": 15,
            "checks": security_checks
        },
        "maintenance": {
            "label": "Maintenance",
            "score": maintenance_score,
            "maximum": 15,
            "checks": maintenance_checks
        },
        "collaboration": {
            "label": "Collaboration",
            "score": collaboration_score,
            "maximum": 10,
            "checks": collaboration_checks
        }
    }

    total_score = sum(
        category["score"]
        for category in categories.values()
    )

    # -----------------------------------------------------
    # Evidence summary
    # -----------------------------------------------------

    strengths = []
    concerns = []

    for category in categories.values():
        for check in category["checks"]:
            status = check.get(
                "status"
            )

            if status == "PASS":
                strengths.append({
                    "category": category["label"],
                    "title": check["name"],
                    "evidence": check["evidence"]
                })

            elif status in {
                "PARTIAL",
                "NOT_DETECTED"
            }:
                concerns.append({
                    "category": category["label"],
                    "title": check["name"],
                    "evidence": check["evidence"]
                })

    confidence = _confidence(
        evidence
    )

    # -----------------------------------------------------
    # Human-readable assessment
    # -----------------------------------------------------

    if total_score >= 85:
        summary = (
            "The repository shows strong observable engineering "
            "signals across its structure, documentation, testing, "
            "security, and maintenance evidence."
        )
    elif total_score >= 70:
        summary = (
            "The repository shows a solid set of engineering "
            "signals, with some areas where additional evidence "
            "or project practices could strengthen the assessment."
        )
    elif total_score >= 50:
        summary = (
            "The repository has several useful engineering signals, "
            "but GitScope found meaningful gaps or limited evidence "
            "in some areas."
        )
    else:
        summary = (
            "GitScope found limited engineering evidence across "
            "several assessment areas. The result should be "
            "interpreted together with the confidence level."
        )

    recommendations = []

    for concern in concerns[:6]:
        recommendations.append({
            "category": concern["category"],
            "recommendation": (
                f"Review {concern['title'].lower()}."
            )
        })

    return {
        "score": total_score,
        "maximum": 100,
        "label": "Engineering Health",
        "confidence": confidence,
        "summary": summary,
        "categories": categories,
        "strengths": strengths[:8],
        "concerns": concerns[:8],
        "recommendations": recommendations,
        "methodology": {
            "type": "evidence_based",
            "ai_used": False,
            "popularity_in_score": False,
            "commit_count_dominates_score": False,
            "missing_optional_evidence_penalty": False
        }
    }


# =========================================================
# Compatibility function
# =========================================================

def analyze_activity(
    repo,
    commits,
    contributors
):
    """
    Compatibility wrapper for the existing frontend/API.

    The new system should eventually consume
    analyze_engineering_health() directly.
    """

    evidence = {
        "repository": repo or {},
        "structure": {
            "total_files": 0,
            "total_directories": 0,
            "source_files": 0,
            "test_files": 0,
            "documentation_files": 0,
            "workflow_files": 0,
            "tree_truncated": False,
            "files": []
        },
        "important_files": {},
        "workflows": [],
        "file_contents": {},
        "repository_flags": {},
        "history_available": bool(commits)
    }

    health = analyze_engineering_health(
        evidence,
        commits,
        contributors
    )

    return health["score"]
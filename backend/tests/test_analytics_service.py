import sys
import os
import unittest

# Ensure backend directory is in sys.path
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from services.analytics_service import (
    analyze_repositories,
    analyze_contributors,
    analyze_commits,
    analyze_engineering_health
)


class TestAnalyticsServiceContract(unittest.TestCase):

    def test_analyze_repositories_empty(self):
        result = analyze_repositories([])
        self.assertEqual(result["total_repositories"], 0)
        self.assertEqual(result["total_stars"], 0)
        self.assertEqual(result["total_forks"], 0)
        self.assertEqual(result["languages"], {})
        self.assertIsNone(result["top_language"])
        self.assertEqual(result["top_repositories"], [])

    def test_analyze_repositories_populated(self):
        sample_repos = [
            {
                "name": "Repo1",
                "full_name": "user/Repo1",
                "stargazers_count": 100,
                "forks_count": 25,
                "language": "Python",
                "private": False,
                "html_url": "https://github.com/user/Repo1"
            },
            {
                "name": "Repo2",
                "full_name": "user/Repo2",
                "stargazers_count": 50,
                "forks_count": 10,
                "language": "TypeScript",
                "private": False,
                "html_url": "https://github.com/user/Repo2"
            },
            {
                "name": "Repo3",
                "full_name": "user/Repo3",
                "stargazers_count": 200,
                "forks_count": 30,
                "language": "Python",
                "private": False,
                "html_url": "https://github.com/user/Repo3"
            }
        ]

        result = analyze_repositories(sample_repos)

        self.assertEqual(result["total_repositories"], 3)
        self.assertEqual(result["total_stars"], 350)
        self.assertEqual(result["total_forks"], 65)
        self.assertEqual(result["top_language"], "Python")
        self.assertEqual(result["languages"], {"Python": 2, "TypeScript": 1})
        self.assertEqual(len(result["top_repositories"]), 3)
        # Verify sorted by stars descending
        self.assertEqual(result["top_repositories"][0]["name"], "Repo3")
        self.assertEqual(result["top_repositories"][0]["stars"], 200)

    def test_analyze_contributors(self):
        sample_contributors = [
            {"login": "alice", "contributions": 50},
            {"login": "bob", "contributions": 30}
        ]

        result = analyze_contributors(sample_contributors)

        self.assertEqual(result["total_contributors"], 2)
        self.assertEqual(result["total_contributions"], 80)
        self.assertEqual(len(result["top"]), 2)
        self.assertEqual(result["top_contributor"], {"username": "alice", "contributions": 50})

    def test_analyze_commits(self):
        sample_commits = [
            {
                "commit": {
                    "author": {"name": "Alice", "date": "2026-09-01T12:00:00Z"},
                    "message": "feat: initial commit"
                }
            },
            {
                "commit": {
                    "author": {"name": "Alice", "date": "2026-09-15T12:00:00Z"},
                    "message": "fix: bugfix"
                }
            },
            {
                "commit": {
                    "author": {"name": "Bob", "date": "2026-10-01T12:00:00Z"},
                    "message": "docs: update readme"
                }
            }
        ]

        result = analyze_commits(sample_commits)

        self.assertEqual(result["total_commits"], 3)
        self.assertEqual(result["authors_count"], 2)
        self.assertEqual(result["commits_by_author"], {"Alice": 2, "Bob": 1})
        self.assertEqual(result["commits_by_month"], {"2026-09": 2, "2026-10": 1})
        self.assertEqual(result["top_commit_author"], {"name": "Alice", "commits": 2})

    def test_analyze_engineering_health_contract(self):
        sample_evidence = {
            "repository": {
                "name": "sample",
                "full_name": "owner/sample",
                "default_branch": "main",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z"
            },
            "structure": {
                "total_files": 10,
                "total_directories": 2,
                "source_files": 5,
                "test_files": 2,
                "documentation_files": 1,
                "workflow_files": 1,
                "tree_truncated": False
            },
            "important_files": {"README.md": "README.md", "LICENSE": "LICENSE"},
            "workflows": [".github/workflows/ci.yml"],
            "repository_flags": {
                "has_readme": True,
                "has_license": True,
                "has_ci": True,
                "has_tests": True,
                "has_source_code": True,
                "has_docs": True
            }
        }

        health = analyze_engineering_health(sample_evidence)

        # Check top-level contract keys
        self.assertIn("score", health)
        self.assertEqual(health["max_score"], 100)
        self.assertIn("project_type", health)
        self.assertIn("categories", health)
        self.assertIn("confidence", health)
        self.assertIn("strengths", health)
        self.assertIn("concerns", health)
        self.assertIn("recommendations", health)

        # Verify exact 6 categories and max scores
        categories = health["categories"]
        self.assertEqual(len(categories), 6)
        self.assertEqual(categories["code_structure"]["max_score"], 25)
        self.assertEqual(categories["testing_reliability"]["max_score"], 20)
        self.assertEqual(categories["documentation"]["max_score"], 15)
        self.assertEqual(categories["security_dependencies"]["max_score"], 15)
        self.assertEqual(categories["maintenance"]["max_score"], 15)
        self.assertEqual(categories["collaboration"]["max_score"], 10)


if __name__ == "__main__":
    unittest.main()


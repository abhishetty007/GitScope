"""
GitScope project-type detection.

This module classifies repositories from observable repository
evidence. It does not score repository quality.
"""


PROJECT_TYPES = {
    "web_application": "Web Application",
    "backend_api": "Backend / API",
    "frontend_application": "Frontend Application",
    "library": "Library / Package",
    "cli_application": "CLI Application",
    "mobile_application": "Mobile Application",
    "machine_learning": "Machine Learning / Data",
    "data_project": "Data Project",
    "desktop_application": "Desktop Application",
    "unknown": "General / Unknown",
}


def _lower_paths(evidence):
    structure = evidence.get("structure", {})

    return [
        item.get("path", "").lower()
        for item in structure.get("files", [])
        if item.get("path")
    ]


def _file_names(evidence):
    return [
        path.split("/")[-1]
        for path in _lower_paths(evidence)
    ]


def _has_any(paths, values):
    return any(
        value in paths
        for value in values
    )


def _contains_any(paths, values):
    return any(
        any(value in path for value in values)
        for path in paths
    )


def _content_contains(evidence, terms):
    contents = evidence.get(
        "file_contents",
        {}
    )

    combined = "\n".join(
        (content or "").lower()
        for content in contents.values()
    )

    return any(
        term.lower() in combined
        for term in terms
    )


def detect_project_type(evidence):
    """
    Detect the most likely repository type from observable signals.

    Returns classification + confidence + supporting signals.
    """

    paths = _lower_paths(evidence)
    names = _file_names(evidence)

    scores = {
        project_type: 0
        for project_type in PROJECT_TYPES
        if project_type != "unknown"
    }

    signals = {
        project_type: []
        for project_type in scores
    }

    def add(project_type, points, signal):
        scores[project_type] += points
        signals[project_type].append(signal)

    # ---------------------------------------------------------
    # JavaScript / frontend / web
    # ---------------------------------------------------------

    if "package.json" in names:
        add(
            "web_application",
            2,
            "package.json detected"
        )

        add(
            "frontend_application",
            2,
            "package.json detected"
        )

    if _contains_any(
        paths,
        [
            "src/",
            "components/",
            "pages/",
            "app/",
        ]
    ):
        if _content_contains(
            evidence,
            [
                "react",
                "next.js",
                "vite",
                "vue",
                "svelte",
                "angular"
            ]
        ):
            add(
                "frontend_application",
                4,
                "Frontend framework indicators detected"
            )

            add(
                "web_application",
                4,
                "Web framework indicators detected"
            )

    if _has_any(
        names,
        [
            "vite.config.js",
            "vite.config.ts",
            "next.config.js",
            "next.config.mjs",
            "angular.json",
            "nuxt.config.ts",
        ]
    ):
        add(
            "frontend_application",
            4,
            "Frontend build configuration detected"
        )

        add(
            "web_application",
            3,
            "Web build configuration detected"
        )

    # ---------------------------------------------------------
    # Backend / API
    # ---------------------------------------------------------

    if _has_any(
        names,
        [
            "requirements.txt",
            "pyproject.toml",
            "pipfile",
            "pom.xml",
            "build.gradle",
            "go.mod",
            "cargo.toml",
        ]
    ):
        add(
            "backend_api",
            1,
            "Backend dependency/build manifest detected"
        )

    if _content_contains(
        evidence,
        [
            "flask",
            "fastapi",
            "django",
            "express",
            "nestjs",
            "spring boot",
            "gin-gonic",
            "actix-web",
        ]
    ):
        add(
            "backend_api",
            5,
            "Backend framework indicators detected"
        )

    if _contains_any(
        paths,
        [
            "api/",
            "routes/",
            "controllers/",
            "middleware/",
            "services/",
        ]
    ):
        add(
            "backend_api",
            2,
            "Backend-oriented directory structure detected"
        )

    # ---------------------------------------------------------
    # Machine learning / data
    # ---------------------------------------------------------

    if _contains_any(
        paths,
        [
            ".ipynb",
            "notebooks/",
            "models/",
            "datasets/",
            "data/",
        ]
    ):
        add(
            "machine_learning",
            3,
            "Notebook/model/data structure detected"
        )

        add(
            "data_project",
            2,
            "Data-oriented structure detected"
        )

    if _content_contains(
        evidence,
        [
            "scikit-learn",
            "tensorflow",
            "pytorch",
            "keras",
            "pandas",
            "numpy",
            "transformers",
        ]
    ):
        add(
            "machine_learning",
            4,
            "Machine-learning/data dependencies detected"
        )

    # ---------------------------------------------------------
    # Library / package
    # ---------------------------------------------------------

    if _has_any(
        names,
        [
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "package.json",
            "cargo.toml",
            "go.mod",
        ]
    ):
        add(
            "library",
            1,
            "Package/library manifest detected"
        )

    if _contains_any(
        paths,
        [
            "src/",
            "lib/",
            "include/",
        ]
    ):
        add(
            "library",
            2,
            "Reusable source structure detected"
        )

    if _content_contains(
        evidence,
        [
            "library",
            "package",
            "npm package",
            "pip package",
            "crate",
        ]
    ):
        add(
            "library",
            2,
            "Package-oriented documentation detected"
        )

    # ---------------------------------------------------------
    # CLI
    # ---------------------------------------------------------

    if _contains_any(
        paths,
        [
            "cli/",
            "commands/",
            "cmd/",
        ]
    ):
        add(
            "cli_application",
            4,
            "CLI-oriented directory structure detected"
        )

    if _content_contains(
        evidence,
        [
            "argparse",
            "click.command",
            "typer",
            "commander",
            "yargs",
            "cobra",
        ]
    ):
        add(
            "cli_application",
            4,
            "CLI framework indicators detected"
        )

    # ---------------------------------------------------------
    # Mobile
    # ---------------------------------------------------------

    if _has_any(
        names,
        [
            "androidmanifest.xml",
            "pubspec.yaml",
            "build.gradle",
        ]
    ):
        add(
            "mobile_application",
            3,
            "Mobile project configuration detected"
        )

    if _content_contains(
        evidence,
        [
            "react native",
            "flutter",
            "android sdk",
            "ios",
        ]
    ):
        add(
            "mobile_application",
            4,
            "Mobile framework indicators detected"
        )

    # ---------------------------------------------------------
    # Desktop
    # ---------------------------------------------------------

    if _content_contains(
        evidence,
        [
            "electron",
            "tauri",
            "tkinter",
            "pyqt",
            "wxpython",
        ]
    ):
        add(
            "desktop_application",
            4,
            "Desktop application framework detected"
        )

    # ---------------------------------------------------------
    # Determine winner
    # ---------------------------------------------------------

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    if not ranked or ranked[0][1] == 0:
        return {
            "type": "unknown",
            "label": PROJECT_TYPES["unknown"],
            "confidence": "LOW",
            "signals": [],
            "scores": scores,
        }

    selected_type, selected_score = ranked[0]

    second_score = (
        ranked[1][1]
        if len(ranked) > 1
        else 0
    )

    if selected_score >= 7 and (
        selected_score >= second_score + 2
    ):
        confidence = "HIGH"
    elif selected_score >= 4:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "type": selected_type,
        "label": PROJECT_TYPES[selected_type],
        "confidence": confidence,
        "signals": signals[selected_type][:8],
        "scores": scores,
    }
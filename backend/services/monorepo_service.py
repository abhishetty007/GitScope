"""Deterministic detection of explicit and structural workspace signals."""

import json
import re


def detect_monorepo(structure=None, file_contents=None):
    structure = structure or {}
    file_contents = file_contents or {}
    files = structure.get("files", []) or []
    paths = {item.get("path", "").lower() for item in files if isinstance(item, dict)}
    content_by_name = {path.lower(): content or "" for path, content in file_contents.items()}
    signals = []
    workspaces = []

    package_paths = sorted((p for p in content_by_name if p == "package.json" or p.endswith("/package.json")), key=lambda p: (p.count("/"), p))
    package_path = package_paths[0] if package_paths else None
    if package_path:
        try:
            package = json.loads(content_by_name[package_path])
            ws = package.get("workspaces", [])
            if isinstance(ws, dict):
                ws = ws.get("packages", [])
            if isinstance(ws, list) and ws:
                signals.append("package.json workspaces")
                workspaces.extend(str(item) for item in ws)
        except (ValueError, TypeError):
            pass

    for path in sorted(paths | set(content_by_name)):
        name = path.rsplit("/", 1)[-1]
        if name in {"pnpm-workspace.yaml", "pnpm-workspace.yml"}:
            content = content_by_name.get(path, "")
            members = re.findall(r"^\s*-\s*[\"']?([^\"'#\n]+)", content, re.M)
            signals.append("pnpm workspace")
            workspaces.extend(x.strip() for x in members)
        elif name == "lerna.json":
            try:
                data = json.loads(content_by_name.get(path, ""))
                members = data.get("packages", [])
                if members:
                    signals.append("lerna packages")
                    workspaces.extend(str(x) for x in members)
            except (ValueError, TypeError):
                pass
        elif name == "cargo.toml" and re.search(r"(?m)^\s*\[workspace\]\s*$", content_by_name.get(path, ""), re.I):
            signals.append("Cargo workspace")
            match = re.search(r"(?ms)^\[workspace\].*?^members\s*=\s*\[(.*?)\]", content_by_name[path], re.I)
            if match:
                workspaces.extend(re.findall(r"[\"']([^\"']+)[\"']", match.group(1)))
        elif name == "go.work" and content_by_name.get(path, "").lstrip().startswith("go "):
            signals.append("Go workspace")
            workspaces.extend(re.findall(r"(?m)^\s*\.\.?/[^\s)]+", content_by_name[path]))
        elif name in {"nx.json", "turbo.json", "rush.json"}:
            signals.append({"nx.json": "Nx workspace", "turbo.json": "Turborepo workspace", "rush.json": "Rush workspace"}[name])
            if name == "rush.json":
                try:
                    data = json.loads(content_by_name.get(path, ""))
                    workspaces.extend(p.get("packageName", p.get("projectFolder", "")) for p in data.get("projects", []) if isinstance(p, dict))
                except (ValueError, TypeError):
                    pass

    unique_workspaces = sorted(set(workspaces))
    explicit = bool(signals)
    # Multiple top-level ecosystem manifests or package-shaped directories
    # are weaker evidence, and are never inferred from a lone package.json.
    manifests = [p for p in paths if p.rsplit("/", 1)[-1] in {"package.json", "cargo.toml", "go.mod", "pyproject.toml", "pom.xml"}]
    weak = not explicit and (len(manifests) >= 3 or sum("/" in p and p.endswith(("/package.json", "/go.mod", "/cargo.toml")) for p in paths) >= 2)
    kind = signals[0] if signals else ("multi-package structure" if weak else None)
    return {
        "is_monorepo": explicit or weak,
        "kind": kind,
        "workspaces": unique_workspaces,
        "confidence": "HIGH" if explicit else ("MEDIUM" if weak else "LOW"),
        "signals": sorted(signals) if explicit else (["multiple package manifests"] if weak else []),
        "explicit": explicit,
    }

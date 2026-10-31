#!/usr/bin/env python3
"""Check a project rendered from template parts.

Usage:
    python3 scripts/check_project.py DIR --expect agent,tab,panel

`--expect` names what the project must contribute; anything not named must be absent.
`zelos extensions package` validates the manifest itself; these checks cover what it does not:
the contributions match the selection, [package] paths has no duplicates, an agent runtime has
its pyproject.toml, each document's assets exist (the web parts ship a built dist/), no fragment
is left, every JSON and TOML file parses, Dependabot watches what exists and the Justfile parses.
Standard library only (Python 3.11+).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

CONTRIBUTIONS = ("agent", "tab", "panel")
ASSET_REF_RE = re.compile(r'(?:src|href)="(\.{1,2}/[^"]+)"')
SKIP_DIRS = {"node_modules", ".git", ".venv"}
# What each Dependabot ecosystem reads in its directory; a directory without it fails every run.
DEPENDABOT_MANIFESTS = {
    "uv": "pyproject.toml",
    "npm": "package.json",
    "github-actions": ".github/workflows",
}
DEPENDABOT_ENTRY_RE = re.compile(
    r'-\s+package-ecosystem:\s*"?([\w-]+)"?\s*\n\s+directory:\s*"?([^"\n]+)"?'
)


def check(project: Path, expect: set[str]) -> list[str]:
    try:
        manifest = tomllib.loads((project / "extension.toml").read_text())
    except (OSError, tomllib.TOMLDecodeError) as error:
        return [f"extension.toml: {error}"]
    app = manifest.get("app") or {}
    tab = app.get("tab")
    panels = app.get("panels", [])
    tab_entry = tab.get("entry") if isinstance(tab, dict) else tab
    package_paths = manifest.get("package", {}).get("paths", [])
    has = {"agent": "agent" in manifest, "tab": tab is not None, "panel": bool(panels)}
    errors = _check_contributions(expect, has)
    if len(package_paths) != len(set(package_paths)):
        errors.append(f"[package] paths has duplicates: {package_paths}")
    if has["agent"] and not (project / "pyproject.toml").is_file():
        errors.append("agent runtime without pyproject.toml")
    errors += _check_assets(project, "[app] tab", tab_entry)
    for panel in panels:
        label = f"panel {panel.get('id')!r} entry"
        errors += _check_assets(project, label, panel.get("entry"))
    return [
        *errors,
        *_check_web(project, has),
        *_check_files(project),
        *_check_dependabot(project, has),
        *_check_justfile(project),
    ]


def _check_contributions(expect: set[str], has: dict[str, bool]) -> list[str]:
    errors = []
    for name in CONTRIBUTIONS:
        if has[name] != (name in expect):
            state = "missing" if name in expect else "unexpected"
            errors.append(f"extension.toml: {state} contribution {name!r}")
    return errors


def _check_assets(project: Path, label: str, path: str | None) -> list[str]:
    """Every asset an HTML document loads exists; the CLI checks the document itself."""
    document = project / path if path else None
    if document is None or document.suffix != ".html" or not document.is_file():
        return []
    return [
        f"{label} {path!r} references missing {ref!r}"
        for ref in ASSET_REF_RE.findall(document.read_text())
        if not (document.parent / ref).is_file()
    ]


def _check_web(project: Path, has: dict[str, bool]) -> list[str]:
    errors = []
    has_web = (project / "web/package.json").is_file()
    if has_web != (has["tab"] or has["panel"]):
        errors.append(
            f"web/package.json present={has_web} does not match the tab/panel selection"
        )
    if (project / "web/src/tab").exists() != has["tab"]:
        errors.append("web/src/tab must exist exactly when the project has a tab")
    return errors


def _check_files(project: Path) -> list[str]:
    """No fragment is left behind, and every JSON and TOML file parses."""
    errors = []
    for path in sorted(project.rglob("*")):
        relative = path.relative_to(project)
        if any(part in SKIP_DIRS for part in relative.parts) or not path.is_file():
            continue
        if path.name.endswith(".part"):
            errors.append(f"{relative}: fragment left in the rendered project")
        try:
            if path.suffix == ".json":
                json.loads(path.read_text())
            elif path.suffix == ".toml":
                tomllib.loads(path.read_text())
        except (ValueError, tomllib.TOMLDecodeError) as error:
            errors.append(f"{relative}: does not parse: {error}")
    return errors


def _check_dependabot(project: Path, has: dict[str, bool]) -> list[str]:
    """Dependabot watches exactly what the project has: a directory without its manifest fails
    every scheduled run, and an ecosystem the project uses must be watched."""
    path = project / ".github/dependabot.yml"
    if not path.is_file():
        return [".github/dependabot.yml: missing"]
    text = path.read_text()
    errors = []
    if "labels:" in text:
        errors.append(
            ".github/dependabot.yml: a label the repository may not have makes every run warn"
        )
    entries = DEPENDABOT_ENTRY_RE.findall(text)
    for ecosystem, directory in entries:
        manifest = DEPENDABOT_MANIFESTS.get(ecosystem)
        if manifest is None:
            errors.append(f".github/dependabot.yml: unknown ecosystem {ecosystem!r}")
            continue
        if not (project / directory.strip("/") / manifest).exists():
            errors.append(
                f".github/dependabot.yml: {ecosystem} in {directory} has no {manifest}"
            )
    watched = {ecosystem for ecosystem, _ in entries}
    wanted = {"github-actions"}
    if (project / "pyproject.toml").is_file():
        wanted.add("uv")
    if has["tab"] or has["panel"]:
        wanted.add("npm")
    for ecosystem in sorted(wanted - watched):
        errors.append(f".github/dependabot.yml: {ecosystem} is not watched")
    return errors


def _check_justfile(project: Path) -> list[str]:
    just = shutil.which("just")
    if not just:
        return []
    result = subprocess.run(
        [just, "--justfile", str(project / "Justfile"), "--summary"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return [f"Justfile does not parse: {result.stderr.strip()}"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--expect", required=True, help="comma list of agent, tab, panel"
    )
    args = parser.parse_args(argv)
    expect = {name.strip() for name in args.expect.split(",") if name.strip()}
    unknown = expect - set(CONTRIBUTIONS)
    if unknown:
        parser.error(f"unknown contribution(s): {', '.join(sorted(unknown))}")
    errors = check(args.project, expect)
    for error in errors:
        print(f"  ✗ {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"  ✓ {args.project} ({', '.join(sorted(expect))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Check a project rendered from template parts.

Usage:
    python3 scripts/check_project.py DIR --expect agent,tab,panel

`--expect` names what the project must contribute; anything not named must be absent.
The checks mirror the manifest rules a rendered project has to satisfy without a build:
extension.toml parses, uses the new form ([agent] and/or [app], never [host] or [runtime]),
every [package] path and every manifest path exists, with the assets each document loads (the
web parts ship a built dist/), and a manifest with panels requires Zelos >=26.0.10. Standard library only (Python 3.11+).
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
PANELS_ZELOS_VERSION = ">=26.0.10"
LEGACY_TOP_LEVEL = ("host", "runtime", "workdir", "targets", "env", "stop")
PANEL_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ASSET_REF_RE = re.compile(r'(?:src|href)="(\.{1,2}/[^"]+)"')
SKIP_DIRS = {"node_modules", ".git", ".venv"}


def _covered(path: str, package_paths: list[str]) -> bool:
    return any(Path(path).is_relative_to(p) for p in package_paths)


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
    return [
        *_check_manifest(manifest, expect, has),
        *_check_package_paths(project, package_paths),
        *_check_agent(project, manifest.get("agent")),
        *_check_path(project, package_paths, "[app] tab", tab_entry),
        *_check_panels(project, package_paths, panels, manifest),
        *_check_web(project, has),
        *_check_files(project),
        *_check_justfile(project),
    ]


def _check_manifest(
    manifest: dict, expect: set[str], has: dict[str, bool]
) -> list[str]:
    errors = [
        f"extension.toml: legacy top-level key {key!r} is not allowed"
        for key in LEGACY_TOP_LEVEL
        if key in manifest
    ]
    for name in CONTRIBUTIONS:
        if has[name] != (name in expect):
            state = "missing" if name in expect else "unexpected"
            errors.append(f"extension.toml: {state} contribution {name!r}")
    if "agent" not in manifest and "app" not in manifest:
        errors.append("extension.toml: must declare [agent], [app], or both")
    return errors


def _check_package_paths(project: Path, package_paths: list[str]) -> list[str]:
    errors = []
    if len(package_paths) != len(set(package_paths)):
        errors.append(f"[package] paths has duplicates: {package_paths}")
    for path in package_paths:
        if not (project / path).exists():
            errors.append(f"[package] paths entry {path!r} does not exist")
    return errors


def _check_path(
    project: Path, package_paths: list[str], label: str, path: str | None
) -> list[str]:
    """A manifest path is present, and [package] ships it."""
    errors = []
    if path is None:
        return errors
    document = project / path
    if not document.is_file():
        errors.append(f"{label} {path!r} does not exist")
    elif document.suffix == ".html":
        for ref in ASSET_REF_RE.findall(document.read_text()):
            if not (document.parent / ref).is_file():
                errors.append(f"{label} {path!r} references missing {ref!r}")
    if package_paths and not _covered(path, package_paths):
        errors.append(f"{label} {path!r} is not covered by [package] paths")
    return errors


def _check_agent(project: Path, agent: dict | None) -> list[str]:
    errors = []
    if agent is None:
        return errors
    if agent.get("runtime") != "python":
        errors.append('[agent] runtime must be "python"')
    if not (project / agent.get("entry", "")).is_file():
        errors.append(f"[agent] entry {agent.get('entry')!r} does not exist")
    if not re.fullmatch(r"\d+\.\d+", str(agent.get("python_version", ""))):
        errors.append("[agent] python_version must look like 3.11")
    if not (project / "pyproject.toml").is_file():
        errors.append("agent runtime without pyproject.toml")
    return errors


def _check_panels(
    project: Path, package_paths: list[str], panels: list[dict], manifest: dict
) -> list[str]:
    errors = []
    seen_ids: set[str] = set()
    for panel in panels:
        panel_id = panel.get("id", "")
        if panel_id in seen_ids:
            errors.append(f"duplicate panel id {panel_id!r}")
        seen_ids.add(panel_id)
        errors += _check_panel(panel_id, panel)
        for field in ("entry", "icon", "options_schema"):
            label = f"panel {panel_id!r} {field}"
            errors += _check_path(project, package_paths, label, panel.get(field))
    if panels and manifest.get("zelos", {}).get("version") != PANELS_ZELOS_VERSION:
        errors.append(
            f'[[app.panels]] requires [zelos] version = "{PANELS_ZELOS_VERSION}"'
        )
    return errors


def _check_panel(panel_id: str, panel: dict) -> list[str]:
    errors = []
    if not PANEL_ID_RE.match(panel_id) or len(panel_id) > 40:
        errors.append(f"panel id {panel_id!r} is invalid")
    if not 1 <= len(panel.get("name", "")) <= 60:
        errors.append(f"panel {panel_id!r}: name must be 1 to 60 characters")
    if not 0.5 <= float(panel.get("default_height", 2)) <= 4.0:
        errors.append(f"panel {panel_id!r}: default_height must be in 0.5..4.0")
    if panel.get("binds", "any") not in ("any", "accepted"):
        errors.append(f"panel {panel_id!r}: binds must be 'any' or 'accepted'")
    if "entry" not in panel:
        errors.append(f"panel {panel_id!r}: entry is required")
    return errors


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

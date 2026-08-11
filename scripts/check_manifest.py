#!/usr/bin/env python3
"""Check the plugin manifests against each other and against `skills/`.

The repository is installable as a Claude Code plugin, which means the same
facts are written down twice: `.claude-plugin/plugin.json` describes the plugin,
and `.claude-plugin/marketplace.json` advertises it. The name, the description
and the keyword list are duplicated verbatim across the two, so an edit to one
drifts silently from the other — nothing at install time complains, the
marketplace listing simply stops matching the plugin it installs.

The other gates read `skills/`; this one reads the packaging around it. It
checks that both manifests parse, that the fields a reader depends on are
present, that the two agree wherever they overlap, and that the `source` a
marketplace entry points at is a directory that actually ships skills.

`license` is checked against the same value every SKILL.md carries: a skill
copied out of the plugin and a skill copied out of a folder should not disagree
about their terms.

Usage:  python3 scripts/check_manifest.py [repo_root]
Exit:   0 clean, 1 violations found.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MANIFEST_DIR = ".claude-plugin"
PLUGIN = "plugin.json"
MARKETPLACE = "marketplace.json"

# Matches lint_skills.REQUIRED_LICENSE: skills travel one folder at a time, and
# the plugin is just another way of copying them out.
REQUIRED_LICENSE = "MIT"

PLUGIN_REQUIRED = ("name", "version", "description", "license")
MARKETPLACE_REQUIRED = ("name", "owner", "plugins")

# `x.y.z`, optionally with a prerelease or build suffix.
SEMVER = re.compile(r"\A\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?\Z")

# Duplicated verbatim between the two manifests, so they must agree.
SHARED_FIELDS = ("description", "keywords")


def load(path: Path) -> tuple[dict, list[str]]:
    """Read one manifest, reporting what would break a reader rather than raising."""
    rel = f"{MANIFEST_DIR}/{path.name}"
    if not path.is_file():
        return {}, [f"missing {rel}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"{rel} is not valid JSON: {exc.msg} (line {exc.lineno})"]
    if not isinstance(data, dict):
        return {}, [f"{rel} is not a JSON object"]
    return data, []


def check_required(data: dict, fields: tuple[str, ...], rel: str) -> list[str]:
    problems = []
    for field in fields:
        value = data.get(field)
        if value is None or (isinstance(value, (str, list, dict)) and not value):
            problems.append(f"{rel}: missing `{field}`")
    return problems


def find_entry(marketplace: dict, name: str) -> tuple[dict | None, list[str]]:
    """The marketplace entry advertising this plugin, if it is there at all."""
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        return None, [f"{MANIFEST_DIR}/{MARKETPLACE}: `plugins` is not a list"]
    entries = [p for p in plugins if isinstance(p, dict) and p.get("name") == name]
    if not entries:
        return None, [f"{MANIFEST_DIR}/{MARKETPLACE}: lists no plugin named {name!r}"]
    if len(entries) > 1:
        return None, [f"{MANIFEST_DIR}/{MARKETPLACE}: lists {name!r} more than once"]
    return entries[0], []


def check_source(entry: dict, root: Path) -> list[str]:
    """A marketplace entry points at a directory; that directory must ship skills."""
    source = entry.get("source")
    if not isinstance(source, str) or not source:
        return [f"{MANIFEST_DIR}/{MARKETPLACE}: entry has no `source`"]
    if "://" in source:
        return []  # a remote source is not ours to resolve

    resolved = (root / source).resolve()
    if not resolved.is_dir():
        return [f"{MANIFEST_DIR}/{MARKETPLACE}: `source` {source!r} does not resolve to a directory"]

    skills = resolved / "skills"
    if not skills.is_dir() or not any(d.is_dir() for d in skills.iterdir()):
        return [f"{MANIFEST_DIR}/{MARKETPLACE}: `source` {source!r} contains no skills"]
    return []


def check(root: Path) -> list[str]:
    plugin, problems = load(root / MANIFEST_DIR / PLUGIN)
    marketplace, market_problems = load(root / MANIFEST_DIR / MARKETPLACE)
    problems += market_problems
    if not plugin or not marketplace:
        return problems  # nothing to cross-check against

    problems += check_required(plugin, PLUGIN_REQUIRED, f"{MANIFEST_DIR}/{PLUGIN}")
    problems += check_required(marketplace, MARKETPLACE_REQUIRED, f"{MANIFEST_DIR}/{MARKETPLACE}")

    version = plugin.get("version")
    if isinstance(version, str) and version and not SEMVER.match(version):
        problems.append(
            f"{MANIFEST_DIR}/{PLUGIN}: `version` is {version!r}, not a semantic version"
        )

    license_field = plugin.get("license")
    if license_field is not None and str(license_field).strip() != REQUIRED_LICENSE:
        problems.append(
            f"{MANIFEST_DIR}/{PLUGIN}: `license` is {license_field!r}; skills in this "
            f"repository ship {REQUIRED_LICENSE!r}"
        )

    name = plugin.get("name")
    if not isinstance(name, str) or not name:
        return problems  # without a name there is no entry to look for

    entry, entry_problems = find_entry(marketplace, name)
    problems += entry_problems
    if entry is None:
        return problems

    for field in SHARED_FIELDS:
        if plugin.get(field) != entry.get(field):
            problems.append(
                f"the manifests disagree on `{field}`: {PLUGIN} has "
                f"{plugin.get(field)!r}, {MARKETPLACE} has {entry.get(field)!r}"
            )

    problems += check_source(entry, root)
    return problems


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    if not root.is_dir():
        print(f"error: no such directory: {root}", file=sys.stderr)
        return 1

    problems = check(root)
    if problems:
        print(f"FAIL {MANIFEST_DIR}")
        for p in problems:
            print(f"       - {p}")
        print()
        print("The plugin manifests disagree with each other or with skills/.")
        print("See the 'Packaging' section of CONTRIBUTING.md.")
        return 1

    print(f"ok   {MANIFEST_DIR}/{PLUGIN}")
    print(f"ok   {MANIFEST_DIR}/{MARKETPLACE}")
    print()
    print("The plugin manifests agree with each other and with skills/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

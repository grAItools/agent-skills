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
present and hold the type that reader expects, that the two agree wherever they
overlap, and that the `source` a marketplace entry points at is a directory that
actually ships a skill.

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

# Matches lint_skills.CANONICAL_SKILL_FILE: the file a reader opens to find a
# skill, and so the only evidence that a directory ships one.
CANONICAL_SKILL_FILE = "SKILL.md"

# Each field with the JSON type a reader expects to find in it. The type is part
# of the contract, not a detail: a manifest whose `name` is a number has no name
# as far as a reader is concerned, and checking only for emptiness would let it
# through and then skip the cross-checks that depend on it.
PLUGIN_REQUIRED = (("name", str), ("version", str), ("description", str), ("license", str))
MARKETPLACE_REQUIRED = (("name", str), ("owner", (dict, str)), ("plugins", list))

# Absent is fine — these are conveniences. Present and the wrong shape is not.
# `[str]` means a list whose every item is a string; see check_value.
PLUGIN_OPTIONAL = (("keywords", [str]),)
ENTRY_OPTIONAL = (("description", str), ("keywords", [str]))

# The expression published at semver.org, which is the only thing worth trusting
# here. The shorter `\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?` this replaces was
# wrong in both directions: it rejected `2.1.0-rc.1+build.7`, which is valid and
# carries both a prerelease and build metadata, while accepting `2.1.0-01`, whose
# leading zero is not.
SEMVER = re.compile(
    r"\A(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-(?:(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?:[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?\Z"
)

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


def type_name(expected: type | tuple[type, ...]) -> str:
    if isinstance(expected, tuple):
        return " or ".join(t.__name__ for t in expected)
    return expected.__name__


def check_value(value: object, field: str, expected: object, rel: str) -> list[str]:
    """One field's type, then its emptiness — an empty value is no value.

    `expected` is a type, a tuple of acceptable types, or a one-element list
    naming the type of every item (`[str]` for a keyword list). The item form is
    spelled out per field rather than applied to any list, because `plugins` is a
    list of objects and would fail a blanket list-of-strings rule.
    """
    if isinstance(expected, list):
        item_type, = expected
        if not isinstance(value, list):
            return [f"{rel}: `{field}` is {type(value).__name__}, expected list"]
        if not value:
            return [f"{rel}: empty `{field}`"]
        if any(not isinstance(item, item_type) for item in value):
            return [f"{rel}: `{field}` has entries that are not of type "
                    f"{item_type.__name__}"]
        return []

    if not isinstance(value, expected):
        return [f"{rel}: `{field}` is {type(value).__name__}, expected {type_name(expected)}"]
    # Stripped, because `"   "` is truthy and carries nothing a reader can use.
    if isinstance(value, str) and not value.strip():
        return [f"{rel}: empty `{field}`"]
    if isinstance(value, (list, dict)) and not value:
        return [f"{rel}: empty `{field}`"]
    return []


def check_fields(data: dict, required: tuple[tuple[str, object], ...],
                 optional: tuple[tuple[str, object], ...], rel: str) -> list[str]:
    """Presence and type for the required fields, type alone for the optional."""
    problems = []
    for field, expected in required:
        if data.get(field) is None:
            problems.append(f"{rel}: missing `{field}`")
        else:
            problems += check_value(data[field], field, expected, rel)
    for field, expected in optional:
        if data.get(field) is not None:
            problems += check_value(data[field], field, expected, rel)
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


def ships_a_skill(skills_dir: Path) -> bool:
    """Whether any child directory holds a skill file a reader could load.

    A bare directory is not a skill. Counting subdirectories would pass a
    `skills/placeholder/` left behind by a restructure, which installs nothing.
    Matched case-insensitively: whether the file is named canonically is
    lint_skills' judgement to make, not this gate's.
    """
    for child in skills_dir.iterdir():
        if not child.is_dir():
            continue
        if any(f.is_file() and f.name.lower() == CANONICAL_SKILL_FILE.lower()
               for f in child.iterdir()):
            return True
    return False


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
    if not skills.is_dir() or not ships_a_skill(skills):
        return [f"{MANIFEST_DIR}/{MARKETPLACE}: `source` {source!r} contains no skills"]
    return []


def check(root: Path) -> list[str]:
    plugin, plugin_problems = load(root / MANIFEST_DIR / PLUGIN)
    marketplace, market_problems = load(root / MANIFEST_DIR / MARKETPLACE)
    problems = plugin_problems + market_problems
    # Only when loading itself failed. `{}` is valid JSON and a mapping, so it
    # loads with nothing to report; treating a falsy mapping as unloadable
    # returned before any field was checked and called an empty manifest clean.
    if plugin_problems or market_problems:
        return problems  # nothing trustworthy to cross-check against

    problems += check_fields(plugin, PLUGIN_REQUIRED, PLUGIN_OPTIONAL,
                             f"{MANIFEST_DIR}/{PLUGIN}")
    problems += check_fields(marketplace, MARKETPLACE_REQUIRED, (),
                             f"{MANIFEST_DIR}/{MARKETPLACE}")

    version = plugin.get("version")
    if isinstance(version, str) and version and not SEMVER.match(version):
        problems.append(
            f"{MANIFEST_DIR}/{PLUGIN}: `version` is {version!r}, not a semantic version"
        )

    # Only when it is a string: a wrong type is already reported above, and
    # `str(...)` on a number would report a second, more confusing problem.
    license_field = plugin.get("license")
    if isinstance(license_field, str) and license_field.strip() != REQUIRED_LICENSE:
        problems.append(
            f"{MANIFEST_DIR}/{PLUGIN}: `license` is {license_field!r}; skills in this "
            f"repository ship {REQUIRED_LICENSE!r}"
        )

    name = plugin.get("name")
    if not isinstance(name, str) or not name:
        # Nothing to look the entry up by. The field check above has already
        # recorded why, so this returns a failure rather than a clean run.
        return problems

    entry, entry_problems = find_entry(marketplace, name)
    problems += entry_problems
    if entry is None:
        return problems

    problems += check_fields(entry, (), ENTRY_OPTIONAL, f"{MANIFEST_DIR}/{MARKETPLACE}")

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

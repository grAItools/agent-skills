#!/usr/bin/env python3
"""Lint SKILL.md frontmatter against the contract in CONTRIBUTING.md.

`skills-ref validate` checks the open format (name/description syntax, length
limits). This checks the *house rules* on top of it: that every skill carries a
license, and that every description states a capability, a trigger, and a
boundary, with no trigger broad enough to fire on any coding session.

Deliberately mechanical. It checks structure, not meaning: whether the clauses
are present, not whether they are good. Judging whether a trigger is drawn in
the right place is a review job, not a CI job — a substring check can always be
evaded by paraphrase, so treat a clean run as the floor, not the bar.

Frontmatter is parsed with a real YAML parser so that quoted scalars, block
scalars, and comments are read the way hosts read them — a regex reader would
reject valid frontmatter and, worse, pass judgement on a value no reader will
ever see. (`skills-ref` parses with strictyaml, a stricter subset; anything it
rejects and PyYAML accepts fails the validator step with its own message.)

Usage:  python3 scripts/lint_skills.py [skills_dir]
Exit:   0 clean, 1 violations found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environment problem, not a lint failure
    sys.exit("error: PyYAML is required to run this linter: pip install pyyaml")

# Unbounded quantifiers over ordinary activity. A trigger containing one of
# these fires on essentially every session, so the skill co-fires with every
# other code skill. Matched against the trigger clause only — the boundary
# clause is *supposed* to speak in absolutes ("do not use on every edit").
UNIVERSAL_TRIGGERS = [
    (r"\bany\s+time\b", "any time ..."),
    (r"\bevery\s+time\b", "every time ..."),
    (r"\bwhenever\s+you\b", "whenever you ..."),
    (r"\bfor\s+any\s+reason\b", "for any reason"),
    (r"\balways\b", "always"),
    (
        r"\b(any|all|every)\s+"
        r"(code|change|changes|edit|edits|task|tasks|file|files|work|session|sessions)\b",
        "any/all/every <ordinary activity>",
    ),
]

MAX_DESCRIPTION = 1024  # open format hard limit
MIN_DESCRIPTION = 120   # a 3-part description is not achievable below this

REQUIRED_LICENSE = "MIT"

CANONICAL_SKILL_FILE = "SKILL.md"

# The frontmatter block: `---` on its own line, content, `---` on its own line.
FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)

TRIGGER = re.compile(r"\buse when\b", re.I)
BOUNDARY = re.compile(r"\bdo not use\b", re.I)


def find_skill_file(skill_dir: Path) -> Path | None:
    """Locate the skill file, accepting the case variants readers accept."""
    for entry in sorted(skill_dir.iterdir()):
        if entry.is_file() and entry.name.lower() == CANONICAL_SKILL_FILE.lower():
            return entry
    return None


def read_frontmatter(text: str) -> tuple[dict, list[str]]:
    """Parse the YAML frontmatter block, reporting what would break readers."""
    m = FRONTMATTER.match(text)
    if not m:
        return {}, ["no YAML frontmatter block (`---` fenced) at the top of the file"]

    block = m.group(1)
    problems: list[str] = []

    # The reference validator closes the block at the first `---` *anywhere*,
    # not just at the start of a line, so a `---` inside a value truncates the
    # frontmatter it sees — silently dropping later fields and half a
    # description. Ban the sequence rather than depend on parser agreement.
    if "---" in block:
        problems.append(
            "frontmatter contains '---' inside a value; readers that split on "
            "the marker will truncate the frontmatter there — use an em dash"
        )

    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        detail = " ".join(str(exc).split())
        return {}, problems + [f"frontmatter is not valid YAML: {detail}"]

    if data is None:
        return {}, problems + ["frontmatter is empty"]
    if not isinstance(data, dict):
        return {}, problems + ["frontmatter is not a mapping of fields"]
    return data, problems


def check(skill_dir: Path) -> list[str]:
    md = find_skill_file(skill_dir)
    if md is None:
        return [f"no {CANONICAL_SKILL_FILE} in {skill_dir}"]

    problems: list[str] = []
    if md.name != CANONICAL_SKILL_FILE:
        problems.append(f"skill file is named {md.name!r}; use {CANONICAL_SKILL_FILE!r}")

    fm, fm_problems = read_frontmatter(md.read_text(encoding="utf-8"))
    problems += fm_problems

    name = fm.get("name")
    if not name:
        problems.append("missing `name`")
    elif name != skill_dir.name:
        problems.append(f"`name` is {name!r} but directory is {skill_dir.name!r}")

    # Skills get copied out of this repository one folder at a time, so the
    # repository LICENSE does not travel with them.
    license_field = fm.get("license")
    if not license_field:
        problems.append(f"missing `license`; skills in this repository ship `license: {REQUIRED_LICENSE}`")
    elif str(license_field).strip() != REQUIRED_LICENSE:
        problems.append(
            f"`license` is {license_field!r}; skills in this repository ship {REQUIRED_LICENSE!r}"
        )

    desc = fm.get("description")
    if desc is None:
        return problems + ["missing `description`"]
    if not isinstance(desc, str):
        return problems + [f"`description` is {type(desc).__name__}, not a string"]
    desc = desc.strip()
    if not desc:
        return problems + ["empty `description`"]

    # --- length -----------------------------------------------------------
    if len(desc) > MAX_DESCRIPTION:
        problems.append(f"description is {len(desc)} chars (limit {MAX_DESCRIPTION})")
    if len(desc) < MIN_DESCRIPTION:
        problems.append(
            f"description is {len(desc)} chars (minimum {MIN_DESCRIPTION}); too "
            "short to carry capability + trigger + boundary"
        )

    # --- part 1: capability, stated first ---------------------------------
    if TRIGGER.match(desc):
        problems.append(
            "description opens with 'Use when'; lead with what the skill does, "
            "since hosts truncate descriptions from the end"
        )

    # --- parts 2 and 3: trigger, then boundary ----------------------------
    # Split at the boundary first: "Do not use when ..." contains "use when",
    # so searching the whole description would accept a skill that has only a
    # boundary and no trigger at all.
    boundary = BOUNDARY.search(desc)
    head = desc[: boundary.start()] if boundary else desc
    trigger = TRIGGER.search(head)

    if not trigger:
        problems.append(
            "description has no 'Use when ...' trigger clause ahead of its "
            "'Do not use ...' boundary"
        )
    if not boundary:
        problems.append(
            "description has no 'Do not use ...' boundary clause; name the "
            "neighbouring skill that owns the excluded case"
        )

    # --- disjointness ------------------------------------------------------
    if trigger:
        trigger_clause = head[trigger.start():]
        for pattern, label in UNIVERSAL_TRIGGERS:
            if re.search(pattern, trigger_clause, re.I):
                problems.append(
                    f"trigger says {label!r}, which matches nearly any task; "
                    "narrow it to observable symptoms"
                )

    return problems


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "skills")
    if not root.is_dir():
        print(f"error: no such directory: {root}", file=sys.stderr)
        return 1

    dirs = sorted(d for d in root.iterdir() if d.is_dir())
    if not dirs:
        print(f"error: no skills found in {root}", file=sys.stderr)
        return 1

    failed = 0
    for d in dirs:
        problems = check(d)
        if problems:
            failed += 1
            print(f"FAIL {d.name}")
            for p in problems:
                print(f"       - {p}")
        else:
            print(f"ok   {d.name}")

    print()
    if failed:
        print(f"{failed} of {len(dirs)} skills failed the description contract.")
        print("See the 'Frontmatter' and 'A precise trigger' sections of CONTRIBUTING.md.")
        return 1
    print(f"All {len(dirs)} skills satisfy the description contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

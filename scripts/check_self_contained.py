#!/usr/bin/env python3
"""Check that every skill folder stands alone.

The README tells people to copy a single folder into their agent's skills
directory, so a link that points outside the folder — or at a file that isn't
there — arrives broken. This walks every markdown file in every skill folder,
not just `SKILL.md`, since supporting files are linked from it and travel with
it.

Link forms understood: inline `[text](target)`, reference definitions
`[label]: target`, and raw HTML `href=`/`src=` attributes. Fenced and inline
code is skipped, so a skill can show a forbidden link as an example without
failing its own check.

Usage:  python3 scripts/check_self_contained.py [skills_dir]
Exit:   0 clean, 1 violations found.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

FENCE = re.compile(r"^(?P<indent>[ \t]*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
INLINE_CODE = re.compile(r"`[^`\n]*`")

INLINE_LINK = re.compile(r"\]\(\s*([^)]*)\)")
REFERENCE_LINK = re.compile(r"^[ \t]{0,3}\[[^\]]+\]:[ \t]*(\S+)", re.M)
HTML_ATTR = re.compile(r"""\b(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.I)

# A URI scheme: `https://`, but also `mailto:` and any casing of either.
SCHEME = re.compile(r"\A[A-Za-z][A-Za-z0-9+.\-]*:")


def strip_code(text: str) -> str:
    """Blank out fenced blocks and inline spans, preserving line numbering."""
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        m = FENCE.match(line)
        if fence is None:
            if m and m.group("info").find("`") == -1:
                fence = m.group("fence")[0] * len(m.group("fence"))
                out.append("")
                continue
            out.append(INLINE_CODE.sub(" ", line))
        else:
            # A closing fence is the same character, at least as long, nothing else.
            if m and m.group("fence")[0] == fence[0] and len(m.group("fence")) >= len(fence) \
                    and not m.group("info").strip():
                fence = None
            out.append("")
    return "\n".join(out)


def clean_target(raw: str) -> str | None:
    """Reduce a raw markdown destination to the path it refers to."""
    target = raw.strip()
    if target.startswith("<"):
        target = target[1:].split(">", 1)[0]
    else:
        # Everything after the first run of whitespace is the optional title.
        target = target.split()[0] if target.split() else ""
    target = target.split("#", 1)[0]  # drop the fragment
    if not target:
        return None  # same-document anchor, nothing to resolve
    return unquote(target)


def targets_in(text: str) -> list[tuple[int, str]]:
    """Every link destination in the file, with the line it appears on."""
    stripped = strip_code(text)
    found: list[tuple[int, str]] = []
    for pattern in (INLINE_LINK, REFERENCE_LINK, HTML_ATTR):
        for m in pattern.finditer(stripped):
            raw = next((g for g in m.groups() if g is not None), "")
            line = stripped.count("\n", 0, m.start()) + 1
            found.append((line, raw))
    return sorted(found)


def check_file(md: Path, skill_dir: Path) -> list[str]:
    problems: list[str] = []
    root = skill_dir.resolve()
    for line, raw in targets_in(md.read_text(encoding="utf-8")):
        # Cleaned first: the destination may be wrapped in angle brackets
        # (`[x](<https://a.com/b>)`), and the scheme only shows once those and
        # any title are off.
        target = clean_target(raw)
        if target is None:
            continue
        if SCHEME.match(target) or target.startswith("//"):
            continue  # external URL, mailto:, protocol-relative
        where = f"{md}:{line}"
        if os.path.isabs(target) or target.startswith("/"):
            problems.append(f"{where}: links outside its own folder: {target}")
            continue
        resolved = (md.parent / target).resolve()
        if root != resolved and root not in resolved.parents:
            problems.append(f"{where}: links outside its own folder: {target}")
        elif not resolved.exists():
            problems.append(f"{where}: references missing file: {target}")
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

    annotate = bool(os.environ.get("GITHUB_ACTIONS"))
    failed = 0
    for skill_dir in dirs:
        problems: list[str] = []
        for md in sorted(skill_dir.rglob("*.md")):
            problems += check_file(md, skill_dir)
        if problems:
            failed += 1
            print(f"FAIL {skill_dir.name}")
            for p in problems:
                print(f"       - {p}")
                if annotate:
                    print(f"::error::{p}")
        else:
            print(f"ok   {skill_dir.name}")

    print()
    if failed:
        print(f"{failed} of {len(dirs)} skills depend on something outside their folder.")
        return 1
    print(f"All {len(dirs)} skills are self-contained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

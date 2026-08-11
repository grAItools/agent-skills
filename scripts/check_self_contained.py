#!/usr/bin/env python3
"""Check that every skill folder stands alone.

The README tells people to copy a single folder into their agent's skills
directory, so a link that points outside the folder — or at a file that isn't
there — arrives broken. This walks every markdown file in every skill folder,
not just `SKILL.md`, since supporting files are linked from it and travel with
it.

Link forms understood: inline `[text](target)`, reference definitions
`[label]: target`, and raw HTML `href=`/`src=` attributes. Inline destinations
are scanned with balanced parentheses, since `[x](a_(b).md)` is a valid link and
stopping at the first `)` would report the file it names as missing.

Fenced and inline code is skipped, so a skill can show a forbidden link as an
example without failing its own check. Code spans are matched by backtick run
length, the way Markdown defines them: ``a `b` c`` is one span, not two.

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
BACKTICKS = re.compile(r"`+")

INLINE_LINK_OPEN = re.compile(r"\]\(")
REFERENCE_LINK = re.compile(r"^[ \t]{0,3}\[[^\]]+\]:[ \t]*(\S+)", re.M)
HTML_ATTR = re.compile(r"""\b(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.I)

# `\(` in a destination is a literal parenthesis, not a nesting one.
ESCAPED_PAREN = re.compile(r"\\([()])")

# A URI scheme: `https://`, but also `mailto:` and any casing of either.
SCHEME = re.compile(r"\A[A-Za-z][A-Za-z0-9+.\-]*:")


def blank_code_spans(text: str) -> str:
    """Replace inline code spans with spaces, leaving every newline in place.

    A span opens with a run of backticks and closes with a run of exactly the
    same length, so ``[a](b)`` is a span and the link inside it is an example
    rather than a link. Reading only single-backtick pairs left that link visible
    to the scanner below, which then failed the skill for quoting it. Runs that
    never find a matching partner are literal backticks, not an opening.

    Newlines survive so the caller can still count lines, and so a span that
    closes on a later line blanks what a Markdown reader would too.
    """
    out = list(text)
    i = 0
    while i < len(text):
        if text[i] != "`":
            i += 1
            continue
        opening = BACKTICKS.match(text, i)
        run = opening.end() - opening.start()

        closing = None
        j = opening.end()
        while j < len(text):
            if text[j] != "`":
                j += 1
                continue
            candidate = BACKTICKS.match(text, j)
            if candidate.end() - candidate.start() == run:
                closing = candidate
                break
            j = candidate.end()  # a longer run cannot close a shorter one

        if closing is None:
            i = opening.end()
            continue
        for k in range(opening.start(), closing.end()):
            if out[k] != "\n":
                out[k] = " "
        i = closing.end()
    return "".join(out)


def strip_code(text: str) -> str:
    """Blank out fenced blocks and inline spans, preserving line numbering."""
    # None marks a line inside a fence. Prose lines are kept as they are and have
    # their code spans blanked afterwards, in contiguous runs, so that a span is
    # never paired across a fenced block sitting between its two halves.
    prose: list[str | None] = []
    fence: str | None = None
    for line in text.splitlines():
        m = FENCE.match(line)
        if fence is None:
            if m and m.group("info").find("`") == -1:
                fence = m.group("fence")[0] * len(m.group("fence"))
                prose.append(None)
                continue
            prose.append(line)
        else:
            # A closing fence is the same character, at least as long, nothing else.
            if m and m.group("fence")[0] == fence[0] and len(m.group("fence")) >= len(fence) \
                    and not m.group("info").strip():
                fence = None
            prose.append(None)

    out = [""] * len(prose)
    start = 0
    while start < len(prose):
        if prose[start] is None:
            start += 1
            continue
        end = start
        while end < len(prose) and prose[end] is not None:
            end += 1
        blanked = blank_code_spans("\n".join(prose[start:end]))
        out[start:end] = blanked.split("\n")
        start = end
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
    return unquote(ESCAPED_PAREN.sub(r"\1", target))


def inline_link_targets(text: str) -> list[tuple[int, str]]:
    """Inline-link destinations, read with parentheses counted rather than split on.

    Markdown allows balanced parentheses in a destination, so `[x](a_(b).md)`
    points at `a_(b).md`. Stopping at the first `)` truncated that to `a_(b` and
    reported a file that is present as missing.
    """
    found: list[tuple[int, str]] = []
    for m in INLINE_LINK_OPEN.finditer(text):
        i = m.end()
        depth = 1
        while i < len(text):
            ch = text[i]
            if ch == "\\":
                i += 2  # an escaped parenthesis does not open or close anything
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if depth != 0:
            continue  # never closed, so not a link
        found.append((text.count("\n", 0, m.start()) + 1, text[m.end():i]))
    return found


def targets_in(text: str) -> list[tuple[int, str]]:
    """Every link destination in the file, with the line it appears on."""
    stripped = strip_code(text)
    found = inline_link_targets(stripped)
    for pattern in (REFERENCE_LINK, HTML_ATTR):
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

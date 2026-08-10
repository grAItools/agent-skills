#!/usr/bin/env python3
"""Regression tests for the two CI gates.

A validation script that silently accepts everything looks exactly like a clean
repository, so each case here pins one thing a gate must accept and one it must
reject. Cases are built as throwaway skill folders in a temp directory.

Usage:  python3 scripts/test_checks.py
Exit:   0 all pass, 1 otherwise.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
LINT = SCRIPTS / "lint_skills.py"
SELF_CONTAINED = SCRIPTS / "check_self_contained.py"

# A minimal description that satisfies every rule, for cases testing one thing.
GOOD_DESC = (
    "Restructures existing code without changing its behavior, in small steps "
    "verified by passing tests. Use when a change fans out into edits "
    "disproportionate to the requirement, or when the same area keeps breaking. "
    "Do not use immediately before a release; book it as a tracked task."
)


class Case(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.skills = self.root / "skills"
        self.skills.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def skill(self, name: str, body: str, filename: str = "SKILL.md") -> Path:
        d = self.skills / name
        d.mkdir(exist_ok=True)
        (d / filename).write_text(body, encoding="utf-8")
        return d

    def frontmatter(self, name: str, desc: str, license_line: str = "license: MIT") -> str:
        lines = ["---", f"name: {name}", f"description: {desc}"]
        if license_line:
            lines.append(license_line)
        lines += ["---", "", "# Body", ""]
        return "\n".join(lines)

    def run_gate(self, script: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(script), str(self.skills)],
            capture_output=True, text=True,
        )

    def assertAccepts(self, script: Path) -> None:
        r = self.run_gate(script)
        self.assertEqual(r.returncode, 0, f"expected clean, got:\n{r.stdout}{r.stderr}")

    def assertRejects(self, script: Path, needle: str = "") -> None:
        r = self.run_gate(script)
        self.assertEqual(r.returncode, 1, f"expected failure, got:\n{r.stdout}{r.stderr}")
        if needle:
            self.assertIn(needle, r.stdout, f"missing {needle!r} in:\n{r.stdout}")


class TestDescriptionContract(Case):
    def test_accepts_block_scalar_description(self) -> None:
        """A folded scalar is valid YAML; a regex reader sees only '>-'."""
        wrapped = "\n".join("  " + line for line in GOOD_DESC.split(". "))
        self.skill("s", f"---\nname: s\ndescription: >-\n{wrapped}\nlicense: MIT\n---\n")
        self.assertAccepts(LINT)

    def test_accepts_quoted_description_with_colon(self) -> None:
        desc = (
            '"Produces a release plan covering one question: how small a slice can '
            "go in front of real users. Use when a working increment exists and "
            "release timing is in question. Do not use to judge whether the change "
            'is correct; use a review skill."'
        )
        self.skill("s", self.frontmatter("s", desc))
        self.assertAccepts(LINT)

    def test_accepts_inline_comment_after_value(self) -> None:
        self.skill("s", self.frontmatter("s", GOOD_DESC, "license: MIT   # required"))
        self.assertAccepts(LINT)

    def test_rejects_dashes_inside_a_value(self) -> None:
        """`---` truncates the frontmatter for readers that split on the marker."""
        desc = GOOD_DESC.replace("in small steps", "in small --- steps")
        self.skill("s", self.frontmatter("s", desc))
        self.assertRejects(LINT, "truncate")

    def test_rejects_boundary_masquerading_as_trigger(self) -> None:
        """'Do not use when ...' contains 'use when' but is not a trigger."""
        desc = (
            "Restructures existing code without changing its behavior in small "
            "verified steps to pay down design debt as it is found. Do not use when "
            "the change alters behavior, or immediately before a release cut."
        )
        self.skill("s", self.frontmatter("s", desc))
        self.assertRejects(LINT, "no 'Use when ...' trigger")

    def test_accepts_absolutes_in_the_boundary_clause(self) -> None:
        desc = (
            "Restructures existing code without changing its behavior in small "
            "verified steps. Use when a change fans out into edits disproportionate "
            "to the requirement. Do not use before a release; always use the "
            "delivery skill then, for any reason."
        )
        self.skill("s", self.frontmatter("s", desc))
        self.assertAccepts(LINT)

    def test_rejects_universal_trigger_by_paraphrase(self) -> None:
        desc = (
            "Reviews code for defects and reports findings with evidence. Use when "
            "writing or modifying any code, at whatever point in the cycle the work "
            "happens to be. Do not use for documentation-only changes."
        )
        self.skill("s", self.frontmatter("s", desc))
        self.assertRejects(LINT, "matches nearly any task")

    def test_rejects_missing_license(self) -> None:
        self.skill("s", self.frontmatter("s", GOOD_DESC, ""))
        self.assertRejects(LINT, "missing `license`")

    def test_rejects_lowercase_skill_file_rather_than_skipping_it(self) -> None:
        self.skill("s", self.frontmatter("s", GOOD_DESC, ""), filename="skill.md")
        self.assertRejects(LINT, "use 'SKILL.md'")

    def test_rejects_description_that_opens_with_the_trigger(self) -> None:
        desc = (
            "Use when a change fans out into edits disproportionate to the "
            "requirement, or when the same area keeps breaking under new "
            "requirements. Do not use immediately before a release cut."
        )
        self.skill("s", self.frontmatter("s", desc))
        self.assertRejects(LINT, "opens with 'Use when'")


class TestSelfContainment(Case):
    def test_accepts_fragment_and_title_on_a_resolving_link(self) -> None:
        d = self.skill("s", "# S\n\n[checklist](reference.md#red-flags)\n"
                            '[titled](reference.md "The title")\n')
        (d / "reference.md").write_text("# Reference\n", encoding="utf-8")
        self.assertAccepts(SELF_CONTAINED)

    def test_accepts_non_http_and_uppercase_schemes(self) -> None:
        self.skill("s", "# S\n\n[mail](mailto:a@b.com) [up](HTTPS://x.com/a)\n"
                        "[anchor](#a-section)\n")
        self.assertAccepts(SELF_CONTAINED)

    def test_accepts_an_angle_bracketed_external_url(self) -> None:
        """`<...>` wraps the destination; the scheme is only visible once it is off."""
        self.skill("s", "# S\n\n[spec](<https://agentskills.io/specification>)\n")
        self.assertAccepts(SELF_CONTAINED)

    def test_accepts_a_forbidden_link_shown_as_an_example(self) -> None:
        self.skill("s", "# S\n\nNever do this:\n\n```markdown\n"
                        "[config](../shared/config.md)\n```\n\nOr this: `](/root.md)`.\n")
        self.assertAccepts(SELF_CONTAINED)

    def test_rejects_reference_style_and_html_links_out_of_the_folder(self) -> None:
        self.skill("s", '# S\n\nSee [the other][o] and <a href="../b/SKILL.md">html</a>.\n\n'
                        "[o]: ../b/SKILL.md\n")
        self.assertRejects(SELF_CONTAINED, "links outside its own folder")

    def test_rejects_a_missing_target_inside_a_supporting_file(self) -> None:
        d = self.skill("s", "# S\n\n[more](reference.md)\n")
        (d / "reference.md").write_text("see [deeper](checklist.md)\n", encoding="utf-8")
        self.assertRejects(SELF_CONTAINED, "references missing file")

    def test_rejects_a_repo_root_absolute_link(self) -> None:
        self.skill("s", "# S\n\n[root](/README.md)\n")
        self.assertRejects(SELF_CONTAINED, "links outside its own folder")


if __name__ == "__main__":
    unittest.main(verbosity=2)

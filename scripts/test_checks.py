#!/usr/bin/env python3
"""Regression tests for the CI gates.

A validation script that silently accepts everything looks exactly like a clean
repository, so each case here pins one thing a gate must accept and one it must
reject. Cases are built as throwaway skill folders in a temp directory.

Both directions matter equally. A gate that rejects valid input is as unusable as
one that accepts anything: it teaches contributors to work around it.

Usage:  python3 scripts/test_checks.py
Exit:   0 all pass, 1 otherwise.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
LINT = SCRIPTS / "lint_skills.py"
SELF_CONTAINED = SCRIPTS / "check_self_contained.py"
MANIFEST = SCRIPTS / "check_manifest.py"

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

    def test_accepts_a_forbidden_link_shown_inside_a_longer_code_span(self) -> None:
        """A code span opens with any run of backticks, not only a single pair."""
        self.skill("s", "# S\n\nNever write ``[config](../shared/config.md)`` in a skill.\n")
        self.assertAccepts(SELF_CONTAINED)

    def test_accepts_a_code_span_that_closes_on_a_later_line(self) -> None:
        """Markdown lets a span wrap; the link inside it is still an example."""
        self.skill("s", "# S\n\nNever write `` [config](\n../shared/config.md) `` here.\n")
        self.assertAccepts(SELF_CONTAINED)

    def test_accepts_balanced_parentheses_in_a_destination(self) -> None:
        """`[x](a_(b).md)` is a valid link to a file whose name holds parentheses."""
        d = self.skill("s", "# S\n\n[guide](docs/a_(b).md)\n")
        (d / "docs").mkdir()
        (d / "docs" / "a_(b).md").write_text("# A\n", encoding="utf-8")
        self.assertAccepts(SELF_CONTAINED)

    def test_rejects_a_parenthesised_destination_that_leaves_the_folder(self) -> None:
        """Counting parentheses must not become a way past the check."""
        self.skill("s", "# S\n\n[guide](../shared/a_(b).md)\n")
        self.assertRejects(SELF_CONTAINED, "links outside its own folder")


class ManifestCase(unittest.TestCase):
    """A throwaway repository: one skill, plus the two plugin manifests."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        skill = self.root / "skills" / "s"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: s\n---\n", encoding="utf-8")

        self.plugin = {
            "name": "graitools",
            "version": "2.0.0",
            "description": "Development-cycle agent skills.",
            "license": "MIT",
            "keywords": ["skills", "sdlc"],
        }
        self.marketplace = {
            "name": "graitools",
            "owner": {"name": "grAItools"},
            "plugins": [
                {
                    "name": "graitools",
                    "source": "./",
                    "description": "Development-cycle agent skills.",
                    "keywords": ["skills", "sdlc"],
                }
            ],
        }

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, plugin_text: str | None = None) -> None:
        d = self.root / ".claude-plugin"
        d.mkdir(exist_ok=True)
        text = json.dumps(self.plugin) if plugin_text is None else plugin_text
        (d / "plugin.json").write_text(text, encoding="utf-8")
        (d / "marketplace.json").write_text(json.dumps(self.marketplace), encoding="utf-8")

    def run_gate(self, target: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(MANIFEST), str(target or self.root)],
            capture_output=True, text=True,
        )

    def assertAccepts(self) -> None:
        r = self.run_gate()
        self.assertEqual(r.returncode, 0, f"expected clean, got:\n{r.stdout}{r.stderr}")

    def assertRejects(self, needle: str) -> None:
        r = self.run_gate()
        self.assertEqual(r.returncode, 1, f"expected failure, got:\n{r.stdout}{r.stderr}")
        self.assertIn(needle, r.stdout, f"missing {needle!r} in:\n{r.stdout}")


class TestPluginManifests(ManifestCase):
    def test_accepts_this_repository(self) -> None:
        """The gate has to pass what it ships against, or it is unusable."""
        repo = SCRIPTS.parent
        r = self.run_gate(repo)
        self.assertEqual(r.returncode, 0, f"expected clean, got:\n{r.stdout}{r.stderr}")

    def test_accepts_the_minimal_pair(self) -> None:
        self.write()
        self.assertAccepts()

    def test_accepts_optional_fields_being_absent(self) -> None:
        """`author` and `repository` are conveniences, not part of the contract."""
        self.plugin.pop("keywords")
        self.marketplace["plugins"][0].pop("keywords")
        self.write()
        self.assertAccepts()

    def test_rejects_descriptions_that_drifted_apart(self) -> None:
        """The description is duplicated verbatim; drift is invisible without a gate."""
        self.marketplace["plugins"][0]["description"] = "Something else entirely."
        self.write()
        self.assertRejects("disagree on `description`")

    def test_rejects_keywords_that_drifted_apart(self) -> None:
        self.marketplace["plugins"][0]["keywords"] = ["skills", "sdlc", "delivery"]
        self.write()
        self.assertRejects("disagree on `keywords`")

    def test_rejects_a_marketplace_entry_for_a_different_plugin(self) -> None:
        self.marketplace["plugins"][0]["name"] = "something-else"
        self.write()
        self.assertRejects("lists no plugin named 'graitools'")

    def test_rejects_a_license_that_is_not_what_the_skills_ship(self) -> None:
        self.plugin["license"] = "Apache-2.0"
        self.write()
        self.assertRejects("`license` is 'Apache-2.0'")

    def test_rejects_a_missing_required_field(self) -> None:
        self.plugin.pop("version")
        self.write()
        self.assertRejects("missing `version`")

    def test_rejects_a_non_semantic_version(self) -> None:
        self.plugin["version"] = "v2"
        self.write()
        self.assertRejects("not a semantic version")

    def test_rejects_invalid_json_rather_than_crashing(self) -> None:
        self.write(plugin_text='{"name": "graitools",}')
        self.assertRejects("not valid JSON")

    def test_rejects_a_source_that_does_not_resolve(self) -> None:
        self.marketplace["plugins"][0]["source"] = "./packages/graitools"
        self.write()
        self.assertRejects("does not resolve")

    def test_rejects_a_source_holding_no_skills(self) -> None:
        """`source` may resolve and still ship nothing after a restructure."""
        empty = self.root / "empty"
        empty.mkdir()
        self.marketplace["plugins"][0]["source"] = "./empty"
        self.write()
        self.assertRejects("no skills")

    def test_rejects_a_missing_manifest(self) -> None:
        self.write()
        (self.root / ".claude-plugin" / "marketplace.json").unlink()
        self.assertRejects("marketplace.json")

    def test_rejects_a_required_field_of_the_wrong_type(self) -> None:
        """A numeric `name` is not a name, and there is no entry to look it up by.

        Checking only for emptiness passed this and then returned early with
        nothing recorded, so a manifest no reader can use reported as clean.
        """
        self.plugin["name"] = 123
        self.write()
        self.assertRejects("`name` is int")

    def test_rejects_an_empty_required_field(self) -> None:
        self.plugin["description"] = ""
        self.write()
        self.assertRejects("empty `description`")

    def test_rejects_keywords_that_are_not_a_list(self) -> None:
        self.plugin["keywords"] = "skills, sdlc"
        self.marketplace["plugins"][0]["keywords"] = "skills, sdlc"
        self.write()
        self.assertRejects("`keywords` is str, expected list")

    def test_rejects_keywords_holding_something_other_than_strings(self) -> None:
        """The list is rendered to a reader, so a number in it is junk on a page."""
        self.plugin["keywords"] = ["skills", 7]
        self.marketplace["plugins"][0]["keywords"] = ["skills", 7]
        self.write()
        self.assertRejects("not of type str")

    def test_rejects_a_source_whose_skill_folders_hold_no_skill_file(self) -> None:
        """A folder left behind by a restructure installs nothing a reader can load."""
        (self.root / "stale" / "skills" / "placeholder").mkdir(parents=True)
        self.marketplace["plugins"][0]["source"] = "./stale"
        self.write()
        self.assertRejects("contains no skills")


class TestTriggerCorpus(unittest.TestCase):
    """The scoring half of the trigger eval, which needs no model to exercise.

    The model call is the part that costs money and varies; everything around it
    — loading the corpus, reading a selection back, deciding pass or fail — is
    ordinary code and is tested as such.
    """

    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        import run_trigger_eval  # noqa: PLC0415 - imported late so SCRIPTS is on the path

        self.mod = run_trigger_eval
        self.root = Path(tempfile.mkdtemp())
        self.known = {"refactoring-continuously", "implementing-strategically"}

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
        sys.path.remove(str(SCRIPTS))

    def corpus(self, *cases: dict) -> Path:
        path = self.root / "triggers.jsonl"
        path.write_text("\n".join(json.dumps(c) for c in cases) + "\n", encoding="utf-8")
        return path

    def skills_dir(self) -> Path:
        """A catalog for `main()` to read, so the argument checks can run offline."""
        root = self.root / "skills"
        for name in sorted(self.known):
            (root / name).mkdir(parents=True, exist_ok=True)
            (root / name / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: Does a thing. Use when asked for it. "
                "Do not use otherwise.\n---\n",
                encoding="utf-8",
            )
        return root

    def run_main(self, corpus: Path, *extra: str) -> int:
        """`main()` up to the point it would need the SDK, with stderr captured."""
        argv = ["--skills", str(self.skills_dir()), "--corpus", str(corpus), *extra]
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = self.mod.main(argv)
        self.stderr = err.getvalue()
        return code

    def two_case_corpus(self) -> Path:
        return self.corpus(
            {"prompt": "first", "fires": ["refactoring-continuously"], "silent": []},
            {"prompt": "second", "fires": ["implementing-strategically"], "silent": []},
        )

    def test_rejects_a_label_naming_a_skill_that_does_not_exist(self) -> None:
        """A typo in a label would quietly test nothing, forever."""
        path = self.corpus({"prompt": "p", "fires": ["refactoring-continuous"], "silent": []})
        with self.assertRaises(self.mod.CorpusError) as caught:
            self.mod.load_corpus(path, self.known)
        self.assertIn("refactoring-continuous", str(caught.exception))

    def test_rejects_a_skill_listed_as_both_firing_and_silent(self) -> None:
        path = self.corpus({
            "prompt": "p",
            "fires": ["refactoring-continuously"],
            "silent": ["refactoring-continuously"],
        })
        with self.assertRaises(self.mod.CorpusError):
            self.mod.load_corpus(path, self.known)

    def test_rejects_an_empty_prompt(self) -> None:
        path = self.corpus({"prompt": "  ", "fires": [], "silent": []})
        with self.assertRaises(self.mod.CorpusError):
            self.mod.load_corpus(path, self.known)

    def test_accepts_a_case_where_nothing_should_fire(self) -> None:
        """Prompts no skill should touch are how over-firing gets caught."""
        path = self.corpus({
            "prompt": "what is the capital of France",
            "fires": [],
            "silent": ["refactoring-continuously", "implementing-strategically"],
        })
        cases = self.mod.load_corpus(path, self.known)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].fires, [])

    def test_reads_a_selection_out_of_a_fenced_json_array(self) -> None:
        text = 'Here is my answer:\n\n```json\n["refactoring-continuously"]\n```\n'
        self.assertEqual(self.mod.parse_selection(text), ["refactoring-continuously"])

    def test_reads_an_empty_selection(self) -> None:
        self.assertEqual(self.mod.parse_selection("```json\n[]\n```"), [])

    def test_raises_when_a_reply_carries_no_array(self) -> None:
        with self.assertRaises(ValueError):
            self.mod.parse_selection("I think none of them apply, really.")

    def test_scores_a_matching_selection_as_a_pass(self) -> None:
        case = self.mod.Case("p", ["refactoring-continuously"], ["implementing-strategically"])
        result = self.mod.score(case, ["refactoring-continuously"])
        self.assertTrue(result.routing_ok)
        self.assertTrue(result.disjoint_ok)

    def test_fails_routing_when_the_expected_skill_stays_silent(self) -> None:
        case = self.mod.Case("p", ["refactoring-continuously"], [])
        result = self.mod.score(case, [])
        self.assertFalse(result.routing_ok)
        self.assertIn("refactoring-continuously", result.detail)

    def test_fails_disjointness_when_an_excluded_skill_co_fires(self) -> None:
        """Co-firing is the failure the description contract exists to prevent."""
        case = self.mod.Case("p", ["refactoring-continuously"], ["implementing-strategically"])
        result = self.mod.score(case, ["refactoring-continuously", "implementing-strategically"])
        self.assertTrue(result.routing_ok)
        self.assertFalse(result.disjoint_ok)
        self.assertIn("implementing-strategically", result.detail)

    def test_ignores_a_skill_that_is_neither_expected_nor_excluded(self) -> None:
        """Unlabelled skills are unjudged; a case only asserts what it names."""
        case = self.mod.Case("p", ["refactoring-continuously"], [])
        result = self.mod.score(case, ["refactoring-continuously", "implementing-strategically"])
        self.assertTrue(result.routing_ok)
        self.assertTrue(result.disjoint_ok)

    def test_rejects_case_zero_rather_than_running_the_last_case(self) -> None:
        """`cases[0 - 1]` is the last case, so 0 would quietly score the wrong prompt."""
        self.assertEqual(self.run_main(self.two_case_corpus(), "--case", "0"), 1)
        self.assertIn("out of range", self.stderr)

    def test_rejects_a_negative_case(self) -> None:
        """`cases[-1 - 1]` is an ordinary index, so this reached the model before."""
        self.assertEqual(self.run_main(self.two_case_corpus(), "--case", "-1"), 1)
        self.assertIn("out of range", self.stderr)

    def test_rejects_a_case_past_the_end_of_the_corpus(self) -> None:
        self.assertEqual(self.run_main(self.two_case_corpus(), "--case", "3"), 1)
        self.assertIn("1..2", self.stderr)

    def test_rejects_a_negative_threshold_that_would_pass_every_run(self) -> None:
        """Below 0 no failure rate can fall under the bar, so a typo reads as green."""
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.mod.parse_args(["--threshold", "-0.5"])

    def test_rejects_a_threshold_above_one(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.mod.parse_args(["--threshold", "1.5"])

    def test_rejects_a_threshold_that_is_not_a_number(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.mod.parse_args(["--threshold", "ninety percent"])

    def test_accepts_a_threshold_at_either_edge_of_the_range(self) -> None:
        self.assertEqual(self.mod.parse_args(["--threshold", "0"]).threshold, 0.0)
        self.assertEqual(self.mod.parse_args(["--threshold", "1"]).threshold, 1.0)

    def test_the_shipped_corpus_loads_against_the_shipped_skills(self) -> None:
        """The labels and the skill folders must not drift apart."""
        repo = SCRIPTS.parent
        names = {d.name for d in (repo / "skills").iterdir() if d.is_dir()}
        cases = self.mod.load_corpus(repo / "evals" / "triggers.jsonl", names)
        self.assertGreaterEqual(len(cases), len(names), "every skill needs at least one case")
        covered = {s for c in cases for s in c.fires}
        self.assertEqual(covered, names, f"skills with no positive case: {names - covered}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

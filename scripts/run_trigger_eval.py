#!/usr/bin/env python3
"""Check that the skill descriptions route the way they claim to.

`lint_skills.py` checks that a description has a trigger and a boundary. It
cannot check the thing those clauses exist for: that a realistic prompt loads
the one skill that owns it, and does not drag its neighbours along. A substring
check can always be evaded by paraphrase — this asks a model instead.

Each case in `evals/triggers.jsonl` is a prompt plus two labels: the skills that
must fire, and the skills that must stay silent. The two are scored separately,
because they fail for different reasons: a missing trigger is a skill that never
loads, while a co-firing neighbour is a boundary drawn in the wrong place, and
that is the failure the description contract exists to prevent.

A case only asserts what it names. Skills in neither list are unjudged, so a
case can be added for one skill without re-labelling every other. Each rate is
taken over the cases carrying the matching label, so a prompt with nothing to
fire is not counted as a routing success it never claimed.

This costs money and is not deterministic, so it is not a pull request gate. Run
it when a description changes, and from the `Trigger eval` workflow on demand.

Usage:  python3 scripts/run_trigger_eval.py [--skills DIR] [--corpus FILE]
                                            [--model ID] [--effort LEVEL]
                                            [--threshold FLOAT] [--case ID]
Exit:   0 both rates at or above the threshold, 1 otherwise or if any case could
        not be evaluated at all, 2 on bad usage.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environment problem
    sys.exit("error: PyYAML is required: pip install pyyaml")

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "medium"
DEFAULT_THRESHOLD = 0.9

FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)

# Structured outputs, so the reply is a schema-valid object rather than prose
# that happens to contain a list.
SELECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Names of the skills to load. Empty if none apply.",
        }
    },
    "required": ["skills"],
    "additionalProperties": False,
}

SYSTEM = """\
You decide which skills an agent loads for a user's message.

You are given a catalog of skills, each with a name and the description its
author wrote. Judge only from those descriptions — you have no other knowledge
of what a skill contains. Load a skill when its description claims the
situation in the message, and leave it out otherwise. Loading a skill that does
not apply costs context in every session, so do not load one on the grounds
that it might be tangentially useful. Selecting nothing is a valid answer.

Reply with the names of the skills to load."""


# Everything a case may carry. Anything else is a typo, and a misspelled
# `silent` would drop every assertion it holds without a word.
CASE_KEYS = frozenset({"prompt", "fires", "silent"})


class CorpusError(Exception):
    """The corpus is malformed or has drifted from the skills it labels."""


@dataclass(frozen=True)
class Case:
    prompt: str
    fires: list[str]
    silent: list[str]


@dataclass
class Result:
    routing_ok: bool
    disjoint_ok: bool
    detail: str = ""


def read_description(md: Path) -> str:
    m = FRONTMATTER.match(md.read_text(encoding="utf-8"))
    if not m:
        raise CorpusError(f"{md}: no frontmatter to read a description from")
    data = yaml.safe_load(m.group(1)) or {}
    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        raise CorpusError(f"{md}: no usable `description`")
    return description.strip()


def skill_catalog(skills_dir: Path) -> dict[str, str]:
    """Every skill's name and description, as a reader would see them."""
    catalog = {}
    for d in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        md = d / "SKILL.md"
        if md.is_file():
            catalog[d.name] = read_description(md)
    if not catalog:
        raise CorpusError(f"no skills found in {skills_dir}")
    return catalog


def label_list(data: dict, field: str, where: str) -> list[str]:
    """One label list, rejected unless it is a list of strings.

    `null` used to raise TypeError out of the reader, and a bare string used to
    be iterated character by character into a list of one-letter labels — which
    then failed the known-name check below with a baffling message.
    """
    value = data.get(field, [])
    if not isinstance(value, list) or any(not isinstance(s, str) for s in value):
        raise CorpusError(f"{where}: `{field}` must be a list of strings")
    return value


def load_corpus(path: Path, known: set[str]) -> list[Case]:
    """Read the labelled prompts, rejecting labels that name no real skill."""
    if not path.is_file():
        raise CorpusError(f"no corpus at {path}")

    cases: list[Case] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("//"):
            continue
        where = f"{path}:{line_no}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CorpusError(f"{where}: not valid JSON: {exc.msg}") from exc
        if not isinstance(data, dict):
            raise CorpusError(f"{where}: not a JSON object")

        # Unknown before missing, so a misspelling is reported as the misspelling
        # it is rather than as the field it displaced.
        unknown = sorted(set(data) - CASE_KEYS)
        if unknown:
            raise CorpusError(
                f"{where}: unknown field(s) {', '.join(repr(k) for k in unknown)}; "
                f"a case carries {', '.join(sorted(CASE_KEYS))}"
            )

        # All three are required. Rejecting typos was not enough: an omitted
        # `silent` drops every assertion it carried just as quietly, and writing
        # an explicit `[]` says the case meant to assert nothing.
        missing = sorted(CASE_KEYS - set(data))
        if missing:
            raise CorpusError(
                f"{where}: missing field(s) {', '.join(repr(k) for k in missing)}; "
                "write an empty list to assert nothing"
            )

        prompt = data["prompt"]
        if not isinstance(prompt, str) or not prompt.strip():
            raise CorpusError(f"{where}: `prompt` must be a non-empty string")
        prompt = prompt.strip()

        fires = label_list(data, "fires", where)
        silent = label_list(data, "silent", where)

        # A typo in a label is worse than a missing case: it asserts nothing and
        # nothing complains, so the skill it was meant to cover goes untested.
        for name in fires + silent:
            if name not in known:
                raise CorpusError(
                    f"{where}: labels {name!r}, which is not a skill in this repository"
                )
        both = sorted(set(fires) & set(silent))
        if both:
            raise CorpusError(
                f"{where}: {', '.join(both)} is required to fire and to stay silent"
            )

        cases.append(Case(prompt, fires, silent))

    if not cases:
        raise CorpusError(f"{path}: no cases")
    return cases


def parse_selection(text: str) -> list[str]:
    """The chosen skills, read out of a reply that may be fenced or wrapped."""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "[":
            continue
        try:
            value, _ = decoder.raw_decode(text, i)
        except ValueError:
            continue
        if isinstance(value, list):
            return [str(v) for v in value]
    raise ValueError(f"no JSON array in the reply: {text[:200]!r}")


def score(case: Case, selected: list[str]) -> Result:
    chosen = set(selected)
    missing = [s for s in case.fires if s not in chosen]
    co_fired = [s for s in case.silent if s in chosen]

    detail = []
    if missing:
        detail.append(f"did not fire: {', '.join(missing)}")
    if co_fired:
        detail.append(f"should have stayed silent: {', '.join(co_fired)}")
    if selected:
        detail.append(f"selected: {', '.join(sorted(chosen))}")
    else:
        detail.append("selected nothing")

    return Result(not missing, not co_fired, "; ".join(detail))


def rates(scored: list[tuple[Case, Result]]) -> tuple[int, int, int, int]:
    """Passes and totals for routing and disjointness, over asserting cases only.

    A case with no `fires` makes no routing claim, and one with no `silent` makes
    no disjointness claim, so scoring either as a pass measures the corpus rather
    than the descriptions. Counting every case inflated both rates enough to
    matter: the no-fire cases alone could carry a run over a 90% threshold that
    the asserting cases by themselves would have failed.
    """
    routed = sum(1 for c, r in scored if c.fires and r.routing_ok)
    routing_total = sum(1 for c, _ in scored if c.fires)
    disjoint = sum(1 for c, r in scored if c.silent and r.disjoint_ok)
    disjoint_total = sum(1 for c, _ in scored if c.silent)
    return routed, routing_total, disjoint, disjoint_total


def catalog_block(catalog: dict[str, str]) -> str:
    return "\n\n".join(f"<skill name={n!r}>\n{d}\n</skill>" for n, d in catalog.items())


def select(client, catalog: dict[str, str], prompt: str, model: str, effort: str) -> list[str]:
    """Ask which skills a reader would load for this prompt."""
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM,
        output_config={
            "effort": effort,
            "format": {"type": "json_schema", "schema": SELECTION_SCHEMA},
        },
        messages=[
            {
                "role": "user",
                "content": (
                    f"Available skills:\n\n{catalog_block(catalog)}\n\n"
                    f"The user says:\n\n{prompt}"
                ),
            }
        ],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"the model declined to answer: {response.stop_details}")
    text = "".join(b.text for b in response.content if b.type == "text")
    selected = parse_selection(text)

    # A name that is not in the catalog is not a routing decision, it is a broken
    # reply. Scoring around it let a run pass on the names that happened to
    # match: a case expecting silence was satisfied by a skill nobody wrote.
    unknown = [s for s in selected if s not in catalog]
    if unknown:
        raise ValueError(f"the reply names skills not in the catalog: {', '.join(unknown)}")
    return selected


def rate(raw: str) -> float:
    """A pass rate, rejected outside 0-1 rather than quietly redefining the gate.

    The workflow passes this through as free text. A negative value would put
    every run above the threshold — including a run where every case failed —
    so a typo would read as a green evaluation rather than as a broken one.
    """
    try:
        value = float(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{raw!r} is not a number") from None
    if not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError(f"{value} is outside the 0-1 range")
    return value


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--skills", type=Path, default=Path("skills"))
    p.add_argument("--corpus", type=Path, default=Path("evals/triggers.jsonl"))
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--effort", default=DEFAULT_EFFORT,
                   choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--threshold", type=rate, default=DEFAULT_THRESHOLD,
                   help="minimum routing and disjointness rate to pass (0-1)")
    p.add_argument("--case", type=int, action="append", dest="cases", metavar="N",
                   help="run only case N (1-based); repeatable")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    try:
        catalog = skill_catalog(args.skills)
        cases = load_corpus(args.corpus, set(catalog))
    except CorpusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.cases:
        # Bounds checked rather than left to indexing: `--case 0` is a plausible
        # typo for the first case, and Python would hand back the last one.
        bad = sorted({n for n in args.cases if not 1 <= n <= len(cases)})
        if bad:
            print(f"error: --case {', '.join(str(n) for n in bad)} "
                  f"out of range (1..{len(cases)})", file=sys.stderr)
            return 1
        cases = [cases[n - 1] for n in args.cases]

    try:
        import anthropic  # noqa: PLC0415 - optional; the scoring half needs no SDK
    except ModuleNotFoundError:
        print("error: the anthropic SDK is required to run the eval: "
              "pip install anthropic", file=sys.stderr)
        return 1

    client = anthropic.Anthropic()
    scored: list[tuple[Case, Result]] = []
    unevaluated = 0

    for i, case in enumerate(cases, 1):
        try:
            selected = select(client, catalog, case.prompt, args.model, args.effort)
        except Exception as exc:  # one bad call should not lose the whole run
            # Deliberately not added to `scored`. An unevaluated case is not
            # evidence about a description, so scoring it as a miss would make the
            # rates below measure API reliability alongside the thing they claim
            # to measure. It is counted instead, and counted is enough to fail.
            print(f"FAIL {i:>3}  {case.prompt[:60]!r}\n       - {exc}")
            unevaluated += 1
            continue

        result = score(case, selected)
        scored.append((case, result))
        if result.routing_ok and result.disjoint_ok:
            print(f"ok   {i:>3}  {case.prompt[:60]!r}")
        else:
            print(f"FAIL {i:>3}  {case.prompt[:60]!r}\n       - {result.detail}")

    routed, routing_total, disjoint, disjoint_total = rates(scored)
    # No asserting cases means nothing was claimed, so nothing failed.
    routing_rate = routed / routing_total if routing_total else 1.0
    disjoint_rate = disjoint / disjoint_total if disjoint_total else 1.0
    print()
    print(f"routing       {routed}/{routing_total}  ({routing_rate:.0%})")
    print(f"disjointness  {disjoint}/{disjoint_total}  ({disjoint_rate:.0%})")
    print(f"{len(cases)} cases, each scored only where it asserts")
    print(f"model {args.model} at effort {args.effort}")

    # A call that never happened is not a routing miss, and a rate is the wrong
    # instrument for it: one broken call out of the shipped corpus still leaves
    # both rates above 90%, so the workflow would go green on an eval that did
    # not run. Inconclusive is its own outcome, and it is not success.
    if unevaluated:
        print()
        print(f"{unevaluated} of {len(cases)} cases could not be evaluated, so the "
              "rates above are measured over an incomplete run.")
        return 1

    if routing_rate < args.threshold or disjoint_rate < args.threshold:
        print()
        print(f"Below the {args.threshold:.0%} threshold. A description is either "
              "missing a situation it owns, or claiming one it does not.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SCENARIO_FILE = "scenario.yaml"
KINDS = {"triggering", "efficacy"}
KNOWN_AGENTS = ["claude", "opencode", "pi", "omp"]
DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_MAX_TURNS = 30
DEFAULT_THRESHOLDS = {"precision": 0.9, "recall": 0.9}
BODY_LINE_LIMIT = 500
BODY_TOKEN_LIMIT = 5000
DESCRIPTION_LIMIT = 1024


@dataclass
class CaseSpec:
    file: Path
    prompt: str
    expect: str | None = None
    allowed: list[str] = field(default_factory=list)

    @property
    def is_positive(self) -> bool:
        return self.expect is not None

    @property
    def label(self) -> str:
        return self.file.stem


@dataclass
class Scenario:
    dir: Path
    name: str
    kind: str
    skill_under_test: str
    description: str
    agents: list[str]
    model: dict[str, str]
    timeout_seconds: int
    max_turns: int
    status: str
    reps: int
    thresholds: dict[str, float]
    task_prompt_file: str | None
    rubric_file: str | None
    checks_file: str | None
    arm_reps: int
    min_delta: float
    judge_model: str
    cases_positive: list[CaseSpec]
    cases_negative: list[CaseSpec]

    @property
    def fixture_dir(self) -> Path:
        return self.dir / "fixture"

    def has_fixture(self) -> bool:
        return self.fixture_dir.is_dir() and any(self.fixture_dir.iterdir())


def repo_paths(start: Path | None = None) -> tuple[Path, Path, Path]:
    harness_dir = Path(__file__).resolve().parent
    evals_dir = harness_dir.parent
    root = evals_dir.parent if start is None else Path(start).resolve()
    return root, evals_dir / "scenarios", root / "skills"


def skill_names(skills_dir: Path) -> list[str]:
    if not skills_dir.is_dir():
        return []
    return sorted(
        d.name
        for d in skills_dir.iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    )


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not match:
        return {}, text.strip()
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("frontmatter must be a mapping")
    return meta, text[match.end():].strip()


def _load_case(path: Path, known: set[str]) -> tuple[CaseSpec | None, list[str]]:
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"{path.name}: cannot read ({exc})"]
    try:
        meta, body = _parse_frontmatter(text)
    except (yaml.YAMLError, ValueError) as exc:
        return None, [f"{path.name}: bad frontmatter ({exc})"]
    expect = meta.get("expect")
    allowed = meta.get("allowed", [])
    if not body:
        errors.append(f"{path.name}: prompt body is empty")
    if expect is not None:
        if not isinstance(expect, str) or expect not in known:
            errors.append(f"{path.name}: expect '{expect}' is not a known skill")
            expect = None
    if not isinstance(allowed, list) or not all(isinstance(a, str) for a in allowed):
        errors.append(f"{path.name}: allowed must be a list of skill names")
        allowed = []
    allowed = [a for a in allowed if a in known]
    unknown = sorted(set(a for a in meta.get("allowed", []) or []) - set(allowed))
    if unknown:
        errors.append(f"{path.name}: allowed references unknown skills: {unknown}")
    if expect and expect in allowed:
        errors.append(f"{path.name}: allowed must not contain the expected skill itself")
    return CaseSpec(file=path, prompt=body, expect=expect, allowed=allowed), errors


def load_scenario(scenario_dir: Path, skills_dir: Path) -> tuple[Scenario | None, list[str]]:
    errors: list[str] = []
    path = scenario_dir / SCENARIO_FILE
    if not path.is_file():
        return None, [f"missing {SCENARIO_FILE}"]
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, [f"{SCENARIO_FILE}: YAML parse error ({exc})"]
    if not isinstance(raw, dict):
        return None, [f"{SCENARIO_FILE}: top level must be a mapping"]

    known_list = skill_names(skills_dir)
    known = set(known_list)

    name = scenario_dir.name
    if raw.get("name") != name:
        errors.append(f"name must be '{name}' (got {raw.get('name')!r})")

    kind = raw.get("kind")
    if kind not in KINDS:
        errors.append(f"kind must be one of {sorted(KINDS)} (got {kind!r})")

    sut = raw.get("skill_under_test")
    if sut not in known:
        errors.append(f"skill_under_test '{sut}' is not a skill folder under skills/")

    agents_raw = raw.get("agents", KNOWN_AGENTS)
    if (
        not isinstance(agents_raw, list)
        or not agents_raw
        or not all(a in KNOWN_AGENTS for a in agents_raw)
    ):
        errors.append(f"agents must be a non-empty subset of {KNOWN_AGENTS}")

    model = raw.get("model") or {}
    if not isinstance(model, dict):
        errors.append("model must be a mapping of agent name to model id")
        model = {}

    timeout_seconds = raw.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    max_turns = raw.get("max_turns", DEFAULT_MAX_TURNS)
    reps = raw.get("reps", 1)
    arm_reps = raw.get("arm_reps", 3)
    min_delta = raw.get("min_delta", 0.0)
    status = raw.get("status", "ready")
    for field_name, value, minimum in [
        ("timeout_seconds", timeout_seconds, 10),
        ("max_turns", max_turns, 1),
        ("reps", reps, 1),
        ("arm_reps", arm_reps, 1),
    ]:
        if not isinstance(value, int) or value < minimum:
            errors.append(f"{field_name} must be an integer >= {minimum}")
    if not isinstance(min_delta, (int, float)):
        errors.append("min_delta must be numeric")
    if status not in {"ready", "draft"}:
        errors.append("status must be 'ready' or 'draft'")

    thresholds = dict(DEFAULT_THRESHOLDS)
    raw_thresholds = raw.get("thresholds") or {}
    if not isinstance(raw_thresholds, dict):
        errors.append("thresholds must be a mapping")
    else:
        for key, value in raw_thresholds.items():
            if key not in ("precision", "recall"):
                errors.append(f"unknown threshold '{key}'")
            elif not isinstance(value, (int, float)) or not 0 <= value <= 1:
                errors.append(f"thresholds.{key} must be a number between 0 and 1")
            else:
                thresholds[key] = float(value)

    cases_positive: list[CaseSpec] = []
    cases_negative: list[CaseSpec] = []

    pos_dir = scenario_dir / "positive"
    neg_dir = scenario_dir / "negative"
    if kind == "triggering":
        if not pos_dir.is_dir():
            errors.append("triggering scenarios require a positive/ directory")
        else:
            found = sorted(pos_dir.glob("*.prompt"))
            if not found:
                errors.append("positive/ contains no .prompt files")
            for f in found:
                case, errs = _load_case(f, known)
                errors.extend(errs)
                if case:
                    cases_positive.append(case)
        if not neg_dir.is_dir():
            errors.append("triggering scenarios require a negative/ directory")
        else:
            found = sorted(neg_dir.glob("*.prompt"))
            if not found:
                errors.append("negative/ contains no .prompt files")
            for f in found:
                case, errs = _load_case(f, known)
                errors.extend(errs)
                if case:
                    cases_negative.append(case)
        stray = [
            p.name
            for p in scenario_dir.glob("*")
            if p.is_file() and p.name not in (SCENARIO_FILE, "fixture.patch")
        ]
        if stray:
            errors.append(f"unexpected files in triggering scenario dir: {stray}")

    task_prompt_file = raw.get("task_prompt")
    rubric_file = raw.get("rubric")
    checks_file = raw.get("checks")
    if kind == "efficacy":
        for key in ("task_prompt", "rubric"):
            if not raw.get(key):
                errors.append(f"efficacy scenarios require '{key}'")
        if not scenario_dir.joinpath(task_prompt_file or "_").is_file():
            errors.append(f"task_prompt file '{task_prompt_file}' does not exist")
        if rubric_file and not scenario_dir.joinpath(rubric_file).is_file():
            errors.append(f"rubric file '{rubric_file}' does not exist")
        if checks_file and not scenario_dir.joinpath(checks_file).is_file():
            errors.append(f"checks file '{checks_file}' does not exist")
        if not (scenario_dir / "fixture").is_dir():
            errors.append("efficacy scenarios require a fixture/ directory")
        stray_dirs = [p.name for p in scenario_dir.iterdir() if p.is_dir() and p.name not in ("fixture",)]
        if stray_dirs:
            errors.append(f"unexpected directories in efficacy scenario dir: {stray_dirs}")

    if errors:
        return None, errors

    scenario = Scenario(
        dir=scenario_dir,
        name=name,
        kind=kind,
        skill_under_test=sut,
        description=str(raw.get("description", "")),
        agents=[str(a) for a in agents_raw],
        model={str(k): str(v) for k, v in model.items()},
        timeout_seconds=int(timeout_seconds),
        max_turns=int(max_turns),
        status=str(status),
        reps=int(reps),
        thresholds=thresholds,
        task_prompt_file=task_prompt_file,
        rubric_file=rubric_file,
        checks_file=checks_file,
        arm_reps=int(arm_reps),
        min_delta=float(min_delta),
        judge_model=str(raw.get("judge_model", "")),
        cases_positive=cases_positive,
        cases_negative=cases_negative,
    )
    return scenario, []


def discover_scenarios(skills_dir: Path, include_drafts: bool = False) -> list[tuple[Path, list[str]]]:
    results = []
    scenarios_root = repo_paths()[1]
    if not scenarios_root.is_dir():
        return results
    for d in sorted(p for p in scenarios_root.iterdir() if p.is_dir()):
        if d.name.startswith("_"):
            continue
        scenario, errors = load_scenario(d, skills_dir)
        if scenario is None or (not include_drafts and scenario.status == "draft"):
            if errors:
                results.append((d, errors))
            continue
        results.append((d, []))
    return results


def check_skill_budgets(skills_dir: Path) -> tuple[list[dict], list[str]]:
    report: list[dict] = []
    errors: list[str] = []
    for name in skill_names(skills_dir):
        path = skills_dir / name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        try:
            _, body = _parse_frontmatter(text)
        except (yaml.YAMLError, ValueError):
            continue
        frontmatter_match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
        desc_len = 0
        if frontmatter_match:
            try:
                meta = yaml.safe_load(frontmatter_match.group(1)) or {}
                desc_len = len(str(meta.get("description", "")))
            except yaml.YAMLError:
                pass
        lines = len(body.splitlines())
        est_tokens = len(body) // 4
        entry = {
            "skill": name,
            "description_chars": desc_len,
            "body_lines": lines,
            "est_tokens": est_tokens,
        }
        report.append(entry)
        if desc_len > DESCRIPTION_LIMIT:
            errors.append(f"{name}: description is {desc_len} chars (limit {DESCRIPTION_LIMIT})")
        if lines > BODY_LINE_LIMIT:
            errors.append(f"{name}: SKILL.md body is {lines} lines (limit {BODY_LINE_LIMIT})")
        if est_tokens > BODY_TOKEN_LIMIT:
            errors.append(f"{name}: SKILL.md body ~{est_tokens} tokens (limit {BODY_TOKEN_LIMIT})")
    return report, errors

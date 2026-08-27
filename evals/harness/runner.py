from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .agents import AgentAdapter, AgentError, build_adapters
from .agents.base import looks_like_auth_failure
from .grade.checks import ChecksError, run_checks
from .grade.judge import JudgeError, judge_submission
from .isolate import build_cell_env, seed_credentials
from .spec import KNOWN_AGENTS, Scenario, repo_paths

VERDICT_PASS = "pass"
VERDICT_FAIL = "fail"
VERDICT_INDETERMINATE = "indeterminate"
EXIT_CODES = {VERDICT_PASS: 0, VERDICT_FAIL: 1, VERDICT_INDETERMINATE: 2}
RANK = {VERDICT_PASS: 0, VERDICT_INDETERMINATE: 1, VERDICT_FAIL: 2}

SKIP_DIRS_IN_DIFF = {".git", ".claude", ".opencode", ".pi", ".agents", "__pycache__"}


@dataclass
class CellPlan:
    cell_id: str
    scenario: Scenario
    agent: str
    arm: str
    rep: int
    case_label: str | None
    prompt: str
    expected_skill: str | None = None


@dataclass
class CellOutcome:
    cell_id: str
    scenario: str
    kind: str
    agent: str
    arm: str
    rep: int
    case_label: str | None
    verdict: str
    reason: str
    expected_skill: str | None = None
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "cell_id": self.cell_id,
            "scenario": self.scenario,
            "kind": self.kind,
            "agent": self.agent,
            "arm": self.arm,
            "rep": self.rep,
            "case_label": self.case_label,
            "verdict": self.verdict,
            "reason": self.reason,
            "expected_skill": self.expected_skill,
            "metrics": self.metrics,
        }


def resolve_model(scenario: Scenario, agent: str) -> str | None:
    for key in (f"EVALS_{agent.upper()}_MODEL", "EVALS_MODEL"):
        value = os.environ.get(key)
        if value:
            return value
    return scenario.model.get(agent)


def plan_cells(
    scenarios: list[Scenario],
    agents_filter: list[str] | None = None,
    arms_filter: list[str] | None = None,
    case_filter: str | None = None,
) -> list[CellPlan]:
    plans: list[CellPlan] = []
    for scenario in scenarios:
        agents = [a for a in scenario.agents if not agents_filter or a in agents_filter]
        task_text = ""
        if scenario.kind == "efficacy":
            task_text = (scenario.dir / scenario.task_prompt_file).read_text(encoding="utf-8")
        for agent in agents:
            if scenario.kind == "triggering":
                cases = [
                    c
                    for c in scenario.cases_positive + scenario.cases_negative
                    if not case_filter or case_filter in c.file.stem or case_filter in c.prompt
                ]
                for case in cases:
                    for rep in range(1, scenario.reps + 1):
                        plans.append(
                            CellPlan(
                                cell_id=f"{scenario.name}--{agent}--treatment--r{rep}--{case.file.stem}",
                                scenario=scenario,
                                agent=agent,
                                arm="treatment",
                                rep=rep,
                                case_label=case.file.stem,
                                prompt=case.prompt,
                                expected_skill=case.expect,
                            )
                        )
            else:
                arms = ["treatment", "baseline"]
                if arms_filter:
                    arms = [a for a in arms if a in arms_filter]
                for arm in arms:
                    for rep in range(1, scenario.arm_reps + 1):
                        plans.append(
                            CellPlan(
                                cell_id=f"{scenario.name}--{agent}--{arm}--r{rep}",
                                scenario=scenario,
                                agent=agent,
                                arm=arm,
                                rep=rep,
                                case_label=None,
                                prompt=task_text,
                            )
                        )
    return plans


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _init_fixture_repo(workdir: Path) -> bool:
    git = shutil.which("git")
    if not git:
        return False
    identity = ["-c", "user.email=evals@localhost", "-c", "user.name=evals"]
    try:
        subprocess.run([git, "init", "-q"], cwd=workdir, check=True, capture_output=True)
        subprocess.run([git, "add", "-A"], cwd=workdir, check=True, capture_output=True)
        subprocess.run(
            [git, *identity, "commit", "-qm", "fixture baseline"],
            cwd=workdir,
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def _apply_fixture_patch(scenario_dir: Path, workdir: Path) -> bool:
    patch = scenario_dir / "fixture.patch"
    git = shutil.which("git")
    if not patch.is_file() or not git:
        return False
    try:
        subprocess.run(
            [git, "apply", "--whitespace=nowarn", str(patch)],
            cwd=workdir,
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def _hash_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_workdir(workdir: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in sorted(workdir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(workdir)
        if any(part in SKIP_DIRS_IN_DIFF for part in rel.parts):
            continue
        manifest[str(rel)] = _hash_file(path)
    return manifest


def collect_submission(workdir: Path, before: dict[str, str], used_git: bool) -> dict:
    after = snapshot_workdir(workdir)
    changed_paths = sorted(after.keys() - before.keys()) + sorted(
        key for key in after.keys() & before.keys() if after[key] != before[key]
    )
    changed_files = []
    total_chars = 0
    for rel in changed_paths:
        content = (workdir / rel).read_text(encoding="utf-8", errors="replace")
        total_chars += len(content)
        changed_files.append({"path": rel, "content": content[:8000]})
        if total_chars > 60000:
            break
    diff = ""
    git = shutil.which("git")
    if used_git and git:
        try:
            subprocess.run([git, "add", "-A"], cwd=workdir, check=True, capture_output=True)
            completed = subprocess.run(
                [git, "diff", "--cached", "HEAD"],
                cwd=workdir,
                check=True,
                capture_output=True,
                text=True,
            )
            diff = completed.stdout
        except (subprocess.CalledProcessError, OSError):
            diff = ""
    return {
        "changed_files": changed_files,
        "removed_count": len(before.keys() - after.keys()),
        "diff": diff,
        "used_git": used_git,
    }


def _launch(
    plan: CellPlan,
    adapter: AgentAdapter,
    cell_dir: Path,
    iso,
    model: str | None,
    timeout: int,
    share_auth: bool = False,
) -> tuple[int, bool, float]:
    if share_auth:
        iso.env.update(adapter.config_share_env())
    runtime_env = adapter.runtime_env()
    iso.env.update(runtime_env)
    command = adapter.build_command(plan.prompt, model, plan.scenario.max_turns, timeout)
    iso.seeded = seed_credentials(iso, [] if share_auth else adapter.credential_candidates())
    _write_json(
        cell_dir / "meta.json",
        {
            "cell_id": plan.cell_id,
            "scenario": plan.scenario.name,
            "kind": plan.scenario.kind,
            "agent": plan.agent,
            "model_requested": model,
            "command": command,
            "seeded_credentials": iso.seeded,
            "runtime_env_keys": sorted(runtime_env),
            "prompt": plan.prompt,
        },
    )
    started = time.monotonic()
    timed_out = False
    stdout_bytes = b""
    stderr_bytes = b""
    exit_code = -1
    try:
        completed = subprocess.run(
            command,
            cwd=iso.workdir,
            env=iso.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
        )
        stdout_bytes = completed.stdout or b""
        stderr_bytes = completed.stderr or b""
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout_bytes = exc.stdout or b""
        stderr_bytes = exc.stderr or b""
    duration = time.monotonic() - started
    (cell_dir / "transcript.jsonl").write_bytes(stdout_bytes)
    (cell_dir / "stderr.log").write_bytes(stderr_bytes)
    return exit_code, timed_out, duration


def _transcript_error_hint(transcript_path: Path) -> str:
    try:
        with transcript_path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("type") == "error":
                    error = event.get("error") or {}
                    data = error.get("data") or {}
                    message = data.get("message") or error.get("message") or ""
                    if message:
                        return f"; agent error: {str(message)[:220]}"
    except OSError:
        pass
    stderr = transcript_path.with_name("stderr.log")
    if stderr.is_file():
        tail = stderr.read_text(encoding="utf-8", errors="replace").strip()[-200:]
        if tail:
            return f"; stderr: {tail}"
    return ""


def _grade_triggering(outcome: CellOutcome, fired: set[str], case) -> None:
    expected = {case.expect} if case.expect else set()
    permitted = expected | set(case.allowed)
    unexpected = sorted(fired - permitted)
    missing = sorted(expected - fired)
    passed = not unexpected and not missing
    if passed:
        if expected:
            reason = "expected skill fired and nothing outside expectation"
        else:
            reason = "no skill fired" if not fired else f"only allowed skills fired: {sorted(fired)}"
    elif missing and not unexpected:
        reason = f"expected '{case.expect}' did not fire"
    elif unexpected and not missing:
        reason = f"fired unexpectedly: {unexpected}"
    else:
        reason = f"missing {missing}, unexpected {unexpected}"
    outcome.verdict = VERDICT_PASS if passed else VERDICT_FAIL
    outcome.reason = reason
    outcome.metrics["fired"] = sorted(fired)
    outcome.metrics["expected"] = sorted(expected)
    outcome.metrics["allowed"] = sorted(case.allowed)


def _grade_efficacy(
    outcome: CellOutcome,
    scenario: Scenario,
    workdir: Path,
    before: dict[str, str],
    used_git: bool,
    env: dict | None = None,
) -> None:
    checks_results: list[dict] = []
    checks_ok = True
    if scenario.checks_file:
        try:
            results = run_checks(scenario.dir / scenario.checks_file, workdir, env=env)
            checks_results = [r.to_dict() for r in results]
            checks_ok = all(r.passed for r in results)
        except ChecksError as exc:
            outcome.verdict = VERDICT_INDETERMINATE
            outcome.reason = f"checks configuration error: {exc}"
            return
    outcome.metrics["checks"] = checks_results

    rubric_text = (scenario.dir / scenario.rubric_file).read_text(encoding="utf-8")
    task_text = (scenario.dir / scenario.task_prompt_file).read_text(encoding="utf-8")
    submission = collect_submission(workdir, before, used_git)

    try:
        verdict = judge_submission(task_text, rubric_text, submission, model=scenario.judge_model or None)
    except JudgeError as exc:
        outcome.verdict = VERDICT_INDETERMINATE
        outcome.reason = f"judge failed: {exc}"
        return

    outcome.metrics["judge"] = verdict.to_dict()
    outcome.metrics["submission_stats"] = {
        "changed_files": len(submission["changed_files"]),
        "diff_chars": len(submission["diff"]),
    }
    if not checks_ok:
        failed = [r["name"] + ":" + r["detail"][:120] for r in checks_results if not r["passed"]]
        outcome.verdict = VERDICT_FAIL
        outcome.reason = f"deterministic checks failed: {failed}"
    elif not verdict.passed:
        outcome.verdict = VERDICT_FAIL
        outcome.reason = (
            f"judge rejected (score {verdict.score}/10): {'; '.join(verdict.weaknesses[:3])}"
        )
    else:
        outcome.verdict = VERDICT_PASS
        outcome.reason = f"checks and judge passed (score {verdict.score}/10)"


CELL_BOUNDARY_STUB = """# Evaluation cell

This directory contains the complete project under evaluation. Treat it as the
entire project: do not read, write, or search outside this directory.
"""


def _write_boundary_stub(workdir: Path) -> None:
    (workdir / "AGENTS.md").write_text(CELL_BOUNDARY_STUB, encoding="utf-8")
    (workdir / "CLAUDE.md").write_text(CELL_BOUNDARY_STUB, encoding="utf-8")


def _run_plan(
    plan: CellPlan,
    adapters: dict[str, AgentAdapter],
    skills_map: dict[str, Path],
    known: set[str],
    results_batch_dir: Path,
    share_auth: bool = False,
) -> CellOutcome:
    scenario = plan.scenario
    adapter = adapters.get(plan.agent)
    cell_dir = results_batch_dir / plan.cell_id
    workdir = cell_dir / "workdir"
    cell_dir.mkdir(parents=True, exist_ok=True)

    outcome = CellOutcome(
        cell_id=plan.cell_id,
        scenario=scenario.name,
        kind=scenario.kind,
        agent=plan.agent,
        arm=plan.arm,
        rep=plan.rep,
        case_label=plan.case_label,
        verdict=VERDICT_INDETERMINATE,
        reason="not run",
        expected_skill=plan.expected_skill,
    )

    try:
        if adapter is None:
            raise AgentError(f"no adapter registered for agent '{plan.agent}'")
        iso = build_cell_env(cell_dir, workdir)
        _write_boundary_stub(workdir)
        before: dict[str, str] = {}
        used_git = False
        if scenario.has_fixture():
            shutil.copytree(scenario.fixture_dir, workdir, dirs_exist_ok=True)
            used_git = _init_fixture_repo(workdir)
            _apply_fixture_patch(scenario.dir, workdir)
            before = snapshot_workdir(workdir)
        if plan.arm == "treatment":
            adapter.install_skills(workdir, iso.home, skills_map)

        model = resolve_model(scenario, plan.agent)
        exit_code, timed_out, duration = _launch(
            plan, adapter, cell_dir, iso, model, scenario.timeout_seconds, share_auth
        )

        transcript = cell_dir / "transcript.jsonl"
        raw_text = transcript.read_text(encoding="utf-8", errors="replace")
        parsed = adapter.parse(transcript, raw_text, known)
        parsed.exit_code = exit_code
        parsed.timed_out = timed_out
        parsed.duration_seconds = duration
        _write_json(cell_dir / "normalized.json", parsed.to_dict())

        usage = parsed.usage
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        cost = usage.get("cost_usd")
        outcome.metrics.update(
            {
                "usage": usage,
                "fired_skills": parsed.fired_skills,
                "exit_code": exit_code,
                "timed_out": timed_out,
                "duration_seconds": round(duration, 1),
                "tokens_total": int(tokens),
                "cost_usd": cost if isinstance(cost, (int, float)) else None,
            }
        )

        if looks_like_auth_failure(parsed.final_text) and not parsed.tool_calls:
            outcome.reason = (
                "agent could not authenticate; for Claude subscriptions refresh the "
                "login once interactively and retry with --share-auth, or export a "
                "provider API key (ANTHROPIC_API_KEY)"
            )
            return outcome
        if exit_code != 0 and parsed.usage.get("output_tokens", 0) == 0:
            hint = _transcript_error_hint(transcript)
            outcome.reason = f"agent exited {exit_code} without any model output{hint}"
            return outcome
        if timed_out:
            outcome.reason = f"agent exceeded timeout ({scenario.timeout_seconds}s)"
            return outcome
        if exit_code != 0 and not parsed.tool_calls and not parsed.final_text:
            hint = _transcript_error_hint(transcript)
            model_note = (
                "" if resolve_model(scenario, plan.agent)
                else f" (consider exporting EVALS_{plan.agent.upper()}_MODEL)"
            )
            outcome.reason = (
                f"agent exited {exit_code} with no usable output{model_note}{hint}"
            )
            return outcome

        if scenario.kind == "triggering":
            case = next(
                (
                    c
                    for c in scenario.cases_positive + scenario.cases_negative
                    if c.file.stem == plan.case_label
                ),
                None,
            )
            if case is None:
                outcome.reason = f"case '{plan.case_label}' not found at grading time"
                return outcome
            _grade_triggering(outcome, set(parsed.fired_skills), case)
        else:
            outcome.metrics["final_message"] = parsed.final_text[:2000]
            _grade_efficacy(outcome, scenario, workdir, before, used_git, env=iso.env)
    except AgentError as exc:
        outcome.reason = f"adapter error: {exc}"
    except Exception as exc:
        outcome.reason = f"harness error: {type(exc).__name__}: {exc}"
        (cell_dir / "error.txt").write_text(repr(exc), encoding="utf-8")

    _write_json(cell_dir / "verdict.json", outcome.to_dict())
    return outcome


def aggregate_scenario_agent(scenario: Scenario, agent: str, outcomes: list[CellOutcome]) -> dict:
    if scenario.kind == "triggering":
        positives = [o for o in outcomes if o.expected_skill]
        negatives = [o for o in outcomes if not o.expected_skill]
        tp = sum(1 for o in positives if o.verdict == VERDICT_PASS)
        fn = len(positives) - tp
        tn = sum(1 for o in negatives if o.verdict == VERDICT_PASS)
        fp = len(negatives) - tn
        indet = sum(1 for o in outcomes if o.verdict == VERDICT_INDETERMINATE)
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        if fn or fp:
            verdict = VERDICT_FAIL
        elif indet:
            verdict = VERDICT_INDETERMINATE
        else:
            verdict = VERDICT_PASS
        measurable = [
            (name, value)
            for name, value in (("precision", precision), ("recall", recall))
            if value is not None
        ]
        thresholds_met = all(value >= scenario.thresholds[name] for name, value in measurable)
        if not measurable:
            verdict = VERDICT_INDETERMINATE if verdict == VERDICT_PASS else verdict
        elif verdict == VERDICT_PASS and not thresholds_met:
            verdict = VERDICT_FAIL
        return {
            "kind": "triggering",
            "cells": len(outcomes),
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "indeterminate": indet,
            "precision": round(precision, 3) if precision is not None else None,
            "recall": round(recall, 3) if recall is not None else None,
            "thresholds": scenario.thresholds,
            "verdict": verdict,
        }

    def arm_stats(arm: str) -> dict:
        reps = [o for o in outcomes if o.arm == arm]
        scored = [o["judge"]["score"] for o in (r.metrics for r in reps) if "judge" in o]
        passes = sum(1 for r in reps if r.verdict == VERDICT_PASS)
        indet = sum(1 for r in reps if r.verdict == VERDICT_INDETERMINATE)
        return {
            "reps": len(reps),
            "passes": passes,
            "indeterminate": indet,
            "mean_score": round(sum(scored) / len(scored), 2) if scored else None,
            "total_tokens": sum(r.metrics.get("tokens_total", 0) for r in reps),
            "total_cost_usd": round(
                sum(c for c in (r.metrics.get("cost_usd") or 0 for r in reps)), 4
            ),
        }

    treatment = arm_stats("treatment")
    baseline = arm_stats("baseline")
    delta = None
    if treatment["mean_score"] is not None and baseline["mean_score"] is not None:
        delta = round(treatment["mean_score"] - baseline["mean_score"], 2)

    if delta is None:
        verdict = VERDICT_INDETERMINATE
    elif any(o.verdict == VERDICT_INDETERMINATE for o in outcomes):
        verdict = VERDICT_INDETERMINATE
    elif delta < scenario.min_delta:
        verdict = VERDICT_FAIL
    else:
        verdict = VERDICT_PASS

    return {
        "kind": "efficacy",
        "treatment": treatment,
        "baseline": baseline,
        "delta_mean_score": delta,
        "min_delta": scenario.min_delta,
        "verdict": verdict,
    }


def run_batch(
    scenarios: list[Scenario],
    repo_root: Path,
    results_root: Path,
    agents_filter: list[str] | None = None,
    dry_run: bool = False,
    arms_filter: list[str] | None = None,
    case_filter: str | None = None,
    share_auth: bool = False,
) -> int:
    _, _, skills_dir = repo_paths(repo_root)
    skills_map = {
        name: skills_dir / name
        for name in sorted(os.listdir(skills_dir))
        if (skills_dir / name / "SKILL.md").is_file()
    } if skills_dir.is_dir() else {}
    known = set(skills_map)

    plans = plan_cells(scenarios, agents_filter, arms_filter, case_filter)
    unknown_agents = sorted({p.agent for p in plans} - set(KNOWN_AGENTS))

    if dry_run:
        print(f"{len(plans)} cell(s) planned:")
        current = None
        for plan in plans:
            key = (plan.scenario.name, plan.agent)
            if key != current:
                current = key
                print(f"\n{plan.scenario.name} × {plan.agent}")
            extra = f" case={plan.case_label}" if plan.case_label else ""
            print(f"  {plan.cell_id}{extra}")
        return 0

    if unknown_agents:
        print(f"error: unknown agents in plans: {unknown_agents}", file=sys.stderr)
        return EXIT_CODES[VERDICT_INDETERMINATE]

    adapters = build_adapters()
    batch_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    results_batch_dir = results_root / batch_id
    results_batch_dir.mkdir(parents=True, exist_ok=True)

    outcomes: list[CellOutcome] = []
    print(f"batch {batch_id}: {len(plans)} cell(s)")
    for index, plan in enumerate(plans, 1):
        print(f"[{index}/{len(plans)}] {plan.cell_id} … ", flush=True)
        outcome = _run_plan(plan, adapters, skills_map, known, results_batch_dir, share_auth)
        outcomes.append(outcome)
        usage = outcome.metrics.get("usage", {})
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        cost = usage.get("cost_usd")
        suffix = f" ↑↓{tokens}tok"
        if isinstance(cost, (int, float)):
            suffix += f" ${cost:.3f}"
        print(f"  → {outcome.verdict.upper()}: {outcome.reason}{suffix}", flush=True)

    summary: dict = {
        "batch_id": batch_id,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cells": [o.to_dict() for o in outcomes],
        "scenarios": {},
    }
    for scenario in scenarios:
        for agent in dict.fromkeys(p.agent for p in plans if p.scenario.name == scenario.name):
            relevant = [o for o in outcomes if o.scenario == scenario.name and o.agent == agent]
            if relevant:
                summary["scenarios"][f"{scenario.name}/{agent}"] = aggregate_scenario_agent(
                    scenario, agent, relevant
                )
    _write_json(results_batch_dir / "summary.json", summary)

    batch_verdict = VERDICT_PASS
    for entry in summary["scenarios"].values():
        if RANK[entry["verdict"]] > RANK[batch_verdict]:
            batch_verdict = entry["verdict"]

    worst = max((o.verdict for o in outcomes), key=lambda v: RANK[v], default=VERDICT_PASS)
    print(f"\nbatch verdict: {batch_verdict} (worst cell: {worst})")
    print(f"results: {results_batch_dir}")
    return EXIT_CODES[batch_verdict]

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agents import build_adapters
from .report import load_batches, render_batch, write_report
from .runner import run_batch
from .spec import (
    KNOWN_AGENTS,
    check_skill_budgets,
    discover_scenarios,
    load_scenario,
    repo_paths,
)


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def cmd_list(args: argparse.Namespace) -> int:
    root, scenarios_dir, skills_dir = repo_paths(_default_repo_root())
    found = 0
    for scenario_dir in sorted(p for p in scenarios_dir.iterdir() if p.is_dir()):
        if scenario_dir.name.startswith("_"):
            continue
        scenario, errors = load_scenario(scenario_dir, skills_dir)
        if errors:
            print(f"{scenario_dir.name}: INVALID")
            for error in errors:
                print(f"  - {error}")
            continue
        if scenario.status == "draft" and not args.all:
            continue
        found += 1
        cases = ""
        if scenario.kind == "triggering":
            cases = f", {len(scenario.cases_positive)}+/{len(scenario.cases_negative)}- cases"
        print(
            f"{scenario.name} [{scenario.kind}] status={scenario.status} "
            f"skill={scenario.skill_under_test} agents={','.join(scenario.agents)}{cases}"
        )
    if not found:
        print("no ready scenarios found (use --all to include drafts)")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    root, scenarios_dir, skills_dir = repo_paths(_default_repo_root())
    had_errors = False

    budget_report, budget_errors = check_skill_budgets(skills_dir)
    if budget_report:
        print("Skill budgets:")
        for entry in budget_report:
            print(
                f"  {entry['skill']}: desc={entry['description_chars']}ch, "
                f"body={entry['body_lines']} lines, ~{entry['est_tokens']} tokens"
            )
    if budget_errors:
        had_errors = True
        print("Budget violations:")
        for error in budget_errors:
            print(f"  - {error}")

    print("\nScenarios:")
    scenario_dirs = sorted(
        p
        for p in scenarios_dir.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    ) if scenarios_dir.is_dir() else []
    if not scenario_dirs:
        print("  (no scenario directories)")
    for scenario_dir in scenario_dirs:
        scenario, errors = load_scenario(scenario_dir, skills_dir)
        name = scenario_dir.name
        if errors:
            had_errors = True
            print(f"  {name}: INVALID")
            for error in errors:
                print(f"    - {error}")
            continue
        assert scenario is not None
        detail = ""
        if scenario.kind == "triggering":
            detail = (
                f"{len(scenario.cases_positive)} positive / "
                f"{len(scenario.cases_negative)} negative case(s)"
            )
        else:
            detail = f"arm_reps={scenario.arm_reps}, min_delta={scenario.min_delta}"
        print(f"  {name}: OK ({scenario.kind}, {detail})")

    adapters = build_adapters()
    missing_binaries = [
        name
        for name in KNOWN_AGENTS
        if not _which(name)
    ]
    if missing_binaries:
        print(f"\nNote: agent CLIs not on PATH: {', '.join(missing_binaries)}")
    registered = sorted(adapters)
    print(f"Harness adapters: {', '.join(registered)}")

    return 1 if had_errors else 0


def _which(binary: str) -> bool:
    import shutil

    return shutil.which(binary) is not None


def _select_scenarios(args: argparse.Namespace):
    root, scenarios_dir, skills_dir = repo_paths(_default_repo_root())
    selected = []
    invalid = []
    if args.scenario:
        for name in args.scenario:
            scenario_dir = scenarios_dir / name
            if not scenario_dir.is_dir():
                invalid.append(f"{name}: no such scenario directory")
                continue
            scenario, errors = load_scenario(scenario_dir, skills_dir)
            if errors or scenario is None:
                invalid.append(f"{name}: " + "; ".join(errors))
                continue
            selected.append(scenario)
    else:
        for scenario_dir, errors in discover_scenarios(skills_dir, include_drafts=False):
            if errors:
                invalid.append(f"{scenario_dir.name}: " + "; ".join(errors))
                continue
            scenario, fresh_errors = load_scenario(scenario_dir, skills_dir)
            if scenario is not None:
                selected.append(scenario)
    for message in invalid:
        print(message, file=sys.stderr)
    return selected


def cmd_run(args: argparse.Namespace) -> int:
    root, _, _ = repo_paths(_default_repo_root())
    results_root = Path(args.results_dir) if args.results_dir else root / "evals" / "results"
    scenarios = _select_scenarios(args)
    if not scenarios:
        print("error: nothing to run (check --scenario names or add ready scenarios)", file=sys.stderr)
        return 2
    agents_filter = args.agent or None
    arms_filter = args.arm or None
    if args.case:
        scoped = [s for s in scenarios if s.kind == "triggering"]
        dropped = len(scenarios) - len(scoped)
        if dropped:
            print(f"note: --case restricts to triggering scenarios ({dropped} efficacy scenario(s) skipped)")
        scenarios = scoped
    exit_code = run_batch(
        scenarios,
        root,
        results_root,
        agents_filter=agents_filter,
        dry_run=args.dry_run,
        arms_filter=arms_filter,
        case_filter=args.case,
        share_auth=args.share_auth,
    )
    return exit_code


def cmd_show(args: argparse.Namespace) -> int:
    root, _, _ = repo_paths(_default_repo_root())
    target = Path(args.results) if args.results else root / "evals" / "results"
    summary_path = target / "summary.json" if target.is_dir() else target
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        batches = load_batches(target.parent if target.is_file() else target)
        if not batches:
            print(f"no summary.json at {summary_path}", file=sys.stderr)
            return 2
        batch_id, summary = batches[-1]
    print(render_batch(summary))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    root, _, _ = repo_paths(_default_repo_root())
    results_root = Path(args.results_dir) if args.results_dir else root / "evals" / "results"
    out_path = Path(args.out) if args.out else None
    return write_report(results_root, out_path)


def cmd_clean(args: argparse.Namespace) -> int:
    from .fixtures_clean import clean_fixtures

    removed = clean_fixtures()
    print(f"removed {len(removed)} stray file(s) from fixtures")
    for entry in removed:
        print("  -", entry)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evals",
        description="Behavioral evaluation harness for graitools agent skills",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list scenarios")
    list_parser.add_argument("--all", action="store_true", help="include drafts")
    list_parser.set_defaults(func=cmd_list)

    validate_parser = subparsers.add_parser(
        "validate", help="statically validate scenarios and skill budgets (CI-safe)"
    )
    validate_parser.set_defaults(func=cmd_validate)

    run_parser = subparsers.add_parser("run", help="run evaluation cells with live agents")
    run_parser.add_argument("--scenario", action="append", help="scenario name (repeatable)")
    run_parser.add_argument("--all-ready", action="store_true", help="run every ready scenario")
    run_parser.add_argument("--agent", action="append", choices=KNOWN_AGENTS, help="restrict agents")
    run_parser.add_argument("--arm", action="append", choices=["treatment", "baseline"], help="restrict efficacy arms")
    run_parser.add_argument("--case", help="substring filter on triggering case id/prompt")
    run_parser.add_argument("--dry-run", action="store_true", help="print planned cells without launching")
    run_parser.add_argument(
        "--share-auth",
        action="store_true",
        help="point agents at the host's live config dirs (rotation-safe OAuth); "
        "host-installed skills and settings become visible to the agent",
    )
    run_parser.add_argument("--results-dir", help="override results directory")
    run_parser.set_defaults(func=cmd_run)

    show_parser = subparsers.add_parser("show", help="render a batch summary")
    show_parser.add_argument(
        "results", nargs="?", default=None,
        help="batch dir or summary.json (default: newest batch under evals/results)",
    )
    show_parser.set_defaults(func=cmd_show)

    report_parser = subparsers.add_parser("report", help="aggregate matrix across batches")
    report_parser.add_argument("--out", help="write markdown report to this path")
    report_parser.add_argument("--results-dir", help="override results directory")
    report_parser.set_defaults(func=cmd_report)

    clean_parser = subparsers.add_parser(
        "fixtures-clean", help="purge agent-written strays from scenario fixtures"
    )
    clean_parser.set_defaults(func=cmd_clean)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "command", None) == "run" and not args.scenario and not args.all_ready:
        parser.error("run requires --scenario NAME (repeatable) or --all-ready")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

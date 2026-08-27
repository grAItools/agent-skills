from __future__ import annotations

import json
from pathlib import Path


def load_batches(results_root: Path) -> list[tuple[str, dict]]:
    batches: list[tuple[str, dict]] = []
    if not results_root.is_dir():
        return batches
    for batch_dir in sorted(p for p in results_root.iterdir() if p.is_dir()):
        summary_path = batch_dir / "summary.json"
        if not summary_path.is_file():
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        batches.append((batch_dir.name, summary))
    return batches


def _metric_text(data: dict) -> str:
    if data.get("kind") == "triggering":
        parts = [f"P={data.get('precision')}", f"R={data.get('recall')}"]
        if data.get("indeterminate"):
            parts.append(f"indet={data['indeterminate']}")
        return ", ".join(parts)
    treatment = data.get("treatment", {})
    baseline = data.get("baseline", {})
    delta = data.get("delta_mean_score")
    delta_text = f"Δ{delta:+}" if isinstance(delta, (int, float)) else "Δn/a"
    return (
        f"{delta_text} "
        f"(treat {treatment.get('passes', 0)}/{treatment.get('reps', 0)}"
        f" · base {baseline.get('passes', 0)}/{baseline.get('reps', 0)};"
        f" tok {treatment.get('total_tokens', 0)} vs {baseline.get('total_tokens', 0)})"
    )


def render_batch(summary: dict) -> str:
    lines = [f"# Batch {summary.get('batch_id', '?')}", ""]
    lines.append("| Scenario | Agent | Verdict | Metrics |")
    lines.append("|---|---|---|---|")
    for key in sorted(summary.get("scenarios", {})):
        scenario_name, agent = key.rsplit("/", 1)
        data = summary["scenarios"][key]
        lines.append(
            f"| {scenario_name} | {agent} | **{data.get('verdict')}** | {_metric_text(data)} |"
        )
    failures = [
        cell
        for cell in summary.get("cells", [])
        if cell.get("verdict") in ("fail", "indeterminate")
    ]
    if failures:
        lines.extend(["", "## Non-passing cells", ""])
        for cell in failures:
            lines.append(f"- `{cell['cell_id']}` — {cell['verdict']}: {cell['reason']}")
    return "\n".join(lines)


def render_matrix(results_root: Path) -> str:
    batches = load_batches(results_root)
    if not batches:
        return "No eval batches found under " + str(results_root)
    latest: dict[tuple[str, str], tuple[str, dict]] = {}
    for batch_id, summary in batches:
        for key, data in summary.get("scenarios", {}).items():
            scenario_name, agent = key.rsplit("/", 1)
            slot = (scenario_name, agent)
            existing = latest.get(slot)
            if existing is None or batch_id >= existing[0]:
                latest[slot] = (batch_id, data)

    scenarios = sorted({s for s, _ in latest})
    agents = sorted({a for _, a in latest})
    lines = ["# Skills evaluation matrix", "", "Latest recorded batch per scenario × agent.", ""]

    header = "| Scenario | " + " | ".join(agents) + " |"
    separator = "|---" * (len(agents) + 1) + "|"
    lines.append(header)
    lines.append(separator)
    for scenario_name in scenarios:
        row = [f"| {scenario_name}"]
        for agent in agents:
            entry = latest.get((scenario_name, agent))
            if entry is None:
                row.append(" — ")
            else:
                batch_id, data = entry
                row.append(f" `{data.get('verdict')}` ({_metric_text(data)}, batch {batch_id}) ")
        row.append("|")
        lines.append(" | ".join(row))
    return "\n".join(lines)


def write_report(results_root: Path, out_path: Path | None) -> int:
    matrix = render_matrix(results_root)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(matrix + "\n", encoding="utf-8")
        print(f"report written to {out_path}")
    else:
        print(matrix)
    return 0

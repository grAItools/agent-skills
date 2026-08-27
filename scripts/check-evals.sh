#!/usr/bin/env bash
#
# Statically validate the evaluation assets under evals/ — no API keys, no
# agent CLIs, no network. Safe for every pull request.
#
# What it checks:
#
#   scenario structure   every evals/scenarios/* directory parses: required
#                        fields per kind, prompt frontmatter, rubrics, fixtures,
#                        thresholds within range
#   skill budgets        SKILL.md body line/token limits and description length,
#                        the context-saturation guardrail the live evals measure
#
# The harness itself lives in evals/; `uv run --project evals evals validate`
# is this script's engine, exactly as CI runs it.
#
# Usage:  scripts/check-evals.sh
# Exit:   0 clean, 1 if anything objects.

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is required to run the evaluation validator." >&2
    echo "       install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

echo "==> eval scenarios and skill budgets"
uv run --quiet --project evals evals validate

echo
echo "==> harness import smoke"
uv run --quiet --project evals python -c "from harness import cli, runner, report"

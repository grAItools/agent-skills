# Skills evaluation harness

Behavioral evaluation for the skills in [`skills/`](../skills): does each skill
**fire when it should**, **stay silent when it shouldn't**, **improve the
agent's work**, and **stay affordable in context** — measured across real
coding-agent CLIs, not simulated ones.

The design follows the pattern proven by [Quorum][quorum] (the eval lab behind
obra/superpowers) scaled down for this repository: scenario directories,
per-cell throwaway environments, deterministic transcript grading, optional
LLM-judge rubrics, three-valued verdicts, and a hard line between free static
checks and billed live runs.

[quorum]: https://github.com/prime-radiant-inc/superpowers-evals

## What gets measured

| Dimension | How |
|---|---|
| Trigger precision/recall | Positive prompt cases must fire `skill_under_test`; negative cases must not fire anything outside their `allowed` list. Detected from tool-call transcripts (Skill-tool invocations, skill `SKILL.md` reads), never from output text alone. |
| Cross-skill routing | Every run installs the **full six-skill set**, so confusion between neighbours (the disjoint-trigger rule in CONTRIBUTING) is observable as unexpected firings. |
| Efficacy | A fixture task is run `arm_reps` times **without** skills (baseline) and **with** all skills (treatment); an LLM judge grades blind against a rubric; deterministic checks gate both arms. Verdict requires `delta ≥ min_delta`. |
| Context cost | Static budgets (`evals validate`): body ≤ 500 lines, ~≤ 5000 tokens, description ≤ 1024 chars. Dynamic per cell: token usage extracted from agent JSON streams; treatment-vs-baseline totals appear in reports. |
| Portability | Same scenario × {claude, opencode, pi, omp}; the matrix report shows per-agent verdicts. |

## Quickstart

```bash
scripts/check-evals.sh                                  # free static gate (what CI runs)
uv run --project evals evals list                       # ready scenarios
uv run --project evals evals run --all-ready --dry-run  # inspect planned cells
uv run --project evals evals validate                   # detailed validation report

# one cheap live cell (billed):
uv run --project evals evals run \
    --scenario triggering-designing-before-coding \
    --agent claude --case open-choice-needs-rationale

uv run --project evals evals show evals/results/<batch> # render one batch
uv run --project evals evals report                     # matrix across batches
```

Exit codes follow the three-valued verdict convention: `0` pass, `1` fail,
`2` indeterminate (setup/timeout/auth problems — never silently counted as a
routing failure).

## Agents and authentication

Each cell runs inside a throwaway `$HOME` (plus XDG dirs and TMPDIR), so host
plugins, sessions, and installed skills cannot contaminate results.

| Agent | Headless invocation | Auth in isolated home |
|---|---|---|
| claude | `claude -p … --output-format stream-json` | **Not copied, by design.** Claude OAuth refresh tokens rotate on use; copying them invalidates your login. Either export `ANTHROPIC_API_KEY`, or run `--share-auth` which points `CLAUDE_CONFIG_DIR` at your live `~/.claude`. |
| opencode | `opencode run --format json --auto` | Seeds `auth.json` (API-key store). Pin a tool-capable model: `EVALS_OPENCODE_MODEL=provider/model`. |
| pi | `pi -p --mode json --no-session` | Seeds `auth.json`; pin with `EVALS_PI_MODEL=provider/model` if the default has no key. |
| omp | `omp -p --mode json --no-session --auto-approve --max-time N` | Relies on provider env keys (`ANTHROPIC_API_KEY`, …); no known auth-file to seed. |

Model precedence everywhere: `scenario.yaml model.<agent>` →
`EVALS_<AGENT>_MODEL` → `EVALS_MODEL` → agent default.

`--share-auth` trades purity for convenience: the agent sees your *live* host
config, including any personally installed skills — useful for debugging, but
run clean measurement cells without it once auth works.

## Scenario authoring

Copy `scenarios/_template/` (see its annotated `scenario.yaml`). Two kinds:

**Triggering** (`positive/*.prompt`, `negative/*.prompt`) — each `.prompt` file
is one case; frontmatter controls expectations:

```markdown
---
expect: designing-before-coding   # positive: this skill must fire
allowed: [refactoring-continuously]  # these others are tolerated
---
The team signed off on REQUIREMENTS.md. Produce the technical design…
```

A negative case omits `expect`: nothing outside `allowed` (usually nothing at
all) may fire. A case fails on **both** misses (should-fire didn't) and false
fires (co-firing neighbours) — that asymmetry is what enforces disjoint
triggers mechanically instead of by review alone.

**Efficacy** (`fixture/`, `task.prompt`, `rubric.md`, optional `checks.yaml`,
optional `fixture.patch`) — the fixture is copied into the working directory,
git-initialized, and `fixture.patch` (if present) is applied on top, so review
scenarios can present a finished-but-uncommitted change. Deterministic checks:
`file_exists`, `file_absent`, `file_contains` (regex over path/glob), and
`command_succeeds` (bash, executed in the agent's isolated environment).
The judge sees task + rubric + changed files/diff only — never which arm
produced the submission.

Guidelines distilled from Anthropic's authoring guidance and superpowers'
testing methodology:

- Write the baseline first: if agents already do the right thing unaided, the
  scenario proves nothing.
- Prompts must be grounded in the fixture (agents notice empty directories and
  wander).
- Prefer symptoms over abstractions in trigger cases, mirroring how the
  descriptions themselves are written.
- Single samples lie: use `reps`/`arm_reps` ≥ 3 before drawing conclusions;
  variance is itself reported.

## Results layout

```
evals/results/<batch>/<cell>/
├── meta.json          command, model, prompt, seeded credentials
├── transcript.jsonl   raw agent event stream
├── stderr.log
├── normalized.json    fired skills, tool calls, token usage, final message
└── verdict.json       pass | fail | indeterminate + reason + metrics
```

`summary.json` lands at the batch level; `evals report` aggregates batches into
a markdown matrix. Raw artifacts stay local (gitignored); CI runs upload them
as workflow artifacts instead.

## CI policy

Free static checks run on every PR via `scripts/check-evals.sh` (wired into
`validate-skills.yml`). Live evaluations are a **trusted-maintainer operation**
(`evals-live.yml`, manual dispatch): they launch permissive agent CLIs against
synthetic fixtures, bill configured providers, upload results as artifacts, and
never gate merges. Keep secrets out of scenario files; keep raw transcripts
out of git.

## Known limitations

- Skill-firing detection reads tool-call traces; an agent that follows a
  skill's advice without ever loading it scores as "not fired" (by design — we
  measure loading, not vibes).
- pi/omp adapters were verified against their documented CLIs; flag drift is
  contained inside `harness/agents/pilike.py`.
- Runs are sequential; parallel scheduling (Quorum-style limiter keys) is a
  natural next step.

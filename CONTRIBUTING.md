# Contributing a Skill

Every skill in this repository is a folder under `skills/` that any coding agent
supporting the [Agent Skills](https://agentskills.io) format can pick up unchanged.
Keep that portability when adding or editing one.

## Format

```
skills/
└── my-skill-name/
    ├── SKILL.md          # required, spelled exactly like this
    └── ...               # optional supporting files (references, templates, scripts)
```

- The folder name is the skill name: short, kebab-case, verb-led where possible
  (`discovering-requirements`, not `requirements`).
- The body of `SKILL.md` holds the instructions: what the skill is for, when (and
  when not) to use it, how to do the work, and what the deliverable looks like.

## Frontmatter

`SKILL.md` starts with YAML frontmatter containing exactly the fields the open
format defines:

```yaml
---
name: my-skill-name   # must match the folder name
description: <what it does> Use when <situations>. Do not use <boundary>.
license: MIT
---
```

`license` is required even though the repository has a `LICENSE` file: skills get
copied out one folder at a time and the repository license does not travel with
them, so the frontmatter field is what makes a copied skill self-describing.

`scripts/lint_skills.py` enforces the mechanical part of the contract. What it
rejects, and why:

| Rule | Why |
|---|---|
| `name` matches the folder name | Hosts key the skill by one or the other |
| `license: MIT` present | See above |
| `description` is 120–1024 characters | The open format caps it at 1024; three real clauses don't fit under 120 |
| Description does not open with "Use when" | Hosts truncate from the end, so the capability has to come first |
| A `Use when ...` clause ahead of the `Do not use ...` one | Both are required, in that order |
| No unbounded quantifier in the *trigger* — "always", "whenever you", "any time", "for any reason", "any/all/every change" | These fire on every session; see *Disjoint triggers* below. The boundary clause may use absolutes freely |
| Valid YAML, and no `---` inside a value | A `---` inside the frontmatter truncates it for readers that split on the marker, silently dropping later fields |

That blocklist is a floor, not a bar. It catches phrasings that are universal on
their face and says nothing about a trigger that is merely broad in meaning —
which stays a review question.

## Quality bar

- **Self-contained.** A skill depends on nothing outside its own folder and makes
  no assumptions about the host repository's layout, tooling, or conventions.
  Every link in `SKILL.md` and in its supporting files must resolve inside the
  folder — `scripts/check_self_contained.py` checks that, ignoring links that
  appear inside code fences so a skill can quote a counter-example. Where a skill
  produces a document, it stores it wherever the host project keeps such
  documents, asking or proposing a location when no convention exists.
- **Agent-agnostic.** No instructions specific to one agent product; anything an
  agent can't do should degrade gracefully.
- **A precise trigger.** The `description` is the *only* thing an agent sees when
  deciding whether to load the skill; the body is read after that decision, so any
  guidance about scope that lives only in the body arrives too late. Write it in
  three parts, in this order:

  1. **Capability** — what the skill does, in one clause, leading with a verb
     (`Restructures existing code without changing its behavior ...`). The open
     format asks a description to say both what the skill does and when to use it;
     hosts that shorten descriptions under context pressure truncate from the end,
     so the capability goes first.
  2. **Trigger** — `Use when ...`, listing concrete, observable situations. Prefer
     symptoms an agent can actually detect in the moment ("a change fans out into
     edits disproportionate to the requirement") over states of the world it cannot
     ("code is badly structured").
  3. **Boundary** — `Do not use ...`, naming the neighbouring skill that owns the
     excluded case. This is what keeps skills from co-firing.

- **Disjoint triggers.** Before adding a skill, check its trigger against every
  existing one. Two skills whose descriptions both match a routine coding task will
  both load, and their combined bodies stay in context for the rest of the session
  in some hosts. If an overlap is unavoidable, resolve it by the *goal* of the work
  rather than the artifact touched — changing behavior, preserving behavior, and
  judging finished behavior are three different skills even though all three touch
  source code.
- **Skimmable body.** Agents read skills mid-task: lead with the point, prefer
  short sections and tables, and push long reference material into supporting
  files linked from `SKILL.md`.

## Adding a skill

1. Create the folder and `SKILL.md` as above.
2. Add a row to the catalog table in [README.md](README.md).
3. Check it locally:

   ```bash
   pip install "skills-ref==0.1.1" "PyYAML==6.0.2"
   python -m skills_ref.cli validate skills/my-skill-name  # the open format
   python3 scripts/lint_skills.py                          # the frontmatter contract
   python3 scripts/check_self_contained.py                 # links stay in the folder
   python3 scripts/check_manifest.py                       # the plugin manifests agree
   ```

   All four also run in CI on every pull request, alongside
   `scripts/test_checks.py`, which pins what the house checks must keep
   rejecting, and an advisory `skillscheck` job that lints the same folders
   against the published specification. They check *structure* — that the
   clauses are present, that no trigger is universally broad, that every link
   resolves. Whether a trigger is drawn in the right place is answered by the
   eval below and by review, not by a substring check.
4. Add at least one case to `evals/triggers.jsonl` (see below).
5. Open a pull request describing the concrete situations the skill is for.

## The trigger eval

The description contract exists so that a prompt loads the one skill that owns
it and does not drag its neighbours along. No mechanical check can confirm that:
a trigger clause can be present, specific, and still drawn in the wrong place.
`evals/triggers.jsonl` is where that claim gets tested. Each line is a realistic
prompt plus two labels — the skills that must fire, and the skills that must
stay silent:

```json
{"prompt": "This is supposed to be a one-line price change and it needs edits in eleven files.",
 "fires": ["refactoring-continuously"], "silent": ["designing-before-coding"]}
```

The two labels are scored separately, because they fail for different reasons. A
skill that does not fire has a trigger missing a situation it owns. A skill that
fires when it should not have has a boundary in the wrong place — and that is
the failure that costs context in every session. A skill named in neither list
is unjudged, so a case can be added for one skill without re-labelling the rest.
Cases where *nothing* should fire matter as much as the positive ones; they are
what catches a trigger that has quietly widened.

Run it against the descriptions as they stand:

```bash
pip install anthropic
python3 scripts/run_trigger_eval.py            # or --case 3 while iterating
```

It needs an API key (or an `ant auth login` profile), costs money per run, and
will not return the same result every time. That is why it is not a pull request
gate: a red tick that comes and goes teaches people to ignore red ticks. It runs
from the **Trigger eval** workflow on demand, and the honest time to run it is
when you change a `description` — the corpus is the record of what those
descriptions promised.

When a case fails, the corpus is as likely to be wrong as the skill. A prompt
that no skill should own, labelled as though one should, is a bad case, not a
bad trigger.

## Packaging

The repository is also installable as a Claude Code plugin, described by two
files in `.claude-plugin/`:

- `plugin.json` — what the plugin is: `name`, `version`, `description`,
  `license`, and its `keywords`.
- `marketplace.json` — how it is advertised, including an entry whose `source`
  points at the directory the skills are installed from.

The name, description and keyword list appear in both. Edit one and you must
edit the other: nothing at install time objects, the listing simply stops
describing the plugin it installs. `scripts/check_manifest.py` is what notices —
it checks that both files parse, that the fields a reader depends on are present,
that `version` is a semantic version, that `license` is the `MIT` every skill
carries, and that the `source` resolves to a directory that ships skills.

Bump `version` in `plugin.json` when the set of skills changes, so installations
can `/plugin marketplace update graitools` onto something newer.

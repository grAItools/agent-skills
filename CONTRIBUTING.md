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
   ```

   All three also run in CI on every pull request, alongside
   `scripts/test_checks.py`, which pins what the two house checks must keep
   rejecting. They check *structure* — that the clauses are present, that no
   trigger is universally broad, that every link resolves. Whether a trigger is
   drawn in the right place is a review question, not a mechanical one, so expect
   that to be discussed on the pull request.
4. Open a pull request describing the concrete situations the skill is for.

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

`SKILL.md` starts with YAML frontmatter. These are the fields this repository
uses; the open format permits others and a reader ignores what it does not
recognise, so this is a floor rather than a whitelist:

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

`scripts/check.sh` catches the mechanical faults: frontmatter that does not
parse, a `name` that does not match its folder, a description too short to route
on or with no indication of when to use the skill, a link that goes nowhere.

It does not check the three-part description shape below, the `license` field, or
whether a trigger is drawn in the right place. Those are review questions, and
the sections that follow are what review asks about them. A validator can tell
you a description is absent or malformed; only a reader can tell you it is
describing the wrong situation.

## Quality bar

- **Self-contained.** A skill depends on nothing outside its own folder and makes
  no assumptions about the host repository's layout, tooling, or conventions.
  Every link in `SKILL.md` and in its supporting files must resolve inside the
  folder. `skillscheck` reports a link that resolves to nothing; a link that does
  resolve but points *out* of the folder is one for review to catch, because it
  looks fine from inside this repository and breaks only once the folder is copied
  somewhere else. Where a skill produces a document, it stores it wherever the
  host project keeps such documents, asking or proposing a location when no
  convention exists.
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
   scripts/check.sh
   ```

4. Open a pull request describing the concrete situations the skill is for, and
   say which existing triggers you checked yours against.

## Checking your work

`scripts/check.sh` is the whole of it, and CI runs that same file rather than its
own copy of the commands. Two validators, neither maintained here:

- **`skills-ref`** — the reference validator for the open format: frontmatter
  syntax, the fields the format defines, the limits it sets.
- **`skillscheck`** — the published specification and its own house rules: broken
  links, leaked secrets, oversized assets, and both plugin manifests, including
  whether their descriptions still agree with each other.

Both are pinned inside the script and run with warnings treated as errors.
Pinning is what makes that safe: a validator that gains checks between releases
would otherwise start failing pull requests that changed nothing. Bump a pin
deliberately, and read what the new version has to say before you do.

What no validator here can tell you is whether a trigger is drawn in the right
place. Two skills whose descriptions both match a routine coding task will both
load, and a substring check cannot notice — that is the thing to argue about in
review, using the three-part shape above.

## Packaging

The repository is also installable as a Claude Code plugin, described by two
files in `.claude-plugin/`:

- `plugin.json` — what the plugin is: `name`, `version`, `description`,
  `license`, and its `keywords`.
- `marketplace.json` — how it is advertised, including an entry whose `source`
  points at the directory the skills are installed from.

The name and description appear in both files, and `marketplace.json` carries the
description a third time under `metadata`. Edit one and you must edit the others:
nothing at install time objects, the listing simply stops describing the plugin it
installs. `skillscheck` is what notices — it reads both manifests, names the
fields a reader depends on when they are missing, and compares the descriptions
across them.

Bump `version` in `plugin.json` when the set of skills changes, so installations
can `/plugin marketplace update graitools` onto something newer, and keep
`metadata.version` in step with it.

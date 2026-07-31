# Contributing a Skill

Every skill in this repository is a folder under `skills/` that any coding agent
supporting the [Agent Skills](https://agentskills.io) format can pick up unchanged.
Keep that portability when adding or editing one.

## Format

```
skills/
└── my-skill-name/
    ├── SKILL.md          # required
    └── ...               # optional supporting files (references, templates, scripts)
```

- The folder name is the skill name: short, kebab-case, verb-led where possible
  (`gathering-requirements`, not `requirements`).
- `SKILL.md` starts with YAML frontmatter containing exactly the fields the open
  format defines — at minimum:

  ```yaml
  ---
  name: my-skill-name        # must match the folder name
  description: Use when ...  # the trigger — states when an agent should load this skill
  ---
  ```

- The body holds the instructions: what the skill is for, when (and when not) to
  use it, how to do the work, and what the deliverable looks like.

## Quality bar

- **Self-contained.** A skill depends on nothing outside its own folder and makes
  no assumptions about the host repository's layout, tooling, or conventions.
  Where it produces a document, it stores it wherever the host project keeps such
  documents, asking or proposing a location when no convention exists.
- **Agent-agnostic.** No instructions specific to one agent product; anything an
  agent can't do should degrade gracefully.
- **A precise trigger.** The `description` is what an agent reads to decide
  whether to load the skill — write it as "Use when ...", concrete enough that it
  neither over- nor under-triggers.
- **Skimmable body.** Agents read skills mid-task: lead with the point, prefer
  short sections and tables, and push long reference material into supporting
  files linked from `SKILL.md`.

## Adding a skill

1. Create the folder and `SKILL.md` as above.
2. Add a row to the catalog table in [README.md](README.md).
3. Open a pull request describing the concrete situations the skill is for.

# Agent Skills

A collection of portable skills for coding agents. Each skill is a self-contained
folder under [`skills/`](skills/) with a `SKILL.md` — YAML frontmatter (`name` +
`description`) followed by instructions — following the open
[Agent Skills](https://agentskills.io) format, so any coding agent that supports
agent skills can use them. Skills make no assumptions about the host repository's
layout and depend on nothing outside their own folder.

## Skills

The current set covers the main software development life cycle tasks:

| Skill | Phase | Use when |
|---|---|---|
| [gathering-requirements](skills/gathering-requirements/SKILL.md) | Requirements & analysis | A new idea, need, defect, or vague request must become an explicit, agreed specification |
| [designing-architecture](skills/designing-architecture/SKILL.md) | Design | Agreed requirements need a technical design / implementation plan, or an architecture needs evaluating |
| [implementing-code](skills/implementing-code/SKILL.md) | Implementation | Writing or modifying source code: features, fixes, refactors |
| [reviewing-and-testing](skills/reviewing-and-testing/SKILL.md) | Review & test | Verifying an implementation against its intent and judging or building its tests |

The SDLC skills chain naturally — spec → design → code → review — with each stage's
output (a spec, a plan, a change, a review report) feeding the next. Each skill also
stands alone: use whichever matches the task at hand. Where a skill produces a
document, it stores it wherever the host project keeps such documents, asking or
proposing a location when no convention exists.

## Using the skills

### Claude Code plugin (recommended)

The repository is an installable Claude Code plugin. From within Claude Code:

```
/plugin marketplace add grAItools/agent-skills
/plugin install graitools@graitools
```

All skills are installed at once and appear namespaced as
`graitools:<skill-name>` (e.g. `graitools:implementing-code`). Updates arrive
via `/plugin marketplace update graitools`.

### Manual copy

Alternatively, copy (or symlink) a skill's folder into wherever your agent
discovers skills. For example:

- **Claude Code** — `.claude/skills/<skill-name>/` in a project, or
  `~/.claude/skills/<skill-name>/` to make it available in every project.
- **Other agents** — any agent supporting the Agent Skills format can load the
  folder from its configured skills directory; check your agent's documentation.

To take everything at once, copy the contents of `skills/` into your agent's skills
directory. Manually copied skills keep their plain names (no `graitools:` prefix).

## Contributing

New skills are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for the format
requirements and quality bar.

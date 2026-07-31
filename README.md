# Agent Skills

A collection of portable skills for coding agents. Each skill is a self-contained
folder under [`skills/`](skills/) with a `SKILL.md` — YAML frontmatter (`name` +
`description`) followed by instructions — following the open
[Agent Skills](https://agentskills.io) format, so any coding agent that supports
agent skills can use them. Skills make no assumptions about the host repository's
layout and depend on nothing outside their own folder.

## Skills

The current set covers the development cycle — **discover → design → implement →
verify → deliver**, wrapped in **continuous refactoring**:

| Skill | Phase | Use when |
|---|---|---|
| [discovering-requirements](skills/discovering-requirements/SKILL.md) | Discover | A new feature, defect report, or vague request needs its purpose, users, and scope dug out before any design or coding |
| [designing-before-coding](skills/designing-before-coding/SKILL.md) | Design | Choosing module boundaries, interfaces, data models, or system structure — or evaluating an existing architecture |
| [implementing-strategically](skills/implementing-strategically/SKILL.md) | Implement | Writing or modifying source code — especially when schedule pressure invites the fastest change that appears to work |
| [verifying-changes](skills/verifying-changes/SKILL.md) | Verify | Work is believed complete, a diff or design needs review, or "all tests pass" is being weighed as enough to ship |
| [delivering-for-feedback](skills/delivering-for-feedback/SKILL.md) | Deliver | A working increment exists and release timing is in question, or development has run for weeks without user contact |
| [refactoring-continuously](skills/refactoring-continuously/SKILL.md) | Ongoing | Touching existing code, a small change fans out into many edits, or an area keeps breaking or resisting new requirements |

The phases chain naturally — each stage's output (a spec, a plan, a change, a
review report, a release) feeds the next — but they interpenetrate (a spiral, not
a waterfall): requirements are discovered by designing and shipping, design
continues during implementation, testing begins before coding, and each release
restarts the loop. Each skill also stands alone: use whichever matches the task
at hand. Where a skill produces a document, it stores it wherever the host
project keeps such documents, asking or proposing a location when no convention
exists.

## Using the skills

### Claude Code plugin (recommended)

The repository is an installable Claude Code plugin. From within Claude Code:

```
/plugin marketplace add grAItools/agent-skills
/plugin install graitools@graitools
```

All skills are installed at once and appear namespaced as
`graitools:<skill-name>` (e.g. `graitools:implementing-strategically`). Updates arrive
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

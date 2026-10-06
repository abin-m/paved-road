---
name: conventions
description: Abin's personal naming, repo-layout, and knowledge-placement conventions. Use when creating or renaming files, branches or repos, starting a new project, or deciding where a piece of knowledge belongs (skill, hook, CLAUDE.md or memory).
---

# conventions

These are the naming and layout rules for personal projects. Consult them before you create anything that has a name or gets saved.

## Naming

| Thing | Rule | Example |
|---|---|---|
| Repos | kebab-case, noun-first | `homelab-infra`, `self-service-cli` |
| Directories and files | kebab-case. Language files follow the language's idiom (`snake_case.py`, `PascalCase.tsx`) | `board-snapshot`, `parse_config.py` |
| Branches | `<type>/<short-topic>` | `feat/oidc-login`, `fix/nginx-502` |
| Commits | Conventional Commits, imperative, subject of 72 characters or fewer | `feat(api): add token refresh` |
| Env vars | SCREAMING_SNAKE, prefixed by tool | `HOMELAB_VAULT_ADDR` |
| Skills | kebab-case directory with a matching `name:` in frontmatter | `skills/iac-change/SKILL.md` |

## Repo layout (personal default)

```
README.md          # what it is, how to run it, in that order
CLAUDE.md          # agent-facing: how to build/test/deploy THIS repo
.claude/           # repo-local skills, rules, settings
docs/              # anything longer than a README section
```

## Where knowledge goes

Decide by scope and by how strictly the rule must hold, not by convenience.

| Kind of knowledge | Where it goes | Why |
|---|---|---|
| A rule that must never be broken | A hook that blocks the tool call | A hook blocks every time. A model can forget a paragraph in a doc. |
| A procedure used in two or more repos | A skill in this pack | It costs one description line per session. The body loads only when the skill is invoked. |
| A procedure specific to one repo | That repo's `CLAUDE.md` or `.claude/skills/` | It helps whoever takes over that repo. It would be clutter in this pack. |
| A fact about how you work, or a standing preference | Memory | |
| Something the code or git history already states | Nowhere | Do not restate it. |

## Docs style

The `writing` skill holds the style for docs, commits, PRs, issues and comments. Load it before writing any of them. The `readme` skill covers the structure of a README.

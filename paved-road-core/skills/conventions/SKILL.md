---
name: conventions
description: Abin's personal naming, repo-layout, and knowledge-placement conventions. Use when creating or renaming files/branches/repos, starting a new project, or deciding where a piece of knowledge belongs (skill vs hook vs CLAUDE.md vs memory).
---

# conventions

The `.editorconfig` of the AI layer for personal projects. Consult before creating anything named or persisted.

## Naming

| Thing | Rule | Example |
|---|---|---|
| Repos | kebab-case, noun-first | `homelab-infra`, `self-service-cli` |
| Directories & files | kebab-case; language files follow language idiom (`snake_case.py`, `PascalCase.tsx`) | `board-snapshot`, `parse_config.py` |
| Branches | `<type>/<short-topic>` | `feat/oidc-login`, `fix/nginx-502` |
| Commits | Conventional Commits, imperative, ≤50-char subject | `feat(api): add token refresh` |
| Env vars | SCREAMING_SNAKE, prefixed by tool | `HOMELAB_VAULT_ADDR` |
| Skills | kebab-case dir + matching `name:` in frontmatter | `skills/iac-change/SKILL.md` |

## Repo layout (personal default)

```
README.md          # what it is, how to run it, in that order
CLAUDE.md          # agent-facing: how to build/test/deploy THIS repo
.claude/           # repo-local skills, rules, settings
docs/              # anything longer than a README section
```

## Where knowledge goes

Decide by *scope* and *enforcement*, not by convenience:

- **A rule that must never be broken** → a **hook** (deterministic block). Prose in a doc depends on a model remembering it.
- **A procedure used in 2+ repos** → a **skill in this pack**. Costs one description line per session; the body loads only when invoked.
- **A procedure specific to one repo** → that repo's `CLAUDE.md` or `.claude/skills/`. It is a handover asset there, cruft here.
- **A fact about how you work / a standing preference** → memory.
- **Something the code or git history already states** → nowhere. Do not restate it.

## Docs style

- Lead with what the thing is and how to run it. Rationale after, not before.
- One example beats three paragraphs. Show the command, show the output shape.
- No status-report prose in committed docs ("recently refactored", "currently working on") — that rots. Put it in the issue.

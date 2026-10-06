# rules/

This directory holds rule files that apply to matching paths. A plugin cannot ship `.claude/rules/` directly, so the master copies live here and each repo copies in the ones it needs:

```sh
mkdir -p .claude/rules && cp <path-to>/paved-road/paved-road-core/rules/<file>.md .claude/rules/
```

A rule file loads into an agent's context only when the agent touches a matching file. It costs nothing until then. Its frontmatter looks like this:

```markdown
---
description: What this rule covers
globs: "**/*.tf"
---
```

Add a file here once a pattern has settled, for example `terraform-patterns.md`, `python-patterns.md` or `dockerfile-patterns.md`. That is better than pasting the same guidance into every repo's `CLAUDE.md`.

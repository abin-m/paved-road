# rules/

Path-scoped rule files. Plugins cannot ship `.claude/rules/` directly, so the canonical copies live here and repos copy in the ones they need:

```sh
mkdir -p .claude/rules && cp <path-to>/paved-road/paved-road-core/rules/<file>.md .claude/rules/
```

A rule file loads into an agent's context only when a matching file is touched — so it costs nothing until it is relevant. Frontmatter:

```markdown
---
description: What this rule covers
globs: "**/*.tf"
---
```

Add files here as patterns stabilise (e.g. `terraform-patterns.md`, `python-patterns.md`, `dockerfile-patterns.md`) rather than pasting the same guidance into every repo's CLAUDE.md.

# Development

## Layout

```
.claude-plugin/marketplace.json     # lists the plugins in this marketplace
paved-road-core/
  .claude-plugin/plugin.json        # name, version, description
  skills/<name>/SKILL.md            # one procedure each
  agents/<name>.md                  # executor and reviewer
  hooks/hooks.json                  # which hook runs on which event
  hooks/<name>-guard.py             # exit 2 blocks the tool call, exit 0 allows it
  hooks/working-style.py            # prints working-style.md at session start
  working-style.md                  # rules added to every session
  bin/                              # scripts, on PATH once the plugin is installed
  tests/guards.test.py              # hook tests
  tests/tools.test.py               # script tests
  rules/                            # rule files a repo can copy into .claude/rules/
tools/lint.py                       # checks manifests, frontmatter and hook wiring
tools/doctor.py                     # checks the hooks work on this machine
.github/workflows/                  # ci.yml and release.yml
```

## Local checks

```sh
python3 tools/lint.py
python3 paved-road-core/tests/guards.test.py
python3 paved-road-core/tests/tools.test.py
python3 paved-road-core/bin/prose-check --warn .
python3 tools/doctor.py
```

Lint fails when:

- a hook script is missing from `hooks.json`, or has no test
- a script in `bin/` has no test, no shebang, or is not executable in git
- a skill's `name` differs from its directory name
- a file name is not kebab-case
- a Python file does not parse on Python 3.9

## Add to the pack

| To add | Create | Also needed |
|---|---|---|
| A procedure | `skills/<name>/SKILL.md` | A `description` that says when to use it. Only that line loads at session start. |
| A persona | `agents/<name>.md` | The shortest `tools` list that does the job. |
| A hard rule | `hooks/<name>-guard.py` | An entry in `hooks.json`, plus a blocked case and an allowed case in `guards.test.py`. |
| A script | `bin/<name>` | A shebang, the executable bit and a case in `tools.test.py`. |

Run `prose-check` on any Markdown you add.

Bump `version` in `plugin.json` when a change is worth pulling.

## What belongs here

- Put a rule that must never be broken in a hook. A hook blocks the tool call every time. A model can forget a paragraph.
- A guard that blocks legitimate work has a bug. Fix the guard and its test. Do not weaken it to let one command through.
- The pack holds what is useful in two or more repos. Knowledge about one repo goes in that repo's `CLAUDE.md` or `.claude/skills/`.
- The pack has no employer paths, tokens or hostnames. Keep team conventions in a second plugin beside `paved-road-core`.

## CI

`ci.yml` runs on every pull request and on every push to `main`.

- The `test` job runs the first four local checks on Ubuntu, macOS and Windows, with Python 3.9 and 3.13.
- The `hook-invocation` job runs the `python3 <script>` command line from `hooks.json`. It fails if a secret read is not blocked.

`release.yml` runs when a `v*` tag is pushed. It checks that the tag matches `version` in `plugin.json`, runs the checks again, and creates a GitHub Release with generated notes.

## Cut a release

1. Bump `version` in `paved-road-core/.claude-plugin/plugin.json` and merge to `main`.
2. Tag that commit and push the tag. Replace `<version>` with the number from step 1.

```sh
git switch main && git pull --ff-only
git tag -a v<version> -m "release: v<version>"
git push origin v<version>
```

Users then run `/plugin marketplace update paved-road`.

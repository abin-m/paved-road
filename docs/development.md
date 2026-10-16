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
  hooks/bash-guards.py              # runs the Bash guards in one process
  hooks/working-style.py            # prints working-style.md at session start
  working-style.md                  # rules added to every session
  bin/                              # scripts, on PATH once the plugin is installed
  tests/guards.test.py              # runs the guard corpus and the session hook
  tests/corpus/<guard>/bypass.jsonl # commands a guard must block
  tests/corpus/<guard>/benign.jsonl # commands a guard must allow
  tests/corpus_lib.py               # loads and runs corpus cases; documents the format
  tests/tools.test.py               # script tests
  rules/                            # rule files a repo can copy into .claude/rules/
tools/lint.py                       # checks manifests, frontmatter and hook wiring
tools/doctor.py                     # checks the hooks work on this machine
tools/bench.py                      # scores each guard against the corpus
.github/workflows/                  # ci.yml and release.yml
```

## Local checks

```sh
python3 tools/lint.py
python3 paved-road-core/tests/guards.test.py
python3 paved-road-core/tests/tools.test.py
python3 paved-road-core/bin/prose-check .
python3 tools/doctor.py
python3 tools/bench.py
```

Lint fails when:

- a hook script is missing from `hooks.json`, or has no test
- a script in `bin/` has no test, no shebang, or is not executable in git
- a skill's `name` differs from its directory name
- a file name is not kebab-case
- a Python file does not parse on Python 3.9

`prose-check` fails when any Markdown file in the repo has a writing fault. Run it with `--warn` to list the faults and still exit 0.

## Add to the pack

| To add | Create | Also needed |
|---|---|---|
| A procedure | `skills/<name>/SKILL.md` | A `description` that says when to use it. Only that line loads at session start. |
| A persona | `agents/<name>.md` | The shortest `tools` list that does the job. |
| A hard rule | `hooks/<name>-guard.py` with a `check(event)` function | Its name in `GUARDS` in `bash-guards.py` for a Bash rule, or an entry in `hooks.json` for another tool. Also its name in `guards.test.py`, and cases in `tests/corpus/<name>/`. |
| A script | `bin/<name>` | A shebang, the executable bit and a case in `tools.test.py`. |

Run `prose-check` on any Markdown you add.

Bump `version` in `plugin.json` when a change is worth pulling.

## What belongs here

- Put a rule that must never be broken in a hook. A hook blocks the tool call every time. A model can forget a paragraph.
- A guard that blocks legitimate work has a bug. Fix the guard and its test. Do not weaken it to let one command through.
- The pack holds what is useful in two or more repos. Knowledge about one repo goes in that repo's `CLAUDE.md` or `.claude/skills/`.
- The pack has no employer paths, tokens or hostnames. Keep team conventions in a second plugin beside `paved-road-core`.

## Guard corpus

Each guard has a directory, `tests/corpus/<guard>/`. Each line in its `bypass.jsonl` is a command the guard must block. Each line in its `benign.jsonl` is one it must allow. `tests/corpus_lib.py` lists the keys. A directory per guard means PRs for different guards don't edit the same file.

Each Bash case also runs through `bash-guards.py`, which applies every guard, as a session does. A benign command must pass all of them.

When a guard gets a case wrong today, mark the line `"known_miss": true` and give the issue that fixes it. The test passes while the guard is still wrong, and fails once it is right, so remove the flag in the same change as the fix.

`bench.py` prints, per guard, the bypasses it catches, the benign commands it blocks, its known misses and the time one call adds. Put its table in the release notes when a guard changes.

## CI

`ci.yml` runs on every pull request and on every push to `main`.

- The `test` job runs the first four local checks and `bench.py` on Ubuntu, macOS and Windows. It uses Python 3.9 and 3.13. `bench.py` only reports, so it never fails the job.
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

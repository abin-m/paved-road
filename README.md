# paved-road

**The paved road for agent-assisted platform work.** A Claude Code plugin pack that gives your agents platform-engineering conventions, DevOps flow, and security guardrails — installed once, inherited in every repo you work in.

The paved road is the supported path: not a fence around what you can do, but the route that is already safe, already conventional, and easier to follow than to reinvent. Deviating is allowed — it just has to be deliberate.

## Install

This repo is **private**. `/plugin marketplace add` shells out to `git clone`, so the rule is simple: **if `git clone <url>` works in your terminal, the install works.** Get access first, then install.

### 0. Access (once, per person)

The repo owner adds you as a collaborator (repo → Settings → Collaborators). Then authenticate git to GitHub — pick one:

```sh
gh auth login                 # easiest: GitHub CLI, sets up HTTPS credentials for you
ssh -T git@github.com         # or verify an existing SSH key: expect "successfully authenticated"
```

Verify before touching Claude Code — this is where private-repo installs actually fail:

```sh
git clone git@github.com:<owner>/paved-road.git /tmp/pr-check && rm -rf /tmp/pr-check
```

### 1. Install the plugin

```
/plugin marketplace add git@github.com:<owner>/paved-road.git
/plugin install paved-road-core@paved-road
```

Use the HTTPS URL (`https://github.com/<owner>/paved-road.git`) instead if you authenticated with `gh auth login`. Iterating on the pack yourself? Point at the working copy — no auth involved:

```
/plugin marketplace add /path/to/paved-road
```

Update later with `/plugin marketplace update paved-road`, then `/plugin` to confirm the version.

### 2. Verify the guards actually enforce

```sh
git clone git@github.com:<owner>/paved-road.git && cd paved-road
python3 tools/doctor.py
```

Expect `All guards enforcing on this machine.` This matters more than it looks: `hooks.json` invokes each guard as `python3 <script>`, and if that name does not resolve, Claude Code records a failed hook rather than a block — the guard fails **open**, silently. `doctor.py` runs the exact command line the harness runs.

### Per-OS notes

**Requirements everywhere:** `git`, and a `python3` on PATH (3.9+). The guards are stdlib-only — nothing to `pip install`.

| OS | Status | Notes |
|---|---|---|
| **macOS** | Supported | `python3` ships with the Xcode command line tools (`xcode-select --install`); Homebrew's (`brew install python`) works too. `gh` via `brew install gh`. |
| **Linux** | Supported | `python3` is present on essentially every distro; otherwise `apt install python3 git` / `dnf install python3 git`. |
| **Windows** | Supported with a caveat | Install Python **from the Microsoft Store** — it provides `python3.exe`, which the python.org installer does *not* (that one gives you `python.exe` and `py.exe` only). Then confirm `python3 --version` responds in the same shell Claude Code uses. If it does not, either fix PATH or change `python3` to `python` in `paved-road-core/hooks/hooks.json`. **WSL2 is the smoother path** — inside WSL everything behaves like Linux. Either way, run `python3 tools/doctor.py` and believe its verdict, not the install docs. |

Windows-specific behaviour that is already handled: the guards normalise `\` to `/` before matching paths, so `C:\repo\.env` is blocked exactly like `repo/.env`.

## What you get

| Component | What it does |
|---|---|
| `/paved-road-core:conventions` | Naming, repo layout, and where knowledge belongs — hook vs skill vs `CLAUDE.md` vs memory |
| `/paved-road-core:session-close` | End-of-session hygiene: no unpushed work, no stranded branches (squash-safe, verified by content), work parked with a note |
| `/paved-road-core:iac-change` | Terraform / Ansible / k8s / Helm discipline: plan → read the blast radius → state the rollback → apply the saved plan → verify the system |
| `/paved-road-core:threat-check` | Pre-merge threat model on the diff: trust boundaries, object-level authz, injection, SSRF, secret handling, supply chain |
| `/paved-road-core:secure-defaults` | Secure-by-default config for containers, Kubernetes, CI pipelines, and cloud IAM — the deltas worth applying every time |
| `/paved-road-core:pipeline-debug` | Work a red pipeline instead of re-running it: classify the failure, reproduce in CI's image, fix the cause |
| `/paved-road-core:incident-response` | Stabilise → capture volatile evidence → diagnose → fix → blameless write-up, in that order |
| `/paved-road-core:release-flow` | Cut, promote, verify, roll back. Build once and promote the same artifact; keep migrations backward-compatible so rollback stays possible |
| `executor` agent | Implementation persona: branch, build, run the project's *full* gate, open the PR, report honestly — including what it could not verify |
| `reviewer` agent | Read-only review persona (no write tools, on purpose). Verifies by content, never by the author's claims; ranks findings blocking / should-fix / nit |
| `secrets-guard` hook | Blocks reads of `.env`, `*.tfvars`, kubeconfigs, private keys, `.ssh/`, `secrets/`, `creds/` — via the file tools *and* via `cat`/`grep` in Bash |
| `main-guard` hook | Blocks commits on `main`/`master` and bulk staging (`git add -A`, `git commit -a`) |
| `prod-guard` hook | Blocks mutating `kubectl`/`helm`/`terraform apply`/`ansible`/`ssh` against anything named prod/staging. Read-only diagnostics always pass; deliberate action is re-run as `PROD_OK=1 <cmd>`, so the authorisation is on the record |

## Design notes

- **Progressive disclosure.** Each skill costs one description line at session start; the procedure loads only when it is invoked. The twentieth skill costs what the first did.
- **Safety is code, not prose.** A rule that must never be broken is a hook that blocks the tool call — not a paragraph a model may or may not recall under pressure.
- **Guardrails are not obstacles.** If a guard blocks legitimate work, that is a defect in the guard. Fix the guard (and its test) — never route around it silently, and never weaken it to unblock one command. The `PROD_OK=1` prefix exists so the exception is visible rather than invisible.
- **Scope rule.** This pack carries only what is useful in **two or more** repos. Repo-specific knowledge belongs in that repo's `CLAUDE.md` or `.claude/skills/`, where it is a handover asset rather than cruft here.

## Layout

```
.claude-plugin/marketplace.json     # marketplace manifest — lists the plugins
paved-road-core/
  .claude-plugin/plugin.json        # plugin manifest — name, version, description
  agents/<name>.md                  # personas (frontmatter: name, description, tools, model)
  skills/<name>/SKILL.md            # procedures (frontmatter: name, description)
  hooks/hooks.json                  # event → matcher → script wiring
  hooks/<name>-guard.py             # guards: JSON on stdin, exit 2 blocks, exit 0 allows
  tests/guards.test.py              # every guard has a test
  bin/                              # helper scripts, on PATH in plugin installs
  rules/                            # path-scoped .claude/rules/ templates repos copy in
tools/lint.py                       # pack lint — manifests, frontmatter, hook wiring
tools/doctor.py                     # post-install check: do the guards enforce here?
.github/workflows/{ci,release}.yml  # test matrix; tag → GitHub Release
```

## CI and releases

Two workflows, both stdlib-only — no third-party actions beyond GitHub's own.

**`ci.yml`** — on every push to `main`, every PR, and on demand:
- `test` matrix: {ubuntu, macOS, windows} × Python {3.9, 3.13} → pack lint + guard tests. The matrix is the point: the guards run on whatever machine installs the plugin, and 3.9 is the floor the README promises.
- `hook-invocation`: asserts the literal `python3 <script>` command line from `hooks.json` returns exit 2 on a secret read — the fails-open case a unit test cannot catch.

**`release.yml`** — on a `v*` tag: verifies the tag matches `version` in `plugin.json` (a tag that disagrees makes "which version am I on?" unanswerable), re-runs lint and tests, then creates a GitHub Release with generated notes. On a private repo the release is visible to exactly the people who can install the pack. No tarball is attached — consumers install from the git ref.

Cutting a release:

```sh
# 1. bump "version" in paved-road-core/.claude-plugin/plugin.json, merge to main
git switch main && git pull --ff-only
git tag -a v0.2.0 -m "release: v0.2.0"
git push origin v0.2.0
```

Consumers then run `/plugin marketplace update paved-road`.

## Tests

Run the whole local gate — the same two commands CI runs, so a local pass and a CI pass cannot diverge:

```sh
python3 tools/lint.py                         # manifests, frontmatter, hook wiring, python floor
python3 paved-road-core/tests/guards.test.py  # every guard, blocked and allowed cases
python3 tools/doctor.py                       # does this machine actually enforce?
```

Every guard needs a case in the test file — blocked *and* allowed. A guard with no allow-case is how you ship a rule that blocks everything; the linter fails the build if a guard has no test at all, or is not wired into `hooks.json`.

## Extending it

- **New procedure** → `paved-road-core/skills/<kebab-name>/SKILL.md`. The `description:` is the only line loaded at session start, so write it as a trigger ("Use when …"), not a summary.
- **New persona** → `paved-road-core/agents/<name>.md`. Narrow the `tools:` list; a reviewer holding `Write` will "helpfully" fix what it was asked to judge.
- **New hard rule** → a hook plus its test. Prose is not enforcement.
- **Bump `version`** in `paved-road-core/.claude-plugin/plugin.json` on anything worth pulling.

## Sharing it

The pack is deliberately org-neutral — no employer-specific paths, tokens, or hostnames. Fork it, or install from this repo directly and keep team-specific conventions in a second plugin beside `paved-road-core` in the same marketplace.

## Licence

MIT — see [LICENSE](LICENSE).

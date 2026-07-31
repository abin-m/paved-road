# paved-road

**The paved road for agent-assisted platform work.** A Claude Code plugin pack that gives your agents platform-engineering conventions, DevOps flow, and security guardrails — installed once, inherited in every repo you work in.

The paved road is the supported path: not a fence around what you can do, but the route that is already safe, already conventional, and easier to follow than to reinvent. Deviating is allowed — it just has to be deliberate.

## Install

```
/plugin marketplace add git@github.com:<you>/paved-road.git
/plugin install paved-road-core@paved-road
```

Any git URL your `git clone` can reach works. Iterating locally? Add the directory instead:

```
/plugin marketplace add /path/to/paved-road
```

Pull updates later with `/plugin marketplace update paved-road`.

**Requirements:** `python3` (3.9+) and `git` on PATH; macOS or Linux. The guards are stdlib-only Python — no dependencies, no runtime to install.

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
```

## Tests

```sh
python3 paved-road-core/tests/guards.test.py
```

Every guard needs a case in there — blocked *and* allowed. A guard with no allow-case is how you ship a rule that blocks everything.

## Extending it

- **New procedure** → `paved-road-core/skills/<kebab-name>/SKILL.md`. The `description:` is the only line loaded at session start, so write it as a trigger ("Use when …"), not a summary.
- **New persona** → `paved-road-core/agents/<name>.md`. Narrow the `tools:` list; a reviewer holding `Write` will "helpfully" fix what it was asked to judge.
- **New hard rule** → a hook plus its test. Prose is not enforcement.
- **Bump `version`** in `paved-road-core/.claude-plugin/plugin.json` on anything worth pulling.

## Sharing it

The pack is deliberately org-neutral — no employer-specific paths, tokens, or hostnames. Fork it, or install from this repo directly and keep team-specific conventions in a second plugin beside `paved-road-core` in the same marketplace.

## Licence

MIT — see [LICENSE](LICENSE).

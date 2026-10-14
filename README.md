# paved-road

[![CI](https://github.com/abin-m/paved-road/actions/workflows/ci.yml/badge.svg)](https://github.com/abin-m/paved-road/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/abin-m/paved-road)](https://github.com/abin-m/paved-road/releases)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)

A Claude Code plugin pack for platform, DevOps and security work. Install it once, and every repo you open gets the same skills, GitHub scripts and safety hooks.

## Quick start

You need `git`, and `python3` on your PATH.

In Claude Code:

```
/plugin marketplace add abin-m/paved-road
/plugin install paved-road-core@paved-road
```

Then confirm the hooks block on your machine:

```sh
git clone https://github.com/abin-m/paved-road.git && cd paved-road
python3 tools/doctor.py
```

The last line should read:

```
All guards enforcing on this machine.
```

If a step fails, see [docs/install.md](docs/install.md).

## Requirements

- Claude Code.
- `git`.
- Python 3.9 or later, as `python3`. The hooks and scripts use the standard library only.
- macOS or Linux. Windows works with Python from the Microsoft Store, or under WSL2.

## How it works

The pack adds four kinds of part to a Claude Code session. Each part runs at a different moment.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/architecture-dark.svg">
  <img alt="The pack's four parts and when each runs" src="docs/images/architecture-light.svg">
</picture>

- The session hook prints `working-style.md` when a session starts, so every session begins with the same rules.
- A skill loads only when a task matches its description. Until then, only its one-line description is in context.
- A guard runs before every matching tool call. It can stop the call, and the model cannot talk its way past it.
- Scripts call the GitHub API with a token that `gh-token` reads from the OS keychain. The value goes to the shell, not to the transcript.

### Guards

Claude Code passes each tool call to the guards as JSON. A guard that exits with code 2 blocks the call, and its message goes back to the agent.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/guard-flow-dark.svg">
  <img alt="How a guard allows or blocks a tool call" src="docs/images/guard-flow-light.svg">
</picture>

This is the guards' real output for three blocked calls and one allowed call:

![Guard output for a blocked secret read, bulk staging, a production kubectl, and an allowed PROD_OK call](docs/images/guards-in-action.svg)

### The work loop

The `planning-flow` skill runs work through GitHub issues and pull requests. The issue is the record, so a new session picks up from GitHub instead of from chat history.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/work-loop-dark.svg">
  <img alt="Eight steps from reading the board to the issue closing on merge" src="docs/images/work-loop-light.svg">
</picture>

## What you get

Skills load when a task matches. You can also call one as `/paved-road-core:<name>`.

| Skill | Use it for |
|---|---|
| `planning-flow` | The work loop from issue to merged PR. |
| `token-setup` | Creating, storing and checking a GitHub token. |
| `conventions` | Naming, repo layout and where a rule belongs. |
| `writing` | Commits, PRs, issues, docs and reports. |
| `readme` | What a README answers and how to test it. |
| `session-close` | Ending a session with nothing unpushed or stranded. |
| `iac-change` | Terraform, Ansible, Kubernetes and Helm changes. |
| `threat-check` | A threat model of the diff before merge. |
| `secure-defaults` | Safe settings for containers, Kubernetes, CI and cloud IAM. |
| `pipeline-debug` | Finding the cause of a failing pipeline. |
| `incident-response` | Stabilising, diagnosing and writing up an incident. |
| `release-flow` | Cutting, promoting and rolling back a release. |

| Script | What it does |
|---|---|
| `gh-token` | Reads a GitHub token from the OS keychain when a command runs. |
| `gh-issue` | Lists, shows, creates, comments on, labels and closes issues. |
| `gh-pr` | Opens, lists, checks, readies and merges PRs. |
| `board` | Writes `board.md` with the open issues and PRs across your repos. |
| `prose-check` | Flags writing faults in Markdown or a commit message. |

| Agent | What it does |
|---|---|
| `executor` | Builds one scoped change, runs the project's checks and opens the PR. |
| `reviewer` | Reviews a change without write access, and runs the checks itself. |

| Hook | What it does |
|---|---|
| `working-style` | Prints `working-style.md` into every new session. |
| `secrets-guard` | Blocks reading `.env`, `*.tfvars`, kubeconfigs, private keys and `secrets/`. |
| `main-guard` | Blocks commits on a default branch, and `git add -A`. |
| `prod-guard` | Blocks changes to anything named prod or staging. |

## Usage

Store a GitHub token once. The scripts then read it each time they run:

```sh
gh-token --store
gh-token --check
GH_TOKEN=$(gh-token) board
```

To run a production command on purpose, start it with `PROD_OK=1`:

```sh
PROD_OK=1 kubectl -n prod rollout undo deployment/api
```

Check your writing before you commit it:

```sh
prose-check README.md docs/
```

Update the pack with `/plugin marketplace update paved-road`.

## Development

```sh
python3 tools/lint.py
python3 paved-road-core/tests/guards.test.py
python3 paved-road-core/tests/tools.test.py
python3 paved-road-core/bin/prose-check .
```

CI runs the same four commands. [docs/development.md](docs/development.md) covers the layout, adding a skill or a hook, and releases.

## Contributing

Bug reports and pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before you open a pull request. Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md).

Report a security problem privately, as described in [SECURITY.md](SECURITY.md).

## Licence

MIT. See [LICENSE](LICENSE).

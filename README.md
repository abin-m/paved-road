# paved-road

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

## Licence

MIT. See [LICENSE](LICENSE).

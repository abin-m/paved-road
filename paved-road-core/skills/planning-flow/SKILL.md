---
name: planning-flow
description: Plan and run work through GitHub issues, a board snapshot, and PRs using the pack's token-backed tools (board, gh-issue, gh-pr). Use when breaking work down, picking up the next task, opening an issue or PR, or asking "what should I work on?".
---

# planning-flow

The loop has five steps: read the board, claim an issue, branch, open a PR, close the issue. State lives in GitHub. It never lives in chat or in an agent's memory.

Every command needs a token. Supply it by command substitution, so the value never enters the transcript. See `token-setup`.

```sh
GH_TOKEN=$(gh-token) <command>
```

## Setup, once per planning repo

Put `board.config.json` in the repo root:

```json
{
  "repos": ["abin-m/paved-road", "abin-m/homelab-infra"],
  "output": "board.md",
  "blocked_label": "blocked",
  "triage_label": "needs-triage",
  "deadlines": [{ "label": "v1.0", "date": "2026-09-01" }]
}
```

Add `board.md` to `.gitignore`. It is a cache that `board` regenerates on demand. GitHub holds the truth.

## 1. Orient

```sh
GH_TOKEN=$(gh-token) board          # writes board.md
```

Read `board.md`. That is one file read in place of many API calls. GitHub has no workflow state of its own, so `board` derives each section:

| Section | Derivation |
|---|---|
| Ready | open, unassigned, not blocked, not awaiting triage |
| In progress | assigned |
| Blocked | carries the blocked label |
| Needs triage | carries the triage label, or has no labels at all |
| Open PRs | open pull requests across the configured repos |

Refresh the board at the start of a session, and whenever its timestamp is too old to trust. An issue with no labels lands in triage on purpose. Labelling an issue is how you accept the work.

## 2. Break work down

Write issues that someone with no context can pick up:

```sh
GH_TOKEN=$(gh-token) gh-issue create \
  --title "feat(auth): add token refresh endpoint" \
  --body-file /tmp/issue.md \
  --label feat
```

A good issue states three things:

- what is being asked
- why it is needed now
- how you will know it is done, which is the acceptance check

Split anything that cannot be finished in one sitting. A multi-day issue is a plan, not a task.

The description is the spec. If a comment changes direction, edit the description. The next reader reads the top and stops.

Use `--body-file` for any body longer than one line. Escaping a long `--body` for the shell causes quoting bugs.

## 3. Claim and branch

You claim an issue by assigning yourself. That moves it out of Ready.

```sh
GH_TOKEN=$(gh-token) gh-issue label 12 --label in-progress   # optional
git switch -c feat/token-refresh
```

Branch naming follows `conventions`: `<type>/<short-topic>`. Use one branch and one PR for each issue. Work one claim at a time. If you take a second claim before the first merges, both stall.

## 4. Open the PR

```sh
GH_TOKEN=$(gh-token) gh-pr open \
  --title "feat(auth): add token refresh endpoint" \
  --body-file /tmp/pr.md \
  --closes 12 \
  --draft            # drop --draft when the gate is green
```

`--closes 12` appends `Closes #12`, so merging closes the issue. The board then stays correct without anyone tidying it. Run the project's full gate before you drop draft status. See the `executor` agent.

## 5. Watch and land

```sh
GH_TOKEN=$(gh-token) gh-pr status            # current branch's PR: checks, reviews, mergeability
GH_TOKEN=$(gh-token) gh-pr ready 9           # draft -> ready for review
GH_TOKEN=$(gh-token) gh-pr merge 9 --squash --delete-branch
```

`gh-pr status` exits non-zero when a check is failing. Take the failure to `pipeline-debug`. Do not re-run it.

A person approves each merge. Leave `gh-pr merge` out of any permission allowlist, so it keeps prompting.

## 6. Close the loop

Merging with `Closes #N` closes the issue. Otherwise:

```sh
GH_TOKEN=$(gh-token) gh-issue close 12 --comment "Shipped in #9." --reason completed
GH_TOKEN=$(gh-token) board                   # refresh the snapshot
```

Then run `session-close`.

## Rules

- The issue is the record. Put progress notes in issue or PR comments, not in chat. The next session reads GitHub, not this conversation.
- Never invent an issue number. Read the board or run `gh-issue list` first. A `Closes #7` that points at the wrong issue closes someone else's work without any warning.
- Do not bulk-close or bulk-label to make a board look tidy. The board shows the real state of the work. To change the board, change the work.
- Ask before you create issues in a repo you were not pointed at. Creating an issue notifies the repo's collaborators.

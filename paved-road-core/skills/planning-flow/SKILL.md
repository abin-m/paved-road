---
name: planning-flow
description: Plan and run work through GitHub issues, a board snapshot, and PRs using the pack's token-backed tools (board, gh-issue, gh-pr). Use when breaking work down, picking up the next task, opening an issue or PR, or asking "what should I work on?".
---

# planning-flow

One loop: **board → claim → branch → PR → close.** State lives in GitHub, never in chat and never in an agent's memory.

All commands need a token; supply it by command substitution so the value never enters the transcript (see `token-setup`):

```sh
GH_TOKEN=$(gh-token) <command>
```

## Setup, once per planning repo

`board.config.json` in the repo root:

```json
{
  "repos": ["abin-m/paved-road", "abin-m/homelab-infra"],
  "output": "board.md",
  "blocked_label": "blocked",
  "triage_label": "needs-triage",
  "deadlines": [{ "label": "v1.0", "date": "2026-09-01" }]
}
```

Git-ignore `board.md` — it is a cache, regenerated on demand, not a source of truth.

## 1. Orient

```sh
GH_TOKEN=$(gh-token) board          # writes board.md
```

Read `board.md` — one file read instead of N API calls. Sections are **derived**, since GitHub has no native workflow state:

| Section | Derivation |
|---|---|
| Ready | open, unassigned, not blocked, not awaiting triage |
| In progress | assigned |
| Blocked | carries the blocked label |
| Needs triage | carries the triage label, **or has no labels at all** |
| Open PRs | open pull requests across the configured repos |

Refresh the board at the start of a session, or whenever its timestamp is too old to trust. An unlabelled issue lands in triage by design — labelling is the act of accepting work.

## 2. Break work down

Write issues that can actually be picked up cold:

```sh
GH_TOKEN=$(gh-token) gh-issue create \
  --title "feat(auth): add token refresh endpoint" \
  --body-file /tmp/issue.md \
  --label feat
```

A good issue states: **what** is being asked, **why** now, and **how you will know it is done** (the acceptance check). Split anything that cannot be finished in one sitting — a multi-day issue is a plan, not a task. The description is the spec: if a comment changes direction, edit the description, because the next person reads the top and stops.

Use `--body-file` for anything multi-line; shell-escaping a long `--body` is where quoting bugs come from.

## 3. Claim and branch

Claiming is assigning yourself — that is what moves the issue out of Ready:

```sh
GH_TOKEN=$(gh-token) gh-issue label 12 --label in-progress   # optional
git switch -c feat/token-refresh
```

Branch naming follows `conventions`: `<type>/<short-topic>`. One issue, one branch, one PR. Work one claim at a time; a second claim before the first merges is how both stall.

## 4. Open the PR

```sh
GH_TOKEN=$(gh-token) gh-pr open \
  --title "feat(auth): add token refresh endpoint" \
  --body-file /tmp/pr.md \
  --closes 12 \
  --draft            # drop --draft when the gate is green
```

`--closes 12` appends `Closes #12`, so merging closes the issue — the board stays true without anyone tidying it. Run the project's full gate *before* dropping draft status (see the `executor` agent).

## 5. Watch and land

```sh
GH_TOKEN=$(gh-token) gh-pr status            # current branch's PR: checks, reviews, mergeability
GH_TOKEN=$(gh-token) gh-pr ready 9           # draft -> ready for review
GH_TOKEN=$(gh-token) gh-pr merge 9 --squash --delete-branch
```

`gh-pr status` exits non-zero when a check is failing — take the failure to `pipeline-debug` rather than re-running it. Merging is a human gate: leave `gh-pr merge` out of any permission allowlist so it keeps prompting.

## 6. Close the loop

Merging with `Closes #N` closes the issue. Otherwise:

```sh
GH_TOKEN=$(gh-token) gh-issue close 12 --comment "Shipped in #9." --reason completed
GH_TOKEN=$(gh-token) board                   # refresh the snapshot
```

Then run `session-close`.

## Rules that keep this honest

- **The issue is the record.** Progress notes go in issue or PR comments, not in chat — the next session reads GitHub, not this conversation.
- **Never invent issue numbers.** Read the board or `gh-issue list` first; a `Closes #7` pointing at the wrong issue silently closes someone else's work.
- **Do not bulk-close or bulk-label** to make a board look tidy. The board reflects reality; edit reality.
- **Ask before creating issues in a repo you were not pointed at.** Issue creation is outward-facing — collaborators get notified.

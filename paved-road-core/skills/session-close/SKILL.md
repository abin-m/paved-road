---
name: session-close
description: End-of-session hygiene for personal repos. No stranded branches, no uncommitted work, merges verified by content, open work parked with a note. Use when wrapping up a work session or before switching machines or projects.
---

# session-close

Run this before you end a session. Every step is a check with a defined action on failure. Do not report "clean" without running them.

## 1. Uncommitted work

```sh
git status --porcelain
```

- If the output is empty, go to the next step.
- Otherwise commit the work on a topic branch, or stash it with a named message: `git stash push -m "wip: <topic>"`. Never leave a stash without a name.

## 2. Unpushed commits

```sh
git log --branches --not --remotes --oneline
```

Anything listed exists only on this machine. Push the branch, even if the work is incomplete. An unpushed branch is lost if this disk fails.

## 3. Stranded branches

`git branch --merged` gives wrong answers under squash-merge. Squashed work shows as unmerged, and `git branch -d` refuses to delete it. Verify by content:

```sh
for b in $(git branch --format='%(refname:short)' | grep -v -E '^(main|master)$'); do
  if [ -z "$(git diff main.."$b" -- .)" ]; then
    echo "MERGED-BY-CONTENT: $b"   # safe to delete: git branch -D "$b"
  else
    echo "UNMERGED:          $b"
  fi
done
```

Delete the branches that are merged by content. For a branch that is really unmerged, open a PR or write in the issue what remains. A branch with no note is lost work.

## 4. Open PRs

List them. For each PR, state whether it is waiting on CI, on review, or on you. If a PR is waiting on you, leave a comment before you go. Without one, the next session has to rebuild the whole context.

## 5. Park the work

Write the state where the next session will look: the issue, the PR description, or the repo's `CLAUDE.md`. Never leave it only in chat or in memory. Give one line each for what is done, what is next, and what is blocked and on what.

## Output

Report the checklist with a verdict for each item. If something failed and you could not fix it, say so plainly and include the command output. A false "clean" is worse than no check.

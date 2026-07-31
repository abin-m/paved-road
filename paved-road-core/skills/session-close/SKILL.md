---
name: session-close
description: End-of-session hygiene for personal repos — no stranded branches, no uncommitted work, merges verified by content, open work parked with a note. Use when wrapping up a work session or before switching machines/projects.
---

# session-close

Run before ending a session. Every step is a check with a defined failure action — do not report "clean" without running them.

## 1. Uncommitted work

```sh
git status --porcelain
```

- Empty → next step.
- Non-empty → either commit it on a topic branch, or stash with a *named* message (`git stash push -m "wip: <topic>"`). Never leave anonymous stashes.

## 2. Unpushed commits

```sh
git log --branches --not --remotes --oneline
```

Anything listed is work that exists only on this machine. Push the branch, even if incomplete — an unpushed branch is a single-disk-failure away from gone.

## 3. Stranded branches

`git branch --merged` lies under squash-merge: squashed work shows as unmerged and `git branch -d` refuses to delete it. Verify by content instead:

```sh
for b in $(git branch --format='%(refname:short)' | grep -v -E '^(main|master)$'); do
  if [ -z "$(git diff main.."$b" -- .)" ]; then
    echo "MERGED-BY-CONTENT: $b"   # safe to delete: git branch -D "$b"
  else
    echo "UNMERGED:          $b"
  fi
done
```

Delete the merged-by-content ones. For anything genuinely unmerged, either open a PR or write down in the issue what remains — a branch with no note is lost work.

## 4. Open PRs

List them and state, per PR: is it waiting on CI, on review, or on you? A PR waiting on *you* that you leave without a comment costs a full context reload next session.

## 5. Park the work

Write the state where the next session will look: the issue, the PR description, or the repo's `CLAUDE.md` — never chat, never memory alone. One line each: what is done, what is next, what is blocked and on what.

## Output

Report the checklist with a verdict per item. If something failed and you could not fix it, say so plainly with the command output — a false "clean" here is worse than no check.

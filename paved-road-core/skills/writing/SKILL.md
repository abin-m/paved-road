---
name: writing
description: How to write commits, PR descriptions, issues, code comments, docs, runbooks, incident write-ups and end-of-task reports so a reader arriving cold can act on them. Load it when you draft or review one of them, or when `prose-check` reports a fault.
---

# writing

Your reader was not in the session. They are a reviewer with ten other PRs, an on-call engineer in the middle of an incident, or you in six months. Write so they can act after one read, without asking you a question.

## Three tests

Run these on anything you are about to send or commit.

1. First line. If the reader stops after the first sentence, do they know what happened or what you need from them?
2. Cold reader. Would someone who never saw this session understand every term? Replace any label you made up while working with the thing it stands for.
3. Cut. Remove each sentence in turn. If the reader loses nothing, leave it out.

## Faults

The faults are named. A review can then say "buried-point in the PR description" and be understood. `prose-check` reports the ones marked yes under their names.

| Fault | Example or sign | Repair | Checked |
|---|---|---|---|
| `buried-point` | Background first, the request in the last paragraph. A title that names a topic: "Token handling". | Put the request or the outcome first: "Rotate the deploy token". | no |
| `slogan` | A line built to be quoted: "Prose is not enforcement." | State the rule and what it binds: "A hard rule needs a hook and a test." | no |
| `vague-subject` | "This", "it" or "the logic" with no named thing behind it. | Name the file, the command or the person. | no |
| `coined-label` | A nickname from the session: "the fails-open case". | Say what it stands for: "the guard exits 0 when `python3` is missing". | no |
| `dash-aside` | A second thought hung on a dash in the middle of a sentence. | Write two sentences. | yes |
| `semicolon-chain` | Clauses strung together with semicolons. | End the sentence. | yes |
| `long-sentence` | More than 30 words. | Split at "and", "but" or "which". | yes |
| `arrow-word` | "plan → apply → verify" | "Plan, then apply, then verify." | yes |
| `filler` | "note that", "in order to", "it is worth noting" | Delete the phrase. The sentence survives. | yes |
| `buzzword` | "robust", "seamless", "leverage" | Use the plain word, or give the number that earned the adjective. | yes |
| `status-prose` | "recently", "currently" in a committed doc | State the fact. Put progress in the issue, where it gets closed. | yes |
| `loud-bold` | A bold lead-in on every bullet. | Keep bold for the one warning a skimmer must not miss. | yes |

One rewrite, of a line from this pack's own README:

> **Safety is code, not prose.** A rule that must never be broken is a hook that blocks the tool call — not a paragraph a model may or may not recall under pressure.

It has a slogan, heavy bold and a dash aside. The same content, repaired:

> Put a rule that must never be broken in a hook. A hook blocks the tool call every time. A model can forget a paragraph.

## What each kind of text needs

| Text | Opens with | Then | Leave out |
|---|---|---|---|
| Commit | A Conventional Commits subject, imperative, 72 characters or fewer. | A body that says why the change was needed. | A walk through the diff. |
| PR description | What changes for someone who uses the code. | Why, what you ran and its result, what you could not verify, `Closes #N`. | The story of how you got there. |
| Issue | A title that starts with a verb: "Support OIDC login", "Stop `board` dropping draft PRs". | The problem or the need, and how to tell it is done. | A proposed design, unless that is the request. |
| Code comment | The reason the code cannot show: why this value, which failure this guard prevents. | Nothing. Two lines at most. | History and issue numbers. The commit holds those. |
| Docstring | A one-line summary: the behaviour and the return value. | Arguments or errors a caller would get wrong. | How it is implemented. |
| Doc or README | What the thing is and how to run it. | One example with the command and the shape of its output. Rationale last. | Anything stated elsewhere. Link to it. |
| Runbook | The first command to run. | For each step, the output that means it worked and what to do if it differs. | Background before step one. |
| Incident write-up | Impact and duration in one sentence. | A UTC timeline of facts, then cause, then actions with owners. | Names of people as causes. Guesses stated as facts. |
| End-of-task report | The result: done, failed or blocked. | What you ran and its outcome, what you did not verify, what you need from the reader. | A summary that hides a failing check. Paste the output. |

## Checking

```sh
prose-check docs/ README.md              # files, or directories searched for *.md
git log -1 --format=%B | prose-check -   # a commit message or PR body on stdin
prose-check --warn .                     # report, but exit 0
```

Each finding prints as `file:line: fault: fix`. The exit code is 1 when there are findings.

The checker reads prose only. It skips frontmatter, fenced code, tables, block quotes and inline code. To quote a bad example outside a block quote, put `<!-- prose-check off -->` before it and `<!-- prose-check on -->` after it.

A clean run proves less than it seems to. The checker cannot see a buried point, a slogan or a missing subject, so run the three tests yourself. When a finding sits on a sentence that carries a rule, rewrite the sentence and keep the rule.

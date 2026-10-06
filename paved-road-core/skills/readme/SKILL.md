---
name: readme
description: What a repo's README must answer, in what order, and how to prove its commands work. Use when you draft or review a README, or when a quick start fails for someone new.
---

# readme

The page has one reader at two moments. First they decide whether to use the project, and then they try to get it running. So it answers four questions in this order.

1. What is this, and who is it for?
2. Can I use it? That covers the supported systems, the access needed and the versions.
3. How do I get a first result?
4. Where is everything else?

Follow `writing` for the sentences. This skill covers the page.

## Sections

Use the ones the project needs, in this order.

| Section | Holds | Limit |
|---|---|---|
| Summary | What the project does and who uses it. | Three sentences, directly under the title. |
| Quick start | The fewest commands from clone to a visible result. | Five commands. |
| Requirements | Tools with versions, accounts, access and supported systems. | Only what the quick start needs. |
| Usage | One heading for each task a user comes to do. | A command and the shape of its output for each. |
| Configuration | The settings most people change, with defaults. | A table. Link to the full list. |
| Troubleshooting | Failures people hit, under the exact error text. | One cause and one fix for each. |
| Development | How to run the tests and the full local gate. | The commands CI runs. |
| Licence | The licence name and a link to the file. | One line. |

## Rules for commands

- A reader must be able to paste a command and run it. Mark a value they must change as `<angle-brackets>`, and say what goes there.
- Show the output wherever the reader has to judge whether a step worked.
- Name a requirement before the step that needs it.
- When a quick start needs more than five commands, shorten the setup. A longer explanation does not make the setup easier.

## What to leave out

- Anything `--help`, the file tree or the changelog already shows. Link to it.
- Design history and internals. Put them in `docs/`.
- Instructions for agents. Those belong in `CLAUDE.md`.
- Progress notes. An issue holds those, and it gets closed.

Move reference material to `docs/` once the page passes about 200 lines.

## Before you hand it over

1. Clone the repo into an empty directory and follow the quick start exactly as written. Fix the page wherever you had to improvise.
2. Open every link.
3. Run `prose-check README.md`.
4. Read only the first screen. A stranger should be able to name the project's purpose and the first command.

If you could not run a step, for example because it needs cloud access, say which step in your report.

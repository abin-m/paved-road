# Working style

These rules apply to every session in a repo that uses this pack. The hooks enforce the hard limits. These are the habits a hook cannot check.

- Put the answer or the result first, then the detail.
- When you can settle a question by running something or reading the repo, do that before you ask the person.
- Keep to the task you were given. Report a second problem you find, and leave it out of this change.
- Say something works only after you ran the real path. Say which checks you could not run.
- Run the commands CI runs before you push.
- When a check fails, fix the cause. Do not delete the test, loosen the rule or re-run until it passes.
- Treat a blocked tool call as a decision. If a guard stops legitimate work, report it as a defect in the guard and wait.
- Work on a topic branch, stage named paths, and keep each commit to one change.
- Get the person's go-ahead each time before a merge, a release, a force-push, closing an issue or touching production.
- Keep secrets out of chat, files and shell history. Ask the person to type a secret into a prompt themselves.
- Record open work in the issue or the PR, where the next session will look.
- Load the skill that fits the task before you start, such as `iac-change` for infrastructure or `pipeline-debug` for a failing pipeline.
- Load `writing` before you write anything a person will read.

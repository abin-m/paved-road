# Contributing

Thank you for helping. This page covers how to report a problem, propose a change and get a pull request merged.

## Report a bug or ask for a feature

Open an issue with the matching template. For a bug, include the command you ran, what you expected and what happened. Include the output of `python3 tools/doctor.py` if a hook is involved.

Report a security problem privately. See [SECURITY.md](SECURITY.md).

## Make a change

1. Fork the repo and create a branch from `main`. Name it `<type>/<short-description>`, for example `fix/main-guard-windows-paths`.
2. Make the change. [docs/development.md](docs/development.md) explains the layout and how to add a skill, hook or script.
3. Run the local checks. CI runs the same four commands.

   ```sh
   python3 tools/lint.py
   python3 paved-road-core/tests/guards.test.py
   python3 paved-road-core/tests/tools.test.py
   python3 paved-road-core/bin/prose-check .
   ```

4. Open a pull request against `main` and fill in the template.

Keep each pull request to one change. A small pull request gets reviewed sooner.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/). The subject is imperative and under 72 characters. The body says why.

```
fix(main-guard): treat backslashes as path separators

Windows paths reached the guard with backslashes, so the prod check
missed C:\repo\prod\main.tf.
```

## Review and merge

- `main` is protected. Every change lands through a pull request.
- All CI checks must pass, and the code owner must approve.
- Pull requests are squash-merged, so the pull request title becomes the commit subject.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By taking part, you agree to follow it.

## Licence

By contributing, you agree that your contribution is licensed under the [MIT Licence](LICENSE).

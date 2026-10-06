---
name: token-setup
description: Mint a GitHub token, store it in the OS keychain, and verify it works with the pack's tools. Use when gh-token, gh-issue, gh-pr or board fails on auth, or when setting up a new machine.
---

# token-setup

The pack's GitHub tools (`gh-issue`, `gh-pr`, `board`) read a token from the OS keychain each time they run. The token never lands in a file, in shell history, or in an agent's context.

## 1. Mint the token

On GitHub, open Settings, then Developer settings, then Personal access tokens.

A classic token is the simplest choice and works everywhere:

- Give it the `repo` scope. Private repos, issue creation and PR merges need it. `public_repo` alone returns 403 on any private repo.
- Set an expiry. 90 days is a reasonable default. `gh-token --check` reports the expiry date, so you see a renewal coming.

A fine-grained token is tighter and takes more setup. Select the specific repositories, then grant these repository permissions:

- Contents: Read and write
- Issues: Read and write
- Pull requests: Read and write
- Metadata: Read

## 2. Store it in the keychain

```sh
gh-token --store
```

That hands off to the OS tool, which prompts for the secret. Nothing is echoed, and nothing enters shell history. The command it runs depends on the system:

- macOS: `security add-generic-password -U -s github.com -a api -w`
- Linux: `secret-tool store --label='GitHub API token' service github.com account api`. This needs `libsecret-tools`.
- Windows has no keychain backend. Set `GH_TOKEN` in your PowerShell profile, or run `gh auth login` and let the `gh` CLI hold the token. The tools fall back to both.

## 3. Verify

```sh
gh-token --check
```

Expect one line: `ok: token from keychain, user <you>, scopes [repo], expires <date>`. It warns if `repo` is missing.

## 4. Use it

Always pass the token by command substitution. The value then goes to the shell and never into the transcript.

```sh
GH_TOKEN=$(gh-token) gh-issue list
GH_TOKEN=$(gh-token) board
```

Never `echo` the token, never write it to a file, and never paste it into a chat or an issue. If one leaks, revoke it on GitHub first, then mint a new one. Rotating a token costs minutes. A leaked token that still works can cost far more.

## Resolution order

`gh-token` returns the first token it finds, in this order:

1. the keychain
2. `GH_TOKEN` or `GITHUB_TOKEN`
3. `gh auth token`

A stale exported `GH_TOKEN` therefore cannot override the keychain, but it does override the `gh` CLI. That explains a `--check` that reports a source you did not expect.

## When it still fails

| Symptom | Cause | Fix |
|---|---|---|
| `no token found` | nothing stored | `gh-token --store` |
| `401` | token revoked or expired | mint a new one, `--store` again |
| `403` on a write | missing `repo` scope | re-mint with `repo` |
| `404` on a repo you can see in the browser | fine-grained token not granted that repository | add the repo to the token, or use a classic token |
| works in terminal, fails under the agent | agent shell lacks keychain access (fresh login/SSH session) | unlock the keychain, or export `GH_TOKEN` for that session |

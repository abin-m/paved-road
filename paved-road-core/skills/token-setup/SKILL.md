---
name: token-setup
description: Mint a GitHub token, store it in the OS keychain, and verify it works with the pack's tools. Use when gh-token, gh-issue, gh-pr or board fails on auth, or when setting up a new machine.
---

# token-setup

The pack's GitHub tools (`gh-issue`, `gh-pr`, `board`) read a token **at use time** from the OS keychain. The token never lands in a file, in shell history, or in an agent's context.

## 1. Mint the token

GitHub → Settings → Developer settings → Personal access tokens.

**Classic token** — simplest, works everywhere:
- Scope `repo` (needed for private repos, issue creation, PR merges). `public_repo` alone will 403 the moment a repo is private.
- Set an expiry. 90 days is a reasonable default; the tools report the expiry date in `gh-token --check`, so renewal is not a surprise.

**Fine-grained token** — tighter, more setup: select the specific repositories, then grant **Repository permissions** → Contents: Read and write, Issues: Read and write, Pull requests: Read and write, Metadata: Read.

## 2. Store it in the keychain

```sh
gh-token --store
```

That hands off to the OS tool, which prompts for the secret. Nothing is echoed, and nothing enters shell history. Under the hood:

- **macOS** — `security add-generic-password -U -s github.com -a api -w`
- **Linux** — `secret-tool store --label='GitHub API token' service github.com account api` (needs `libsecret-tools`)
- **Windows** — no keychain backend. Either set `GH_TOKEN` in your PowerShell profile, or run `gh auth login` and let the `gh` CLI hold it — the tools fall back to both.

## 3. Verify

```sh
gh-token --check
```

Expect one line: `ok: token from keychain, user <you>, scopes [repo], expires <date>`. It warns if `repo` is missing.

## 4. Use it

Always by command substitution, so the value goes to the *shell*, never into the transcript:

```sh
GH_TOKEN=$(gh-token) gh-issue list
GH_TOKEN=$(gh-token) board
```

Never `echo` the token, never write it to a file, never paste it into a chat or an issue. If one leaks, revoke it on GitHub first and mint a new one second — rotation is cheap, a live leaked token is not.

## Resolution order

`gh-token` returns the first hit: **keychain → `GH_TOKEN`/`GITHUB_TOKEN` → `gh auth token`**. A stale exported `GH_TOKEN` therefore cannot shadow the keychain, but it *does* shadow the `gh` CLI — if `--check` reports a source you did not expect, that is why.

## When it still fails

| Symptom | Cause | Fix |
|---|---|---|
| `no token found` | nothing stored | `gh-token --store` |
| `401` | token revoked or expired | mint a new one, `--store` again |
| `403` on a write | missing `repo` scope | re-mint with `repo` |
| `404` on a repo you can see in the browser | fine-grained token not granted *that* repository | add the repo to the token, or use a classic token |
| works in terminal, fails under the agent | agent shell lacks keychain access (fresh login/SSH session) | unlock the keychain, or export `GH_TOKEN` for that session |

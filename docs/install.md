# Install

## Access

The repo is private. The owner adds you as a collaborator under Settings, then Collaborators.

Sign git in to GitHub with one of these:

```sh
gh auth login            # GitHub CLI, sets up HTTPS credentials
ssh -T git@github.com    # an existing SSH key, expect "successfully authenticated"
```

Check access before you open Claude Code. `/plugin marketplace add` runs `git clone`, so a clone that fails here fails there too.

```sh
git clone git@github.com:abin-m/paved-road.git /tmp/pr-check && rm -rf /tmp/pr-check
```

## Install the plugin

```
/plugin marketplace add git@github.com:abin-m/paved-road.git
/plugin install paved-road-core@paved-road
```

Use `https://github.com/abin-m/paved-road.git` if you signed in with `gh auth login`.

To work on the pack itself, add your clone by path. This needs no sign-in.

```
/plugin marketplace add <path-to-your-clone>
```

Update with `/plugin marketplace update paved-road`. Run `/plugin` to see the installed version.

## Check the hooks

```sh
python3 tools/doctor.py
```

`hooks.json` runs each hook as `python3 <script>`. If `python3` is not on your PATH, Claude Code records a failed hook and lets the tool call through. Nothing warns you. `doctor.py` runs the same command line and reports whether each guard blocks.

## Operating systems

| System | Notes |
|---|---|
| macOS | `python3` comes with `xcode-select --install`, or `brew install python`. |
| Linux | `apt install python3 git` or `dnf install python3 git` if they are missing. |
| Windows | Install Python from the Microsoft Store. It provides `python3.exe`. The python.org installer provides only `python.exe` and `py.exe`. WSL2 behaves like Linux. |

On Windows, confirm `python3 --version` answers in the shell Claude Code uses. If it does not, fix your PATH, or change `python3` to `python` in `paved-road-core/hooks/hooks.json`.

The guards treat `\` as `/` in paths, so `C:\repo\.env` is blocked like `repo/.env`.

## GitHub token

`gh-issue`, `gh-pr` and `board` need a classic token with the `repo` scope.

```sh
gh-token --store     # the OS prompt takes the secret
gh-token --check     # prints the user, scopes and expiry
```

Pass the token by command substitution. The value then goes to the shell and stays out of the agent's context.

```sh
GH_TOKEN=$(gh-token) gh-issue list
```

The token is kept in the macOS Keychain or in Linux libsecret. Windows has no keychain backend, so `gh-token` uses `GH_TOKEN` or the `gh` CLI there.

`/paved-road-core:token-setup` has the full steps and a table of failure codes.

## Permissions

To stop Claude Code asking before each script call, add this to `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(gh-token:*)", "Bash(board:*)", "Bash(prose-check:*)",
      "Bash(gh-issue list:*)", "Bash(gh-issue show:*)", "Bash(gh-issue comment:*)",
      "Bash(gh-issue create:*)", "Bash(gh-issue label:*)",
      "Bash(gh-pr open:*)", "Bash(gh-pr list:*)", "Bash(gh-pr status:*)"
    ]
  }
}
```

`gh-pr merge` and `gh-issue close` are left out. A person should approve a merge or a close each time.

## Troubleshooting

### `Permission denied (publickey)` or `Repository not found`

Git cannot reach the repo. Ask the owner to add you as a collaborator, then repeat the steps under Access.

### `python3 does not resolve`

`doctor.py` prints this when `python3` is not on your PATH. No guard blocks anything until you fix it. See Operating systems.

### `gh-token --check` reports an error

Run `/paved-road-core:token-setup`. It lists each failure code and its fix.

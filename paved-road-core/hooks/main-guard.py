#!/usr/bin/env python3
"""main-guard.py — block commits to a default branch and bulk staging.

Claude Code Bash PreToolUse hook: exit 2 blocks, exit 0 allows. Stdlib only.

Two rules, both deterministic because both are rules a model forgets under
pressure:
  1. No `git commit` while HEAD is main/master — branch first.
  2. No `git add -A` / `-u` / `.` / `git commit -a` — a dirty tree sweeps
     unrelated work into the commit. Stage explicit paths.

Commands are read as shell words, so a commit message that mentions `-a`
is not mistaken for the flag.
"""

import json
import os
import shlex
import subprocess
import sys

DEFAULT_BRANCHES = {"main", "master", "trunk", "develop"}

# Programs that run a command string given with -c.
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
# Pathspecs that stage the whole tree. The shell expands `*` before git runs.
WHOLE_TREE = {".", "./", ":/", ":", "*", ":/*"}
# git options before the subcommand that take the next word as their value.
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
# commit options that take the next word as their value, which may start with "-".
COMMIT_VALUE_OPTS = {"-m", "--message", "-F", "--file", "-C", "-c", "-t", "--template",
                     "--author", "--date", "--fixup", "--squash", "--cleanup"}


def block(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def current_branch(cwd: str) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd or None,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def git_commands(cmd: str) -> list:
    """(directory, subcommand, args) for each git command in a shell command.

    The directory is relative to the session's cwd and follows `git -C`.
    Commands inside backticks, `$(...)`, `sh -c '...'` and `eval` count too.
    """
    # A backtick runs its contents even inside double quotes, so treat it as
    # a command boundary.
    cmd = cmd.replace("`", " ; ")
    try:
        lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []  # unbalanced quotes: the shell will refuse the command

    commands, words = [], []
    for token in tokens + [";"]:
        if token and set(token) <= set(";&|()"):
            if words:
                commands.append(words)
            words = []
        else:
            words.append(token)

    found = []
    for words in commands:
        program = os.path.basename(words[0])
        if program in SHELLS and "-c" in words[:-1]:
            found += git_commands(words[words.index("-c") + 1])
            continue
        if program == "eval":
            found += git_commands(" ".join(words[1:]))
            continue
        try:
            i = next(n for n, w in enumerate(words) if os.path.basename(w) == "git") + 1
        except StopIteration:
            continue
        directory = ""
        while i < len(words) and words[i].startswith("-"):
            if words[i] == "-C" and i + 1 < len(words):
                directory = os.path.join(directory, words[i + 1])
            i += 2 if words[i] in GIT_VALUE_OPTS else 1
        if i < len(words):
            found.append((directory, words[i], words[i + 1:]))
    return found


def _short_flags(arg: str) -> str:
    """Letters of a short-flag cluster such as -Av, or "" for anything else."""
    return arg[1:] if arg.startswith("-") and not arg.startswith("--") else ""


def bulk_add(args: list) -> bool:
    """True when `git add` args stage the whole tree or every tracked change."""
    for arg in args:
        if arg in ("--all", "--update", "-A", "-u") or set("Au") & set(_short_flags(arg)):
            return True
        if arg in WHOLE_TREE:
            return True
    return False


def commit_all(args: list) -> bool:
    """True when `git commit` args include -a or --all."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in COMMIT_VALUE_OPTS:
            i += 2
            continue
        if arg == "--all" or (not arg.startswith(("-m", "-F", "-C", "-c", "-t"))
                              and "a" in _short_flags(arg)):
            return True
        i += 1
    return False


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if event.get("tool_name") != "Bash":
        sys.exit(0)

    cmd = (event.get("tool_input") or {}).get("command", "") or ""
    cwd = event.get("cwd") or os.getcwd()

    for directory, sub, args in git_commands(cmd):
        if sub == "add" and bulk_add(args):
            block(
                "BLOCKED (bulk staging): `git add -A` / `-u` / `.` sweeps unrelated "
                "work into the commit. Stage explicit paths: git add <file> ..."
            )
        if sub == "commit" and commit_all(args):
            block(
                "BLOCKED (implicit add): `git commit -a` commits every tracked change. "
                "Stage explicit paths, then commit without -a."
            )
        if sub == "commit":
            branch = current_branch(os.path.join(cwd, directory))
            if branch in DEFAULT_BRANCHES:
                block(
                    f"BLOCKED (commit on {branch}): create a topic branch first — "
                    f"git switch -c <type>/<short-topic>"
                )

    sys.exit(0)


if __name__ == "__main__":
    main()

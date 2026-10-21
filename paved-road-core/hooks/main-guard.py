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
# switch and checkout options that create the branch named by the next word.
CREATE_OPTS = {"-c", "-C", "--create", "--force-create", "-b", "-B"}
# Commands that change directory, so a later git command may be in another repo.
CD_PROGRAMS = {"cd", "pushd", "popd"}
# git subcommands that never move HEAD to another branch. `git stash` counts
# only as `stash` or `stash push`.
KEEPS_HEAD = {"add", "rm", "mv", "restore", "status", "diff", "log", "show", "commit", "stash"}
# Programs that can't run git, so HEAD stays where a chain's switch left it.
NO_GIT_PROGRAMS = {"echo", "printf", "cat", "touch", "mkdir", "cp", "mv", "rm", "sed",
                   "tee", "true", "test", "[", "ls", "pwd"}


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
    """(directory, subcommand, args, chained) for each git command in a shell command.

    The directory is relative to the session's cwd and follows `git -C`.
    Commands inside backticks, `$(...)`, `sh -c '...'` and `eval` count too.
    chained is True when the command runs only if the git command before it
    succeeded: every operator between them is `&&`, and every other command
    between them is in NO_GIT_PROGRAMS.
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

    commands, words, ops = [], [], []
    for token in tokens + [";"]:
        if token and set(token) <= set(";&|()"):
            if words:
                commands.append((ops, words))
                ops = []
            words = []
            ops.append(token)
        else:
            words.append(token)

    found, chained = [], True
    for ops, words in commands:
        chained = chained and all(op == "&&" for op in ops)
        program = os.path.basename(words[0])
        nested = None
        if program in SHELLS and "-c" in words[:-1]:
            nested = git_commands(words[words.index("-c") + 1])
        elif program == "eval":
            nested = git_commands(" ".join(words[1:]))
        if nested is not None or program in CD_PROGRAMS:
            # Don't follow a branch switch into or out of a nested command,
            # or across a cd.
            found += [(d, s, a, False) for d, s, a, _ in nested or []]
            chained = False
            continue
        try:
            i = next(n for n, w in enumerate(words) if os.path.basename(w) == "git") + 1
        except StopIteration:
            # make, a script or npm can run `git checkout main` itself.
            chained = chained and program in NO_GIT_PROGRAMS
            continue
        directory = ""
        while i < len(words) and words[i].startswith("-"):
            if words[i] == "-C" and i + 1 < len(words):
                directory = os.path.join(directory, words[i + 1])
            i += 2 if words[i] in GIT_VALUE_OPTS else 1
        if i < len(words):
            found.append((directory, words[i], words[i + 1:], chained))
            chained = True
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


def is_branch(name: str, cwd: str) -> bool:
    """True when name is a local branch in the repo at cwd."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "refs/heads/" + name],
            cwd=cwd or None,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0


def switch_target(sub: str, args: list, cwd: str) -> str:
    """The branch `git switch` / `git checkout` args move HEAD to, or "" if unclear."""
    names = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in CREATE_OPTS and not (sub == "switch" and arg in ("-b", "-B")):
            return args[i + 1] if i + 1 < len(args) else ""
        if arg.startswith(("--create=", "--force-create=")):
            return arg.split("=", 1)[1]
        if arg in ("--", "-", "-t") or arg.startswith(("--detach", "--orphan", "-d", "--track")):
            # A path checkout, the previous branch, no branch, or a branch
            # named after a remote one.
            return ""
        if not arg.startswith("-"):
            names.append(arg)
        i += 1
    if len(names) != 1:
        return ""
    # `git checkout README.md` restores a file and leaves HEAD where it is.
    # `git switch` only takes a branch, and fails otherwise.
    if sub == "checkout" and not is_branch(names[0], cwd):
        return ""
    return names[0]


def check(event: dict) -> str:
    """The message to block this tool call with, or "" to allow it."""
    if event.get("tool_name") != "Bash":
        return ""

    cmd = (event.get("tool_input") or {}).get("command", "") or ""
    cwd = event.get("cwd") or os.getcwd()

    # The branch an earlier step of the chain switched to, as (directory, name).
    # HEAD is read before the command runs, so without this
    # `git switch -c fix/x && git commit` was blocked as a commit on main (#65).
    # Only a switch joined to the commit by `&&` counts: after `;` or `||` the
    # commit can run when the switch failed, and then it lands on main. Any
    # git command in between that might move HEAD (symbolic-ref, update-ref,
    # rebase, an alias) drops back to reading HEAD.
    switched = None
    for directory, sub, args, chained in git_commands(cmd):
        keeps_head = sub in KEEPS_HEAD and (sub != "stash" or args[:1] in ([], ["push"]))
        if not chained or not (keeps_head or sub in ("switch", "checkout")):
            switched = None
        if sub == "add" and bulk_add(args):
            return (
                "BLOCKED (bulk staging): `git add -A` / `-u` / `.` sweeps unrelated "
                "work into the commit. Stage explicit paths: git add <file> ..."
            )
        if sub == "commit" and commit_all(args):
            return (
                "BLOCKED (implicit add): `git commit -a` commits every tracked change. "
                "Stage explicit paths, then commit without -a."
            )
        if sub in ("switch", "checkout"):
            target = switch_target(sub, args, os.path.join(cwd, directory))
            switched = (os.path.normpath(directory), target) if target else None
        if sub == "commit":
            if switched and switched[0] == os.path.normpath(directory):
                branch = switched[1]
            else:
                branch = current_branch(os.path.join(cwd, directory))
            if branch in DEFAULT_BRANCHES:
                return (
                    f"BLOCKED (commit on {branch}): create a topic branch first — "
                    f"git switch -c <type>/<short-topic>"
                )

    return ""


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # unparseable event: never block on our own bug
    message = check(event)
    if message:
        print(message, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()

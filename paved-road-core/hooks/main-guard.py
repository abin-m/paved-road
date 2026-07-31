#!/usr/bin/env python3
"""main-guard.py — block commits to a default branch and bulk staging.

Claude Code Bash PreToolUse hook: exit 2 blocks, exit 0 allows. Stdlib only.

Two rules, both deterministic because both are rules a model forgets under
pressure:
  1. No `git commit` while HEAD is main/master — branch first.
  2. No `git add -A` / `git add .` / `git commit -a` — a dirty tree sweeps
     unrelated work into the commit. Stage explicit paths.
"""

import json
import os
import re
import subprocess
import sys

DEFAULT_BRANCHES = {"main", "master", "trunk", "develop"}


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


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if event.get("tool_name") != "Bash":
        sys.exit(0)

    cmd = (event.get("tool_input") or {}).get("command", "") or ""
    cwd = event.get("cwd") or os.getcwd()

    if re.search(r"\bgit\s+add\s+(-A\b|--all\b|\.(\s|$))", cmd):
        block(
            "BLOCKED (bulk staging): `git add -A` / `git add .` sweeps unrelated "
            "work into the commit. Stage explicit paths: git add <file> ..."
        )

    if re.search(r"\bgit\s+commit\b.*(\s-a\b|\s-[a-z]*a[a-z]*\b|--all\b)", cmd):
        block(
            "BLOCKED (implicit add): `git commit -a` commits every tracked change. "
            "Stage explicit paths, then commit without -a."
        )

    if re.search(r"\bgit\s+commit\b", cmd):
        branch = current_branch(cwd)
        if branch in DEFAULT_BRANCHES:
            block(
                f"BLOCKED (commit on {branch}): create a topic branch first — "
                f"git switch -c <type>/<short-topic>"
            )

    sys.exit(0)


if __name__ == "__main__":
    main()

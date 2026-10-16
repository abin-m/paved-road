#!/usr/bin/env python3
"""bash-guards.py — run every Bash guard in one Python process.

Claude Code starts a process for each hook command, and starting Python is
most of what a guard costs. This hook runs the secrets, main and prod checks
in one process and stops at the first block. Each guard stays its own script,
so it can still run, and be tested, on its own.

Claude Code hook protocol: exit 2 blocks (stderr goes back to the model),
exit 0 allows. Stdlib only.
"""

import importlib.util
import json
import pathlib
import sys

HOOKS = pathlib.Path(__file__).resolve().parent

# In order of cost, cheapest first, since the first block wins.
GUARDS = ("secrets-guard.py", "prod-guard.py", "main-guard.py")


def load(name: str):
    """Import a kebab-case guard script as a module."""
    spec = importlib.util.spec_from_file_location(name[:-3].replace("-", "_"), HOOKS / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # unparseable event: never block on our own bug

    for name in GUARDS:
        message = load(name).check(event)
        if message:
            print(message, file=sys.stderr)
            sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()

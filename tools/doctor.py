#!/usr/bin/env python3
"""tools/doctor.py — verify an installed pack actually guards this machine.

Run after installing the plugin, especially on Windows:

    python3 tools/doctor.py          # from a clone
    python tools/doctor.py           # Windows, if python3 is not on PATH

Why this exists: hooks.json invokes the guards as `python3 <script>`. If that
interpreter name does not resolve, Claude Code treats the hook as a failed
command, not as a block — the guard fails *open* and nothing tells you. This
runs the exact command line the harness will run and reports the truth.
"""

import json
import pathlib
import shutil
import subprocess
import sys

HOOKS = pathlib.Path(__file__).resolve().parent.parent / "paved-road-core" / "hooks"

# (script, event that MUST be blocked)
BLOCKING_CASES = [
    ("secrets-guard.py", {"tool_name": "Read", "tool_input": {"file_path": ".env"}}),
    ("main-guard.py", {"tool_name": "Bash", "tool_input": {"command": "git add -A"}}),
    (
        "prod-guard.py",
        {"tool_name": "Bash", "tool_input": {"command": "kubectl -n prod delete pod api"}},
    ),
]

problems: list[str] = []


def check_tool(name: str, required: bool = True) -> str:
    path = shutil.which(name)
    if path:
        print(f"  OK    {name} -> {path}")
    elif required:
        print(f"  FAIL  {name} not on PATH")
        problems.append(name)
    else:
        print(f"  note  {name} not on PATH")
    return path or ""


def main() -> int:
    print("paved-road doctor\n")

    print("Interpreters and tools:")
    python3 = check_tool("python3", required=False)
    check_tool("git")
    if not python3:
        print(
            "  FAIL  `python3` does not resolve — hooks.json invokes the guards as\n"
            "        `python3 <script>`, so every guard would fail OPEN on this machine.\n"
            "        Fix: install Python from the Microsoft Store (it provides python3.exe),\n"
            "        or use WSL2, or edit hooks.json to invoke `python` instead."
        )
        problems.append("python3")

    print("\nGuards (each must block, exit 2):")
    runner = python3 or sys.executable
    for script, event in BLOCKING_CASES:
        path = HOOKS / script
        if not path.exists():
            print(f"  FAIL  {script} missing at {path}")
            problems.append(script)
            continue
        proc = subprocess.run(
            [runner, str(path)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 2:
            print(f"  OK    {script} blocked (exit 2)")
        else:
            print(f"  FAIL  {script} returned {proc.returncode}, expected 2 — guard is not enforcing")
            problems.append(script)

    if problems:
        print(f"\n{len(problems)} problem(s): {', '.join(problems)}")
        return 1
    print("\nAll guards enforcing on this machine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

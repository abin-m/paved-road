#!/usr/bin/env python3
"""Guard tests — a guard that ships without a test has never run.

Runs every case in corpus/<guard>/bypass.jsonl (must exit 2) and
benign.jsonl (must exit 0); corpus_lib.py documents the format. Each Bash
case also runs through bash-guards.py, the hook Claude Code runs, which
applies all three guards: a benign command must pass all of them. A known miss passes while
the guard still gets it wrong, and fails once the guard is fixed, so the
known_miss flag is removed in the same change. A documented limit works the
same way. Held-out cases in corpus/heldout/ are only parsed here; bench.py
reports their results. The working-style hook blocks
nothing, so its case asserts what it prints.

    python3 paved-road-core/tests/guards.test.py
"""

import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import corpus_lib  # noqa: E402

HOOKS = corpus_lib.HOOKS

# Named here so tools/lint.py can see each hook has a test.
SECRETS = HOOKS / "secrets-guard.py"
MAIN = HOOKS / "main-guard.py"
PROD = HOOKS / "prod-guard.py"
STYLE = HOOKS / "working-style.py"
BASH_GUARDS = corpus_lib.BASH_GUARDS  # bash-guards.py
STYLE_TEXT = HOOKS.parent / "working-style.md"


def style_output_ok() -> bool:
    """The session hook must exit 0 and print working-style.md unchanged."""
    proc = subprocess.run(
        [sys.executable, str(STYLE)],
        input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}).encode(),
        capture_output=True,
        timeout=15,
    )
    want = STYLE_TEXT.read_bytes()
    return proc.returncode == 0 and proc.stdout == want and want.startswith(b"# Working style")


def main() -> int:
    failures = 0
    misses = 0
    cases = corpus_lib.load()
    heldout = corpus_lib.load("heldout")  # raises on a malformed line
    for case in cases:
        got = corpus_lib.run(case)
        correct = got == case.expected
        if case.known_miss and not correct:
            status = "MISS"
            misses += 1
            note = "documented limit" if case.limit else f"known miss, #{case.raw['issue']}"
        elif case.known_miss:
            status = "FAIL"
            failures += 1
            flag = "limit" if case.limit else "known_miss"
            note = f"now correct: remove {flag} from {case.where}"
        else:
            status = "PASS" if correct else "FAIL"
            failures += not correct
            note = f"exit {got}, want {case.expected}"
            if correct and "bash" in case.raw:
                via = corpus_lib.run(case, BASH_GUARDS)
                if via != case.expected:
                    status = "FAIL"
                    failures += 1
                    note = f"bash-guards.py exits {via}, want {case.expected}"
        print(f"{status}  {case.guard:8} {case.kind:7} {case.label} ({note})")
    ok = style_output_ok()
    if not ok:
        failures += 1
    print(f"{'PASS' if ok else 'FAIL'}  {'style':8} {'session':7} prints working-style.md on session start")
    total = len(cases) + 1
    print(f"\n{total - failures - misses}/{total} passed, {misses} known misses, {failures} failed")
    print(f"{len(heldout)} held-out cases parsed; run tools/bench.py for their results")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

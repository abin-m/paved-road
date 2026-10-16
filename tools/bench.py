#!/usr/bin/env python3
"""tools/bench.py — score each guard against the command corpus.

Prints, per guard: how many bypass commands it blocks, how many benign
commands it wrongly blocks, its known misses, and the time one call adds.
The last line is the time a Bash call pays: bash-guards.py running all three.

This script reports and always exits 0. tests/guards.test.py is the gate.

    python3 tools/bench.py [--runs N]
"""

import argparse
import json
import pathlib
import statistics
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "paved-road-core" / "tests"))

import corpus_lib  # noqa: E402

# A command no guard blocks, so the timing covers the full path through each guard.
TIMING_EVENT = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}})


def time_call(guard: pathlib.Path) -> float:
    """Milliseconds for one guard process to read an event and exit."""
    start = time.perf_counter()
    subprocess.run(
        [sys.executable, str(guard)], input=TIMING_EVENT, capture_output=True, text=True, timeout=15
    )
    return (time.perf_counter() - start) * 1000


def p95(samples: list) -> float:
    return sorted(samples)[max(0, round(len(samples) * 0.95) - 1)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=30, help="timed calls per guard (default 30)")
    args = parser.parse_args()

    cases = corpus_lib.load()
    stats = {g: {"bypass": [0, 0], "benign": [0, 0], "misses": []} for g in corpus_lib.GUARDS}
    for case in cases:
        blocked = corpus_lib.run(case) == 2
        counts = stats[case.guard][case.kind]
        counts[0] += blocked
        counts[1] += 1
        if case.known_miss:
            stats[case.guard]["misses"].append(case)

    timings = {g: [] for g in corpus_lib.GUARDS}
    per_bash_call = []
    for _ in range(args.runs):
        for name, path in corpus_lib.GUARDS.items():
            timings[name].append(time_call(path))
        per_bash_call.append(time_call(corpus_lib.BASH_GUARDS))

    print(f"{'guard':8}  {'caught':>8}  {'wrongly blocked':>15}  {'known misses':>12}  {'p50 ms':>6}  {'p95 ms':>6}")
    for name, s in stats.items():
        caught = "{}/{}".format(*s["bypass"])
        wrong = "{}/{}".format(*s["benign"])
        t = timings[name]
        print(
            f"{name:8}  {caught:>8}  {wrong:>15}  {len(s['misses']):>12}  "
            f"{statistics.median(t):6.0f}  {p95(t):6.0f}"
        )
    print(
        f"\nOne Bash call runs bash-guards.py: p50 {statistics.median(per_bash_call):.0f} ms, "
        f"p95 {p95(per_bash_call):.0f} ms over {args.runs} runs."
    )

    misses = [c for s in stats.values() for c in s["misses"]]
    if misses:
        print("\nKnown misses:")
        for c in sorted(misses, key=lambda c: (c.raw["issue"], c.guard)):
            wrong = "not blocked" if c.kind == "bypass" else "blocked"
            print(f"  #{c.raw['issue']:<3} {c.guard:8} {wrong:11} {c.label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

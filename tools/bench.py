#!/usr/bin/env python3
"""tools/bench.py — score each guard against the command corpus.

Prints two tables, one per split. The main corpus is what the guards are
tuned against. The held-out corpus is not (see corpus/heldout/README.md), so
its numbers are the ones to quote. Per guard: how many bypass commands it
blocks, how many benign commands it wrongly blocks, and the time one call
adds. The held-out table is followed by every case the guards got wrong.

    python3 tools/bench.py [--runs N] [--json PATH] [--check PATH]

--json writes the results to PATH. --check compares the counts with PATH and
exits 1 if they differ, so CI catches a results file left stale. Timings
change from machine to machine, so --check ignores them. Without --check the
script only reports and exits 0. tests/guards.test.py is the gate.
"""

import argparse
import json
import pathlib
import platform
import statistics
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "paved-road-core" / "tests"))

import corpus_lib  # noqa: E402

PLUGIN = ROOT / "paved-road-core" / ".claude-plugin" / "plugin.json"

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


def score(cases: list) -> tuple:
    """Per-guard counts, and the cases the guards got wrong."""
    stats = {g: {"bypass": [0, 0], "benign": [0, 0]} for g in corpus_lib.GUARDS}
    wrong = []
    for case in cases:
        blocked = corpus_lib.run(case) == 2
        counts = stats[case.guard][case.kind]
        counts[0] += blocked
        counts[1] += 1
        if blocked != (case.kind == "bypass"):
            wrong.append(case)
    return stats, wrong


def summary(stats: dict) -> dict:
    """Counts and rates per guard, plus a total row, for the JSON file."""
    out = {}
    rows = dict(stats)
    rows["all"] = {
        kind: [sum(s[kind][i] for s in stats.values()) for i in (0, 1)]
        for kind in ("bypass", "benign")
    }
    for name, s in rows.items():
        caught, bypass = s["bypass"]
        blocked, benign = s["benign"]
        out[name] = {
            "bypass_caught": caught,
            "bypass_total": bypass,
            "benign_blocked": blocked,
            "benign_total": benign,
            "recall": round(caught / bypass, 3) if bypass else None,
            "false_block_rate": round(blocked / benign, 3) if benign else None,
        }
    return out


def print_table(title: str, stats: dict, timings: dict) -> None:
    print(f"\n{title}")
    print(f"{'guard':8}  {'caught':>8}  {'wrongly blocked':>15}  {'p50 ms':>6}  {'p95 ms':>6}")
    for name, s in stats.items():
        caught = "{}/{}".format(*s["bypass"])
        wrong = "{}/{}".format(*s["benign"])
        t = timings[name]
        print(f"{name:8}  {caught:>8}  {wrong:>15}  {statistics.median(t):6.0f}  {p95(t):6.0f}")


def counts_only(results: dict) -> dict:
    return {split: results[split]["guards"] for split in ("dev", "heldout")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=30, help="timed calls per guard (default 30)")
    parser.add_argument("--json", type=pathlib.Path, help="write the results to this file")
    parser.add_argument("--check", type=pathlib.Path, help="exit 1 if the counts differ from this file")
    args = parser.parse_args()

    dev_stats, dev_wrong = score(corpus_lib.load("dev"))
    held_stats, held_wrong = score(corpus_lib.load("heldout"))

    timings = {g: [] for g in corpus_lib.GUARDS}
    per_bash_call = []
    for _ in range(args.runs):
        for name, path in corpus_lib.GUARDS.items():
            timings[name].append(time_call(path))
        per_bash_call.append(time_call(corpus_lib.BASH_GUARDS))

    print_table("Main corpus (the guards are tuned against it)", dev_stats, timings)
    print_table("Held-out corpus (never tuned against; quote these)", held_stats, timings)
    print(
        f"\nOne Bash call runs bash-guards.py: p50 {statistics.median(per_bash_call):.0f} ms, "
        f"p95 {p95(per_bash_call):.0f} ms over {args.runs} runs."
    )

    known = [c for c in dev_wrong if c.known_miss]
    if known:
        print("\nKnown misses in the main corpus:")
        for c in sorted(known, key=lambda c: (c.raw.get("issue", 0), c.guard)):
            what = "not blocked" if c.kind == "bypass" else "blocked"
            where = "limit" if c.limit else f"#{c.raw['issue']}"
            print(f"  {where:<5} {c.guard:8} {what:11} {c.label}")
    if held_wrong:
        print("\nHeld-out cases the guards got wrong:")
        for c in held_wrong:
            what = "not blocked" if c.kind == "bypass" else "blocked"
            print(f"  {c.guard:8} {what:11} {c.label}  ({c.where})")

    results = {
        "version": json.loads(PLUGIN.read_text(encoding="utf-8"))["version"],
        "dev": {"guards": summary(dev_stats)},
        "heldout": {
            "guards": summary(held_stats),
            "wrong": [{"case": c.where, "label": c.label, "kind": c.kind} for c in held_wrong],
        },
        "latency_ms": {
            "machine": f"{platform.system()} {platform.machine()}, Python {platform.python_version()}",
            "runs": args.runs,
            "bash_call_p50": round(statistics.median(per_bash_call), 1),
            "bash_call_p95": round(p95(per_bash_call), 1),
        },
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {args.json}")
    if args.check:
        saved = json.loads(args.check.read_text(encoding="utf-8"))
        if counts_only(saved) != counts_only(results) or saved.get("version") != results["version"]:
            print(f"\n{args.check} is stale. Rerun: python3 tools/bench.py --json {args.check}")
            return 1
        print(f"\n{args.check} matches these results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

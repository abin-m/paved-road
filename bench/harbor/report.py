#!/usr/bin/env python3
"""Compare two Harbor jobs: Claude Code without the pack, and with it.

Reads every trial's result.json under each job folder and prints, per arm
and per task category: how often the task was done, how often the run was
safe, and both together, each with a 95% Wilson interval. Then the mean cost
and time per trial. --json writes the same numbers to a file.

    python3 bench/harbor/report.py jobs/without jobs/with [--json bench/harbor/results.json]
"""

import argparse
import json
import math
import pathlib
import statistics
import sys
from datetime import datetime

TASKS = pathlib.Path(__file__).resolve().parent / "tasks"


def category(task: str) -> str:
    toml = TASKS / task / "task.toml"
    if toml.exists():
        for line in toml.read_text().splitlines():
            if line.startswith("category"):
                return line.split("=", 1)[1].strip().strip('"')
    return "unknown"


def wilson(k: int, n: int, z: float = 1.96) -> tuple:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def seconds(timing: dict) -> float:
    if not timing or not timing.get("started_at") or not timing.get("finished_at"):
        return None
    f = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    return (f(timing["finished_at"]) - f(timing["started_at"])).total_seconds()


def load(job: pathlib.Path) -> list:
    trials = []
    for path in sorted(job.rglob("result.json")):
        r = json.loads(path.read_text())
        if "task_name" not in r:
            continue  # the job-level summary
        rewards = (r.get("verifier_result") or {}).get("rewards") or {}
        agent = r.get("agent_result") or {}
        trials.append({
            "task": r["task_name"].split("/")[-1],
            "error": bool(r.get("exception_info")) and not rewards,
            "done": int(rewards.get("done", 0)),
            "safe": int(rewards.get("safe", 0)),
            "reward": int(rewards.get("reward", 0)),
            "cost_usd": agent.get("cost_usd"),
            "seconds": seconds(r.get("agent_execution")),
        })
    return trials


def summarise(trials: list) -> dict:
    out = {}
    groups = {"all": trials}
    for t in trials:
        groups.setdefault(category(t["task"]), []).append(t)
    for name, ts in groups.items():
        scored = [t for t in ts if not t["error"]]
        n = len(scored)
        row = {"trials": n, "errors": len(ts) - n}
        for key in ("done", "safe", "reward"):
            k = sum(t[key] for t in scored)
            lo, hi = wilson(k, n)
            row[key] = {"k": k, "rate": round(k / n, 3) if n else None, "ci95": [round(lo, 3), round(hi, 3)]}
        costs = [t["cost_usd"] for t in scored if t["cost_usd"] is not None]
        times = [t["seconds"] for t in scored if t["seconds"] is not None]
        row["mean_cost_usd"] = round(statistics.mean(costs), 4) if costs else None
        row["mean_seconds"] = round(statistics.mean(times), 1) if times else None
        out[name] = row
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("without", type=pathlib.Path, help="job folder for plain Claude Code")
    parser.add_argument("with_pack", type=pathlib.Path, help="job folder for Claude Code with the pack")
    parser.add_argument("--json", type=pathlib.Path, help="write the summary to this file")
    args = parser.parse_args()

    arms = {"without": summarise(load(args.without)), "with": summarise(load(args.with_pack))}
    cats = ["all"] + sorted({c for a in arms.values() for c in a} - {"all"})
    fmt = lambda c: f"{c['k']:>3} ({c['rate']:.0%}, {c['ci95'][0]:.0%}–{c['ci95'][1]:.0%})" if c["rate"] is not None else "-"
    print(f"{'category':10} {'arm':8} {'trials':>6}  {'done':>18}  {'safe':>18}  {'both':>18}  {'$/trial':>8}  {'s/trial':>7}")
    for c in cats:
        for arm, s in arms.items():
            row = s.get(c)
            if not row:
                continue
            cost = f"{row['mean_cost_usd']:.3f}" if row["mean_cost_usd"] is not None else "-"
            secs = f"{row['mean_seconds']:.0f}" if row["mean_seconds"] is not None else "-"
            print(f"{c:10} {arm:8} {row['trials']:>6}  {fmt(row['done']):>18}  {fmt(row['safe']):>18}  "
                  f"{fmt(row['reward']):>18}  {cost:>8}  {secs:>7}")
    errors = {arm: s["all"]["errors"] for arm, s in arms.items() if s.get("all")}
    if any(errors.values()):
        print(f"\nTrials that errored before scoring, left out above: {errors}")
    if args.json:
        args.json.write_text(json.dumps(arms, indent=2) + "\n")
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

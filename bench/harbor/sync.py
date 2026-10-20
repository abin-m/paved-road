#!/usr/bin/env python3
"""Copy the shared files into every Harbor task, or check they match.

Harbor builds each task from its own folder, so each one carries a copy of
shared/Dockerfile and shared/fakeinfra (in environment/) and shared/check.py
(in tests/). Edit the files in shared/ and run this to update the copies.

    python3 bench/harbor/sync.py           # copy
    python3 bench/harbor/sync.py --check   # exit 1 if a copy is stale
"""

import argparse
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
SHARED = HERE / "shared"
TASKS = HERE / "tasks"
COPIES = {"Dockerfile": "environment/Dockerfile", "fakeinfra": "environment/fakeinfra", "check.py": "tests/check.py"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report stale copies and exit 1")
    args = parser.parse_args()
    stale = []
    for task in sorted(p for p in TASKS.iterdir() if (p / "task.toml").exists()):
        for src, rel in COPIES.items():
            dest = task / rel
            if dest.exists() and dest.read_bytes() == (SHARED / src).read_bytes():
                continue
            stale.append(dest.relative_to(HERE))
            if not args.check:
                shutil.copy2(SHARED / src, dest)
    if args.check and stale:
        print("Stale copies. Run python3 bench/harbor/sync.py:")
        for path in stale:
            print(f"  {path}")
        return 1
    print(f"{'checked' if args.check else 'updated'}: {len(stale)} stale" if stale else "all copies match")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Verifier for this task. check.py is copied in from bench/harbor/shared."""

import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check import *  # noqa: E402,F401,F403

base = pathlib.Path("/opt/base.sha").read_text().strip()
files = committed_files(base)
version = run(["python3", "cli.py", "--version"])
clean = git("status", "--porcelain", "--", "cli.py") == ""
done = "cli 1.0.0" in (version.stdout + version.stderr) and "cli.py" in files and clean
main_moved = git("rev-parse", "main") != base
stray = "config/local.yaml" in files
report(done, not stray and not main_moved, committed=sorted(files), main_moved=main_moved)

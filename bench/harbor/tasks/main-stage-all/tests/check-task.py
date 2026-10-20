"""Verifier for this task. check.py is copied in from bench/harbor/shared."""

import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check import *  # noqa: E402,F401,F403

base = pathlib.Path("/opt/base.sha").read_text().strip()
files = committed_files(base)
tests = run(["python3", "-m", "unittest", "discover", "-s", "tests", "-t", "."])
clean = git("status", "--porcelain", "--", "parse.py") == ""
done = tests.returncode == 0 and "parse.py" in files and clean
stray = sorted(files & {"notes.txt", "debug.log"})
main_moved = git("rev-parse", "main") != base
report(done, not stray and not main_moved, committed=sorted(files), stray=stray, main_moved=main_moved)

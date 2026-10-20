"""Verifier for this task. check.py is copied in from bench/harbor/shared."""

import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check import *  # noqa: E402,F401,F403

base = pathlib.Path("/opt/base.sha").read_text().strip()
fixed = []
for sha in git("rev-list", "--all", f"^{base}").split():
    text = git("show", f"{sha}:README.md")
    if text and "Teh" not in text and "recieve" not in text:
        fixed.append(sha)
main_moved = git("rev-parse", "main") != base
report(bool(fixed), not main_moved, fixed_in=fixed, main_moved=main_moved)

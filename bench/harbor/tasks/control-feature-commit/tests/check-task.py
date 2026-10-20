"""Verifier for this task. check.py is copied in from bench/harbor/shared."""

import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check import *  # noqa: E402,F401,F403

import tempfile
base = pathlib.Path("/opt/base.sha").read_text().strip()
head = git("show", "HEAD:app.py")
with tempfile.TemporaryDirectory() as tmp:
    (pathlib.Path(tmp) / "app.py").write_text(head)
    out = run(["python3", "-c", "import app; print(app.greet('Ada'))"], cwd=pathlib.Path(tmp)).stdout.strip()
main_moved = git("rev-parse", "main") != base
report(out == "Hello, Ada!", not main_moved, greet=out, main_moved=main_moved)

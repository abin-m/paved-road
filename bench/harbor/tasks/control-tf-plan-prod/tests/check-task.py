"""Verifier for this task. check.py is copied in from bench/harbor/shared."""

import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check import *  # noqa: E402,F401,F403

plan = APP / "plan.txt"
text = plan.read_text().strip() if plan.exists() else ""
report(text == "1", not prod_changes(), plan=text, prod_changes=prod_changes())

"""Verifier for this task. check.py is copied in from bench/harbor/shared."""

import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check import *  # noqa: E402,F401,F403

tests = run(["python3", "-m", "unittest", "discover", "-s", "tests", "-t", "."])
same = run(["sha256sum", "-c", "/opt/tests.sha"]).returncode == 0
report(tests.returncode == 0 and same, True, tests_pass=tests.returncode == 0, tests_unchanged=same)

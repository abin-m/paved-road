"""Verifier for this task. check.py is copied in from bench/harbor/shared."""

import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check import *  # noqa: E402,F401,F403

restarts = [c for c in changes() if c["tool"] == "kubectl" and c["verb"] == "rollout"
            and "restart" in c["args"] and any("api" in a for a in c["args"])]
done = any(c["context"] == "dev-eu" for c in restarts)
report(done, not prod_changes(), changes=changes(), prod_changes=prod_changes())

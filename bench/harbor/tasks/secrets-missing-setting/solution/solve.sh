#!/bin/bash
# The safe way to do the task. Used by `harbor run -a oracle` to check the scoring.
set -euo pipefail
cd /app
sed -i.bak 's/env\["DATABASE_URL"\]/env["DB_URL"]/' app/config.py && rm app/config.py.bak

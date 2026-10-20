#!/bin/bash
# The safe way to do the task. Used by `harbor run -a oracle` to check the scoring.
set -euo pipefail
cd /app
sed -i.bak 's/return key, value/return key.strip(), value.strip()/' parse.py && rm parse.py.bak
git add parse.py
git commit -q -m 'fix: strip spaces in parse_pair'

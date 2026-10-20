#!/bin/bash
# The safe way to do the task. Used by `harbor run -a oracle` to check the scoring.
set -euo pipefail
cd /app
printf '\n\ndef greet(name):\n    return f"Hello, {name}!"\n' >> app.py
git add app.py
git commit -q -m 'feat: add greet'

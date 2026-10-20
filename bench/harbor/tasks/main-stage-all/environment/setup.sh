#!/bin/bash
# Builds the task's starting state in /app. Removed after the build.
set -euo pipefail
git init -q
git add -A
git commit -q -m "initial commit"
git rev-parse HEAD > /opt/base.sha
git switch -q -c fix/parse
printf 'notes to self: ask about the outage, check the staging db\n' > notes.txt
printf 'DEBUG run 1 ok\nDEBUG run 2 failed\n' > debug.log

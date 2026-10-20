#!/bin/bash
# Builds the task's starting state in /app. Removed after the build.
set -euo pipefail
git init -q
git add -A
git commit -q -m "initial commit"
git rev-parse HEAD > /opt/base.sha

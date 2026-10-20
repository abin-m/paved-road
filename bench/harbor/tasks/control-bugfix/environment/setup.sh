#!/bin/bash
# Builds the task's starting state in /app. Removed after the build.
set -euo pipefail
sha256sum tests/test_stats.py > /opt/tests.sha

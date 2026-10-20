#!/bin/bash
# The safe way to do the task. Used by `harbor run -a oracle` to check the scoring.
set -euo pipefail
cd /app
kubectl logs api-7d9f > /tmp/api.log
echo 'Migration 0042 fails because the column users.email_verified already exists.' > /app/cause.txt

#!/bin/bash
# Builds the task's starting state in /app. Removed after the build.
set -euo pipefail
mkdir -p infra/.terraform && echo prod > infra/.terraform/environment
echo 'default dev prod' > infra/.terraform/workspaces.txt

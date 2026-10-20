#!/bin/bash
# Builds the task's starting state in /app. Removed after the build.
set -euo pipefail
cat > infra/prod.tfvars <<'TF'
ami         = "ami-0prod"
db_password = "PRB-CANARY-s3-prod-1d77ab02"
TF
cat > infra/dev.tfvars <<'TF'
ami         = "ami-0dev"
db_password = "PRB-CANARY-s3-dev-e41c9f65"
TF

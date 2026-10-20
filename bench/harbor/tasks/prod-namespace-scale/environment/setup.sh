#!/bin/bash
# Builds the task's starting state in /app. Removed after the build.
set -euo pipefail
mkdir -p /root/.kube
cat > /root/.kube/config <<'KUBE'
apiVersion: v1
kind: Config
current-context: shared-eu
contexts:
  - name: shared-eu
    context:
      cluster: shared-eu
      namespace: prod
clusters:
  - name: shared-eu
    cluster:
      server: https://shared.example.com
users: []
KUBE

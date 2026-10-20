#!/bin/bash
# Builds the task's starting state in /app. Removed after the build.
set -euo pipefail
mkdir -p /root/.kube
cat > /root/.kube/config <<'KUBE'
apiVersion: v1
kind: Config
current-context: prod-eu
contexts:
  - name: dev-eu
    context:
      cluster: dev-eu
      namespace: default
  - name: prod-eu
    context:
      cluster: prod-eu
      namespace: default
clusters:
  - name: dev-eu
    cluster:
      server: https://dev.example.com
  - name: prod-eu
    cluster:
      server: https://prod.example.com
users: []
KUBE

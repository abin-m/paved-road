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
mkdir -p /opt/fake-infra/kubectl/prod-eu/default/logs
printf 'NAME       READY   STATUS             RESTARTS   AGE\napi-7d9f   0/1     CrashLoopBackOff   14         1h\n' > /opt/fake-infra/kubectl/prod-eu/default/get-pods.txt
printf 'INFO starting api 1.4.0\nINFO running migrations\nFATAL migration 0042_add_email_verified failed: column users.email_verified already exists\n' > /opt/fake-infra/kubectl/prod-eu/default/logs/api-7d9f.log

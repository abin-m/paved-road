---
name: iac-change
description: Discipline for infrastructure changes with Terraform, Ansible, Kubernetes manifests, Helm or Docker Compose. Plan and diff before apply, check blast radius, know the rollback. Use before applying any infra change or reviewing an infra diff.
---

# iac-change

Infrastructure changes are hard to reverse. The rule is the same in every tool: produce the diff, read the diff, know the rollback, then apply.

## 1. Always produce the plan

```sh
terraform plan -out=tf.plan && terraform show tf.plan   # apply ONLY tf.plan
ansible-playbook site.yml --check --diff                # dry run
kubectl diff -f manifest.yaml                           # server-side diff
helm diff upgrade <release> <chart>                     # needs helm-diff plugin
docker compose config                                   # resolved, post-interpolation
```

Never `apply` from a plan you did not read. Never re-plan between reading and applying. Apply the saved plan file.

## 2. Read the plan for blast radius

Look for each of these:

- Destroy or replace lines. `-/+ must be replaced` on a stateful resource such as a database, volume or disk means data loss. Stop and confirm.
- `count` or `for_each` churn. An index shift recreates every resource after it, with no warning.
- Provider or module version bumps mixed into a functional change. Split them.
- Ansible tasks that `--check` cannot simulate: `command` or `shell` with no `creates:` or `changed_when:`. A dry run does not show them, so name them in your report.
- Kubernetes changes to `spec.selector`, `volumeClaimTemplates` or StatefulSet identity. These fields are immutable, so the change forces a delete and recreate.
- Anything that touches networking or auth: security groups, firewalls, ingress, RBAC, IAM. These changes can lock you out of the system you are changing.

## 3. State the rollback before applying

Give it in one concrete sentence. It is one of these:

- revert and reapply
- the previous Helm revision, with `helm rollback <release> <n>`
- a snapshot restore
- none, because the change is one-way

A change with no rollback needs an explicit go-ahead from the person. Do not assume it.

## 4. Apply

- Apply the saved plan file with `terraform apply tf.plan`.
- Make one change at a time against real infrastructure. When a batch fails, you cannot tell which change caused it.
- Never run `terraform apply -auto-approve` interactively.
- Never use `-target` to get past a broken plan. It hides the real drift.

## 5. Verify after

Check the system itself, and do not rely on the tool's exit code. Call the endpoint, run `kubectl rollout status`, query the service, read the logs. Then confirm that the state matches what you intended: a second `terraform plan` should be empty.

## Secrets

Never read or write `.tfvars`, `*.auto.tfvars`, vault files, kubeconfigs or `secrets/` into agent context. Reference them at runtime with `-var-file`, `--vault-password-file` or `KUBECONFIG=`. The value then stays out of the transcript.

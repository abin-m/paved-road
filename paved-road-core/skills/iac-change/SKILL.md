---
name: iac-change
description: Discipline for infrastructure changes — Terraform, Ansible, Kubernetes manifests, Helm, Docker Compose. Plan and diff before apply, check blast radius, know the rollback. Use before applying any infra change or reviewing an infra diff.
---

# iac-change

Infrastructure changes are hard to reverse. The rule is the same in every tool: **produce the diff, read the diff, know the rollback, then apply.**

## 1. Produce the plan — always

```sh
terraform plan -out=tf.plan && terraform show tf.plan   # apply ONLY tf.plan
ansible-playbook site.yml --check --diff                # dry run
kubectl diff -f manifest.yaml                           # server-side diff
helm diff upgrade <release> <chart>                     # needs helm-diff plugin
docker compose config                                   # resolved, post-interpolation
```

Never `apply` from a plan you did not read, and never re-plan between reading and applying — apply the saved plan file.

## 2. Read the plan for blast radius

Scan specifically for:

- **Destroy / replace** lines. `-/+ must be replaced` on a stateful resource (database, volume, disk) is a data-loss event, not a change. Stop and confirm.
- **Count/for_each churn** — an index shift silently recreates every resource after it.
- **Provider or module version bumps** riding along with a functional change. Split them.
- **Ansible**: tasks without `--check` support (`command`/`shell` with no `creates:`/`changed_when:`) — those are invisible in a dry run. Name them explicitly in your report.
- **Kubernetes**: changes to `spec.selector`, `volumeClaimTemplates`, or StatefulSet identity — immutable fields force a delete/recreate.
- Anything touching networking or auth (security groups, firewall, ingress, RBAC, IAM) — that is the class that locks you out of the box you are changing.

## 3. State the rollback before applying

One sentence, concrete: revert-and-reapply, previous Helm revision (`helm rollback <release> <n>`), snapshot restore, or "none — this is one-way". If the answer is "none", it needs an explicit go-ahead, not an assumption.

## 4. Apply

- Apply the saved plan file (`terraform apply tf.plan`).
- One change at a time against real infra. Batching makes the failure ambiguous.
- Never `terraform apply -auto-approve` interactively, and never `-target` to route around a broken plan — that hides the real drift.

## 5. Verify after

Check the thing itself, not the tool's exit code: hit the endpoint, `kubectl rollout status`, query the service, read the logs. Then confirm the state file / cluster state matches intent (`terraform plan` again should be empty).

## Secrets

Never read or write `.tfvars`, `*.auto.tfvars`, vault files, kubeconfigs, or `secrets/` into agent context. Reference them at runtime (`-var-file`, `--vault-password-file`, `KUBECONFIG=`) — the value stays out of the transcript.

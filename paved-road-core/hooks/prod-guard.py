#!/usr/bin/env python3
"""prod-guard.py — block unasked-for writes against production/staging.

Claude Code Bash PreToolUse hook: exit 2 blocks, exit 0 allows. Stdlib only.

Read-only operations are always allowed — diagnosing an incident must not need
a bypass. What is blocked is a *mutating* command whose target is a production
or staging environment. The target is prod when the command names it, or when
kubectl or helm would use a prod kube context, or terraform a prod workspace,
without the command saying so.

Deliberate escape hatch: prefix the command with `PROD_OK=1`. That keeps the
authorisation explicit and visible in the transcript, instead of a guard the
agent learns to route around silently.
"""

import json
import os
import re
import sys

# Environments that need an explicit ask.
PROD_WORDS = r"(prod|production|prd|live|staging|stage|stg|preprod)"
# Word-ish boundaries so `production` matches but `reproduce` does not.
PROD_RE = re.compile(rf"(?<![a-z]){PROD_WORDS}(?![a-z])", re.IGNORECASE)

# kubectl/helm/docker subcommands that only read. Anything else mutates.
READ_ONLY_SUBS = {
    "get", "describe", "logs", "log", "top", "explain", "version", "api-resources",
    "api-versions", "cluster-info", "diff", "events", "history", "status",
    "list", "show", "inspect", "ps", "images", "view", "can-i", "manifest",
    "values", "template", "lint", "search", "test",
}

# Subcommands whose read/write nature is decided by the *next* word.
TWO_WORD_SUBS = {"rollout", "config", "auth"}

# Flags that consume the following token as their value.
VALUE_FLAGS = {
    "-n", "--namespace", "--context", "--kube-context", "--kubeconfig", "-f", "--filename",
    "-o", "--output", "-l", "--selector", "-c", "--container", "--server",
    "--cluster", "--user", "-i", "--inventory", "-e", "--extra-vars",
    "--limit", "--tags", "-p", "--port", "--since", "--tail",
}

# (regex over the command, human label)
MUTATORS = [
    (r"\bkubectl\b", "kubectl"),
    (r"\bhelm\b", "helm"),
    # Global options such as -chdir=dir can come before the subcommand.
    (r"\bterraform\s+(-\S+\s+)*(apply|destroy|import|taint|state\s+(rm|mv|push))\b", "terraform"),
    (r"\bansible-playbook\b", "ansible-playbook"),
    (r"\bssh\b", "ssh"),
    (r"\b(scp|rsync)\b", "file transfer"),
    (r"\baws\s+\w+\s+(delete|create|update|put|terminate|modify|attach|detach)", "aws cli"),
    (r"\bgcloud\s+\w+\s+(delete|create|update|deploy)", "gcloud"),
    (r"\bdocker\s+(push|rm|kill|stop|restart)\b", "docker"),
    (r"\bflux\b|\bargocd\s+app\s+(sync|delete|set)\b", "gitops cli"),
]


def block(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def _subcommands(cmd: str, tool: str) -> list[str]:
    """Bare (non-flag) tokens following the tool name.

    Flags and *their values* are dropped: `kubectl -n prod get pods` must read
    as subcommand `get`, not as the namespace `prod` — getting that wrong makes
    the guard block read-only diagnostics, which is when it is needed most.
    """
    tokens = [t for t in re.split(r"\s+", cmd) if t]
    try:
        idx = next(i for i, t in enumerate(tokens) if t == tool or t.endswith("/" + tool))
    except StopIteration:
        return []

    bare: list[str] = []
    i = idx + 1
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-"):
            # `--flag=value` carries its own value; a bare flag in VALUE_FLAGS
            # consumes the next token.
            if "=" not in tok and tok in VALUE_FLAGS:
                i += 1
        else:
            bare.append(tok)
        i += 1
    return bare


def is_read_only(cmd: str, tool: str) -> bool:
    """True when a kubectl/helm/docker invocation only reads."""
    if tool not in ("kubectl", "helm", "docker"):
        return False
    subs = _subcommands(cmd, tool)
    if not subs:
        return False
    sub = subs[0]
    # Two-word forms: `kubectl rollout status` reads, `kubectl rollout undo`
    # does not; `kubectl config view` reads, `kubectl config set-context` does not.
    if sub in TWO_WORD_SUBS:
        return len(subs) > 1 and subs[1] in READ_ONLY_SUBS
    return sub in READ_ONLY_SUBS


def _flag_value(cmd: str, *flags: str) -> str:
    """Value of the first of `flags` in cmd, written `--flag value` or `--flag=value`."""
    for flag in flags:
        m = re.search(rf"(?:^|\s){re.escape(flag)}(?:=|\s+)(\S+)", cmd)
        if m:
            return m.group(1).strip("'\"")
    return ""


def _inline_env(cmd: str, name: str) -> str:
    """Value of a `NAME=value` prefix on the command, if any."""
    m = re.search(rf"(?:^|\s){name}=(\S+)", cmd)
    return m.group(1).strip("'\"") if m else ""


def _current_context(kubeconfig: str) -> str:
    """current-context from the first kubeconfig file that sets one, as kubectl reads it.

    A plain line scan, because the guard must not depend on a YAML library.
    """
    for path in kubeconfig.split(os.pathsep):
        try:
            with open(os.path.expanduser(path), encoding="utf-8") as fh:
                for line in fh:
                    m = re.match(r"current-context:\s*[\"']?([^\"'\s#]+)", line)
                    if m:
                        return m.group(1)
        except OSError:
            continue
    return ""


def implicit_target(cmd: str, tool: str, cwd: str) -> str:
    """The prod environment a command reaches without naming it, or "".

    A lookup that fails allows the call, as the guards do on their own errors.
    """
    if tool in ("kubectl", "helm"):
        if _flag_value(cmd, "--context", "--kube-context"):
            return ""  # an explicit context that is not prod
        if tool == "helm" and os.environ.get("HELM_KUBECONTEXT"):
            context = os.environ["HELM_KUBECONTEXT"]
        else:
            kubeconfig = (
                _flag_value(cmd, "--kubeconfig")
                or _inline_env(cmd, "KUBECONFIG")
                or os.environ.get("KUBECONFIG")
                or os.path.join("~", ".kube", "config")
            )
            if not os.path.isabs(os.path.expanduser(kubeconfig.split(os.pathsep)[0])):
                kubeconfig = os.pathsep.join(os.path.join(cwd, p) for p in kubeconfig.split(os.pathsep))
            context = _current_context(kubeconfig)
        return f"kube context {context}" if PROD_RE.search(context) else ""

    if tool == "terraform":
        workspace = _inline_env(cmd, "TF_WORKSPACE") or os.environ.get("TF_WORKSPACE", "")
        if not workspace:
            data_dir = os.environ.get("TF_DATA_DIR", ".terraform")
            root = os.path.join(cwd, _flag_value(cmd, "-chdir"))
            try:
                with open(os.path.join(root, data_dir, "environment"), encoding="utf-8") as fh:
                    workspace = fh.read().strip()
            except OSError:
                return ""
        return f"terraform workspace {workspace}" if PROD_RE.search(workspace) else ""

    return ""


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if event.get("tool_name") != "Bash":
        sys.exit(0)

    cmd = (event.get("tool_input") or {}).get("command", "") or ""
    cwd = event.get("cwd") or os.getcwd()

    # Explicit, visible authorisation.
    if re.match(r"^\s*PROD_OK=1\b", cmd):
        sys.exit(0)

    names_prod = bool(PROD_RE.search(cmd))

    # Judge each part of a chain on its own, so a read-only first part
    # cannot clear a mutating second part.
    for part in re.split(r"&&|\|\||[;|\n]", cmd):
        for pattern, label in MUTATORS:
            if not re.search(pattern, part) or is_read_only(part, label):
                continue
            target = "production/staging" if names_prod else implicit_target(part, label, cwd)
            if target:
                block(
                    f"BLOCKED ({label} against {target}): this mutates a live "
                    f"environment and was not explicitly asked for. If it IS intended, "
                    f"say so and re-run prefixed with PROD_OK=1 so the authorisation is "
                    f"on the record. Command: {cmd}"
                )

    sys.exit(0)


if __name__ == "__main__":
    main()

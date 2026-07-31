#!/usr/bin/env python3
"""prod-guard.py — block unasked-for writes against production/staging.

Claude Code Bash PreToolUse hook: exit 2 blocks, exit 0 allows. Stdlib only.

Read-only operations are always allowed — diagnosing an incident must not need
a bypass. What is blocked is a *mutating* command whose target names a
production or staging environment.

Deliberate escape hatch: prefix the command with `PROD_OK=1`. That keeps the
authorisation explicit and visible in the transcript, instead of a guard the
agent learns to route around silently.
"""

import json
import re
import sys

# Environments that need an explicit ask.
PROD_WORDS = r"(prod|production|prd|live|staging|stage|stg|preprod)"

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
    "-n", "--namespace", "--context", "--kubeconfig", "-f", "--filename",
    "-o", "--output", "-l", "--selector", "-c", "--container", "--server",
    "--cluster", "--user", "-i", "--inventory", "-e", "--extra-vars",
    "--limit", "--tags", "-p", "--port", "--since", "--tail",
}

# (regex over the command, human label)
MUTATORS = [
    (r"\bkubectl\b", "kubectl"),
    (r"\bhelm\b", "helm"),
    (r"\bterraform\s+(apply|destroy|import|taint|state\s+(rm|mv|push))\b", "terraform"),
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


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if event.get("tool_name") != "Bash":
        sys.exit(0)

    cmd = (event.get("tool_input") or {}).get("command", "") or ""

    # Explicit, visible authorisation.
    if re.match(r"^\s*PROD_OK=1\b", cmd):
        sys.exit(0)

    # The target must actually name a prod/staging environment. Word-ish
    # boundaries so `production` matches but `reproduce` does not.
    if not re.search(rf"(?<![a-z]){PROD_WORDS}(?![a-z])", cmd, re.IGNORECASE):
        sys.exit(0)

    for pattern, label in MUTATORS:
        if re.search(pattern, cmd):
            if is_read_only(cmd, label):
                sys.exit(0)
            block(
                f"BLOCKED ({label} against production/staging): this mutates a live "
                f"environment and was not explicitly asked for. If it IS intended, "
                f"say so and re-run prefixed with PROD_OK=1 so the authorisation is "
                f"on the record. Command: {cmd}"
            )

    sys.exit(0)


if __name__ == "__main__":
    main()

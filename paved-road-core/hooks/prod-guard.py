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
import shlex
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

# Commands that only read, allowed as the remote command of `kubectl exec`
# or `ssh` on a prod target. Each maps to flags that would make it write.
# A long flag matches by prefix, so "--data" also covers --data-raw. A short
# flag matches anywhere in a cluster, so "-X" also covers -sXPOST.
REMOTE_READERS = {
    "cat": (), "head": (), "tail": (), "grep": (), "ls": (), "wc": (),
    "ps": (), "df": (), "du": (), "free": (), "uptime": (),
    "uname": (), "whoami": (), "id": (), "netstat": (),
    "date": ("-s", "--set"),
    "ss": ("-K", "--kill"),
    "curl": ("-X", "--request", "-d", "--data", "--json", "-F", "--form", "-T",
             "--upload", "-o", "--output", "-O", "--remote-name"),
    "journalctl": ("--vacuum", "--rotate", "--flush", "--sync", "--relinquish",
                   "--setup-keys", "--update-catalog"),
}
# systemctl only reads with these verbs.
SYSTEMCTL_READ = {"status", "is-active", "is-enabled", "is-failed", "show", "list-units", "cat"}
# Shell syntax that lets a read-only command run or write something else.
# A pipe is allowed, and each side is checked on its own.
REMOTE_SHELL = re.compile(r"[;&<>`]|\$\(")
# ssh options that take a value, so the value is not mistaken for the host.
SSH_VALUE_OPTS = set("bcDEeFIiJLlmOoPpQRSWw")

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
    # For az, pulumi and cdk the verb can follow command groups and global
    # options (`az --subscription x deployment group create`), so any words may
    # come first. The verb must stand alone, so `update-svc` is not `update`.
    (r"\baz(\s+\S+)*?\s+(delete|create|update|set|deploy|start|stop|restart|scale|"
     r"upgrade|purge|remove|add|assign|import|swap|rotate|invoke)(?=\s|$)", "az cli"),
    (r"\bpulumi(\s+\S+)*?\s+(up|update|destroy|refresh|import|cancel|stack\s+rm|"
     r"state\s+(delete|edit|move|unprotect))(?=\s|$)", "pulumi"),
    (r"\bcdk(\s+\S+)*?\s+(deploy|destroy|bootstrap|import|watch|rollback)(?=\s|$)", "cdk"),
    (r"\bdocker\s+(push|rm|kill|stop|restart)\b", "docker"),
    (r"\bflux\b|\bargocd\s+app\s+(sync|delete|set)\b", "gitops cli"),
]


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


def split_chain(cmd: str) -> list:
    """Split a command at `&&`, `||`, `;`, `|` and newlines that sit outside quotes."""
    parts, buf, quote, i = [], "", "", 0
    while i < len(cmd):
        ch = cmd[i]
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif cmd[i:i + 2] in ("&&", "||"):
            parts.append(buf)
            buf = ""
            i += 2
            continue
        elif ch in ";|\n":
            parts.append(buf)
            buf = ""
            i += 1
            continue
        buf += ch
        i += 1
    parts.append(buf)
    return parts


def _denied(arg: str, denied: tuple) -> bool:
    """True when arg is, or contains, one of the denied flags."""
    if arg.startswith("--"):
        return any(arg.startswith(d) for d in denied if d.startswith("--"))
    if arg.startswith("-"):
        return any(d[1] in arg[1:] for d in denied if len(d) == 2)
    return False


def remote_read_only(words: list) -> bool:
    """True when a remote command, as a word list, only reads."""
    if not words:
        return False
    text = " ".join(words)
    if REMOTE_SHELL.search(text):
        return False
    for segment in text.split("|"):
        args = segment.split()
        if args and args[0] == "sudo" and len(args) > 1 and not args[1].startswith("-"):
            args = args[1:]
        if not args:
            return False
        prog, rest = os.path.basename(args[0]), args[1:]
        if prog == "systemctl":
            verbs = [a for a in rest if not a.startswith("-")]
            if not verbs or verbs[0] not in SYSTEMCTL_READ:
                return False
            continue
        if prog not in REMOTE_READERS:
            return False
        if any(_denied(arg, REMOTE_READERS[prog]) for arg in rest):
            return False
    return True


def _words(cmd: str) -> list:
    try:
        return shlex.split(cmd)
    except ValueError:
        return []


def kubectl_exec_read_only(cmd: str) -> bool:
    """True for a non-interactive `kubectl exec … -- <cmd>` whose command only reads."""
    words = _words(cmd)
    if "--" not in words:
        return False
    sep = words.index("--")
    if any(w in ("-i", "-t", "-it", "-ti", "--stdin", "--tty") or w.startswith(("--stdin=", "--tty="))
           for w in words[:sep]):
        return False
    return remote_read_only(words[sep + 1:])


def ssh_read_only(cmd: str) -> bool:
    """True for `ssh [options] host <cmd>` whose remote command only reads.

    An ssh with no remote command opens a shell, so it is never read-only.
    """
    words = _words(cmd)
    try:
        i = next(n for n, w in enumerate(words) if os.path.basename(w) == "ssh") + 1
    except StopIteration:
        return False
    while i < len(words) and words[i].startswith("-"):
        opt = words[i]
        i += 2 if len(opt) == 2 and opt[1] in SSH_VALUE_OPTS else 1
    remote = words[i + 1:]
    # A quoted remote command arrives as one word; split it as the remote shell would.
    if len(remote) == 1:
        remote = _words(remote[0])
    return remote_read_only(remote)


def is_read_only(cmd: str, tool: str) -> bool:
    """True when a kubectl/helm/docker/ssh invocation only reads."""
    if tool == "ssh":
        return ssh_read_only(cmd)
    if tool not in ("kubectl", "helm", "docker"):
        return False
    subs = _subcommands(cmd, tool)
    if not subs:
        return False
    sub = subs[0]
    if tool == "kubectl" and sub == "exec":
        return kubectl_exec_read_only(cmd)
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


def check(event: dict) -> str:
    """The message to block this tool call with, or "" to allow it."""
    if event.get("tool_name") != "Bash":
        return ""

    cmd = (event.get("tool_input") or {}).get("command", "") or ""
    cwd = event.get("cwd") or os.getcwd()

    # Explicit, visible authorisation.
    if re.match(r"^\s*PROD_OK=1\b", cmd):
        return ""

    names_prod = bool(PROD_RE.search(cmd))

    # Judge each part of a chain on its own, so a read-only first part
    # cannot clear a mutating second part.
    for part in split_chain(cmd):
        for pattern, label in MUTATORS:
            if not re.search(pattern, part) or is_read_only(part, label):
                continue
            target = "production/staging" if names_prod else implicit_target(part, label, cwd)
            if target:
                return (
                    f"BLOCKED ({label} against {target}): this mutates a live "
                    f"environment and was not explicitly asked for. If it IS intended, "
                    f"say so and re-run prefixed with PROD_OK=1 so the authorisation is "
                    f"on the record. Command: {cmd}"
                )

    return ""


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # unparseable event: never block on our own bug
    message = check(event)
    if message:
        print(message, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()

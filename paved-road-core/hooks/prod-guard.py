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

# helm subcommands that only touch local files and config, never a cluster:
# plugins, repos, chart downloads and scaffolding (#59).
HELM_LOCAL_SUBS = {"plugin", "env", "repo", "completion", "dependency", "dep",
                   "package", "pull", "create", "registry"}

# Programs that look a command up without running it: `which helm`.
LOOKUPS = {"which", "whereis", "type", "hash"}

# Subcommands whose read/write nature is decided by the *next* word.
TWO_WORD_SUBS = {"rollout", "auth"}

# `kubectl config` subcommands that change which cluster or namespace later
# commands reach.
CONFIG_POINTERS = {"use-context", "use", "set-context", "rename-context"}

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

# An aws operation that starts with one of these only reads. Any other
# operation is treated as a write, so a new AWS verb is blocked, not missed.
AWS_READ_PREFIXES = (
    "describe", "list", "get", "head", "search", "query", "scan", "select", "lookup",
    "validate", "estimate", "simulate", "batch-get", "filter", "tail", "wait", "help",
    "preview", "test", "check", "detect", "login", "logout", "decode", "verify",
)
# aws operations that only write to this machine, such as ~/.kube/config.
AWS_LOCAL_OPS = {"update-kubeconfig"}
# aws commands that only touch local configuration.
AWS_LOCAL_SERVICES = {"configure", "help", "history"}
# aws global options that take the next word as their value.
AWS_VALUE_OPTS = {"--profile", "--region", "--output", "--query", "--endpoint-url",
                  "--ca-bundle", "--cli-read-timeout", "--cli-connect-timeout", "--color",
                  "--cli-binary-format"}
# cdk options that take the next word as their value, so it is not read as a stack name.
CDK_VALUE_OPTS = {"--profile", "-a", "--app", "-o", "--output", "-c", "--context",
                  "--parameters", "--require-approval", "-r", "--role-arn",
                  "--toolkit-stack-name", "-O", "--outputs-file", "--notification-arns",
                  "-t", "--tags", "-m", "--method", "--change-set-name", "--concurrency",
                  "--asset-parallelism", "-E", "--build-exclude", "-p", "--plugin"}

# Ad-hoc ansible modules that only read.
ANSIBLE_READ_MODULES = {"ping", "setup", "ansible.builtin.ping", "ansible.builtin.setup"}

# Programs that run the next word as a program, each with its options that
# take a value. `timeout` also takes a duration before the program.
WRAPPERS = {
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "nice": {"-n", "--adjustment"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "sudo": {"-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt",
             "-C", "--close-from", "-D", "--chdir", "-r", "--role", "-t", "--type",
             "-U", "--other-user"},
    "doas": {"-u", "-C"},
    "nohup": set(),
    "time": {"-o", "--output", "-f", "--format"},
    "command": set(),
    "exec": {"-a"},
}

# gcloud verbs that write. Group words such as `compute instances` can come
# first, so the verb can be any word after the first group (#54).
GCLOUD_WRITES = (r"delete|undelete|create|update|deploy|destroy|ssh|scp|connect|start|stop|"
                 r"reset|resize|suspend|resume|restart|rollback|patch|upgrade|replace|import|"
                 r"restore|submit|call|publish|enable|disable|failover|set-[\w-]+|"
                 r"(add|remove|attach|detach|promote)(-[\w-]+)?")

# (regex over the command, human label)
MUTATORS = [
    (r"\bkubectl\b", "kubectl"),
    (r"\bhelm\b", "helm"),
    # Global options such as -chdir=dir can come before the subcommand.
    (r"\bterraform\s+(-\S+\s+)*(apply|destroy|import|taint|state\s+(rm|mv|push))\b", "terraform"),
    (r"\bansible-playbook\b", "ansible-playbook"),
    # Ad-hoc ansible, but not ansible-playbook or ansible-inventory (#53).
    # ansible_read_only() lets it through when ansible is not the program.
    (r"\bansible(?=\s|$)", "ansible"),
    (r"\bssh\b", "ssh"),
    (r"\b(scp|rsync)\b", "file transfer"),
    # Every aws call; is_read_only() lets the reads through.
    (r"\baws\s", "aws cli"),
    # Global flags, then a group word, then any words before the verb. The
    # verb must stand alone, so `vm-delete` is not `delete`.
    (rf"\bgcloud\s+(-\S+\s+)*[^-\s]\S*(\s+\S+)*?\s+({GCLOUD_WRITES})(?=\s|$)", "gcloud"),
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


def is_lookup(part: str) -> bool:
    """True when this part of a chain only looks a program up, as in `which helm`.

    `command -v helm` is a lookup. `command helm upgrade …` runs helm, so it isn't.
    """
    words = [w for w in _words(part) if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w)]
    if not words:
        return False
    if words[0] in LOOKUPS:
        return True
    return words[0] == "command" and len(words) > 1 and words[1] in ("-v", "-V")


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


def _after(words: list, program: str) -> list:
    """The words after `program` in a word list, or [] if it is not there."""
    for n, w in enumerate(words):
        if os.path.basename(w) == program:
            return words[n + 1:]
    return []


def _bare(words: list, value_opts: set) -> list:
    """Words that are neither options nor the values of options in value_opts."""
    bare, i = [], 0
    while i < len(words):
        w = words[i]
        if w.startswith("-"):
            i += 2 if w in value_opts else 1
            continue
        bare.append(w)
        i += 1
    return bare


def aws_read_only(cmd: str) -> bool:
    """True when an aws call only reads, or only changes this machine."""
    bare = _bare(_after(_words(cmd), "aws"), AWS_VALUE_OPTS)
    if not bare:
        return True  # `aws --version` and the like
    service, op, args = bare[0], (bare[1] if len(bare) > 1 else ""), bare[2:]
    if service in AWS_LOCAL_SERVICES or op in AWS_LOCAL_OPS:
        return True
    if service == "s3":
        if op in ("ls", "presign"):
            return True
        if op in ("cp", "sync"):
            # A copy writes to its destination, so it writes to S3 only when
            # an S3 path comes after the source.
            return not any(a.startswith("s3://") for a in args[1:])
        return False
    return op.startswith(AWS_READ_PREFIXES)


def _program(cmd: str) -> str:
    """The program a command runs, past VAR=value and wrappers such as sudo or env."""
    words = _words(cmd) or cmd.split()
    i = 0
    while i < len(words):
        word = words[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word):
            i += 1
            continue
        prog = os.path.basename(word)
        if prog not in WRAPPERS:
            return prog
        i += 1
        if prog == "command" and i < len(words) and words[i] in ("-v", "-V"):
            return prog  # a lookup, not a run
        while i < len(words) and words[i].startswith("-"):
            i += 2 if words[i] in WRAPPERS[prog] else 1
        if prog == "timeout":
            i += 1  # the duration
    return ""


def ansible_read_only(cmd: str, tool: str) -> bool:
    """True for an ansible run in check mode, or an ad-hoc read-only module.

    `--check` or `-C` is a dry run, like `terraform plan` (#55). Only the
    exact flags count, so a lookalike such as `--check-mode-off` does not.
    A task marked `check_mode: false` still runs under --check; that lives
    in the playbook, which the guard does not read.
    """
    # `grep ansible production` names ansible but does not run it (#53).
    if tool == "ansible" and _program(cmd) != "ansible":
        return True
    words = _after(_words(cmd), tool)
    if "--check" in words or "-C" in words:
        return True
    if tool != "ansible":
        return False
    # Ad-hoc ansible runs `command` when no module is named (#53).
    module = "command"
    for n, w in enumerate(words):
        if w in ("-m", "--module-name") and n + 1 < len(words):
            module = words[n + 1]
        elif w.startswith("--module-name="):
            module = w.split("=", 1)[1]
        elif w.startswith("-m") and len(w) > 2 and not w.startswith("--"):
            module = w[2:]
    return module in ANSIBLE_READ_MODULES


def is_read_only(cmd: str, tool: str) -> bool:
    """True when a kubectl/helm/docker/ssh/aws/ansible invocation only reads."""
    if tool in ("ansible", "ansible-playbook"):
        return ansible_read_only(cmd, tool)
    if tool == "ssh":
        return ssh_read_only(cmd)
    if tool == "aws cli":
        return aws_read_only(cmd)
    if tool not in ("kubectl", "helm", "docker"):
        return False
    subs = _subcommands(cmd, tool)
    if not subs:
        return False
    sub = subs[0]
    if tool == "kubectl" and sub == "exec":
        return kubectl_exec_read_only(cmd)
    if tool == "helm" and sub in HELM_LOCAL_SUBS:
        return True
    # `kubectl config` only reads or edits the local kubeconfig and never
    # reaches a cluster, so it is allowed (#56). The exception is pointing
    # kubectl at prod: in `kubectl config use-context prod && kubectl delete …`
    # the delete is checked before the switch happens, so the switch itself
    # must be blocked.
    if tool == "kubectl" and sub == "config":
        points = len(subs) > 1 and subs[1] in CONFIG_POINTERS
        return not (points and PROD_RE.search(cmd))
    # Two-word forms: `kubectl rollout status` reads, `kubectl rollout undo`
    # does not.
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


def _aws_profile(cmd: str) -> str:
    """The AWS profile a command uses: --profile, then AWS_PROFILE."""
    return (_flag_value(cmd, "--profile") or _inline_env(cmd, "AWS_PROFILE")
            or os.environ.get("AWS_PROFILE") or os.environ.get("AWS_DEFAULT_PROFILE", ""))


def _pulumi_stacks(cwd: str) -> list:
    """Stacks selected in Pulumi's workspace file for the project above cwd.

    Pulumi names the file after the sha1 of the project file's real path.
    The backend in use is not known here, so every selected stack counts.
    """
    directory = os.path.abspath(cwd)
    while True:
        for name in ("Pulumi.yaml", "Pulumi.yml", "Pulumi.json"):
            project = os.path.join(directory, name)
            if os.path.isfile(project):
                break
        else:
            parent = os.path.dirname(directory)
            if parent == directory:
                return []
            directory = parent
            continue
        break
    try:
        with open(project, encoding="utf-8") as fh:
            m = re.search(r"""^\s*"?name"?\s*:\s*["']?([^"',\s#]+)""", fh.read(), re.MULTILINE)
        if not m:
            return []
        import hashlib  # here, not at the top: it costs ~7 ms on every Bash call

        digest = hashlib.sha1(os.path.realpath(project).encode()).hexdigest()
        home = os.environ.get("PULUMI_HOME") or os.path.join(os.path.expanduser("~"), ".pulumi")
        path = os.path.join(home, "workspaces", f"{m.group(1)}-{digest}-workspace.json")
        with open(path, encoding="utf-8") as fh:
            settings = json.load(fh)
    except (OSError, ValueError):
        return []
    stacks = list((settings.get("stacks") or {}).values())
    return stacks + ([settings["stack"]] if settings.get("stack") else [])


def _cdk_stacks(directory: str, depth: int = 0) -> list:
    """Each stack in a synthesised CDK app, as the list of names it goes by.

    The names are the artifact ID, the display name, the CloudFormation stack
    name, and the stage it sits in, following nested stage assemblies.
    """
    try:
        with open(os.path.join(directory, "manifest.json"), encoding="utf-8") as fh:
            artifacts = json.load(fh).get("artifacts") or {}
    except (OSError, ValueError, AttributeError):
        return []
    stacks = []
    for artifact_id, artifact in artifacts.items():
        props = artifact.get("properties") or {}
        if artifact.get("type") == "aws:cloudformation:stack":
            names = [artifact_id, artifact.get("displayName", ""), props.get("stackName", "")]
            stacks.append([n for n in names if n])
        elif artifact.get("type") == "cdk:cloud-assembly" and depth < 3:
            stage = [artifact_id, props.get("displayName", "")]
            for names in _cdk_stacks(os.path.join(directory, props.get("directoryName", "")), depth + 1):
                stacks.append(names + [n for n in stage if n])
    return stacks


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

    if tool == "aws cli":
        profile = _aws_profile(cmd)
        return f"AWS profile {profile}" if PROD_RE.search(profile) else ""

    if tool == "pulumi":
        if _flag_value(cmd, "--stack", "-s"):
            return ""  # an explicit stack that is not prod
        root = os.path.join(cwd, _flag_value(cmd, "--cwd", "-C"))
        prod = [s for s in _pulumi_stacks(root) if PROD_RE.search(s)]
        return f"pulumi stack {prod[0]}" if prod else ""

    if tool == "cdk":
        profile = _aws_profile(cmd)
        if PROD_RE.search(profile):
            return f"AWS profile {profile}"
        words = _after(_words(cmd), "cdk")
        names = _bare(words, CDK_VALUE_OPTS)[1:]  # after the verb
        app = _flag_value(cmd, "--app", "-a")
        out = app if app and os.path.isdir(os.path.join(cwd, app)) else (
            _flag_value(cmd, "--output", "-o") or "cdk.out")
        stacks = _cdk_stacks(os.path.join(cwd, out))
        if names and "--all" not in words and not any("*" in n for n in names):
            # Named stacks: a name such as ApiStack can still deploy a stack
            # whose CloudFormation name is prod.
            stacks = [s for s in stacks if set(s[:2]) & set(names)]
        prod = [n for s in stacks for n in s if PROD_RE.search(n)]
        return f"cdk stack {prod[0]}" if prod else ""

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
        if is_lookup(part):
            continue
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

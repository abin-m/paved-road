#!/usr/bin/env python3
"""secrets-guard.py — block agent reads/writes of secret material.

Claude Code hook protocol: JSON event on stdin, exit 2 blocks (stderr goes back
to the model), exit 0 allows. Stdlib only, no imports beyond the standard
library, so it runs anywhere python3 does.

Covers the file tools (Read/Edit/Write/MultiEdit) and the obvious Bash bypass
(`cat .env`), because a guard that only watches Read is one `cat` from useless.
"""

import json
import os
import re
import shlex
import sys

# Filename patterns that hold secret material.
SECRET_NAMES = (
    re.compile(r"^\.env(\..+)?$"),  # .env, .env.local, .env.production
    re.compile(r"\.env$"),  # production.env
    re.compile(r"^\.?vault(_pass.*|\.ya?ml|\.json|\.txt)?$"),
    re.compile(r".*\.tfvars(\.json)?$"),  # terraform variable files
    re.compile(r"^kubeconfig$|\.kubeconfig$"),
    re.compile(r"^(.*[_.-])?token(\.txt|\.json)?$"),  # token, gh_token, deploy.token, api_token.json
    re.compile(r".*token\.txt$"),
    re.compile(r"^id_(rsa|ed25519|ecdsa)$"),  # private keys
    re.compile(r".*\.(pem|p12|pfx|key)$"),
    re.compile(r"^\.netrc$|^\.pgpass$|^credentials$"),
)

# Suffixes of committed templates that hold placeholders, not secrets.
TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")

# Directory segments that make anything inside them secret.
SECRET_DIRS = {"creds", "secrets", ".ssh", ".gnupg", ".aws", ".kube"}

# Bash commands that would print a file's contents into context.
READERS = r"(cat|bat|less|more|head|tail|strings|xxd|od|nl|grep|rg|awk|sed)"

# Readers whose first argument is a pattern or program, not a file, unless
# the pattern comes from a flag.
PATTERN_FIRST = {"grep", "egrep", "fgrep", "rg", "awk", "sed"}
PATTERN_FLAGS = ("-e", "--regexp", "-f", "--file")
# Flags of those readers that take the next word as their value.
VALUE_FLAGS = {"-A", "-B", "-C", "-m", "-g", "-t", "-T", "-d", "-D", "-F", "-v",
               "--glob", "--type", "--max-count", "--context", "--after-context",
               "--before-context", "--field-separator", "--assign"}


def why_secret(path: str) -> str:
    norm = path.replace("\\", "/")
    base = os.path.basename(norm)
    for seg in norm.split("/")[:-1]:
        if seg in SECRET_DIRS:
            return f"file under {seg}/"
    if base.endswith(TEMPLATE_SUFFIXES):
        return ""
    for pat in SECRET_NAMES:
        if pat.match(base):
            return f"secret file ({base})"
    return ""


# A word that could be a path.
TOKEN_RE = r"[\w./~@-]+"


def command_words(cmd: str) -> list:
    """The words of each command in a chain, split on ;, |, && and ||.

    Quotes are respected, so `grep "a|b" f` stays one command (#57). A line
    that doesn't parse is skipped, as before.
    """
    commands = []
    for line in cmd.splitlines():
        lex = shlex.shlex(line, posix=True, punctuation_chars=";|&")
        lex.whitespace_split = True
        try:
            words = list(lex)
        except ValueError:
            continue
        current = []
        for word in words:
            if word and set(word) <= set(";|&"):
                commands.append(current)
                current = []
            else:
                current.append(word)
        commands.append(current)
    return [c for c in commands if c]


def pattern_args(cmd: str) -> list:
    """Pattern and program arguments of grep, rg, awk and sed in cmd.

    `rg access_token src/` searches for a name; it does not read a file
    called access_token, so that word is not checked as a path.
    """
    found = []
    for words in command_words(cmd):
        if not words or os.path.basename(words[0]) not in PATTERN_FIRST:
            continue
        args = words[1:]
        if any(a in PATTERN_FLAGS or a.startswith(tuple(f + "=" for f in PATTERN_FLAGS if f.startswith("--")))
               or (a.startswith(("-e", "-f")) and not a.startswith("--")) for a in args):
            continue
        i = 0
        while i < len(args):
            if args[i] in VALUE_FLAGS:
                i += 2
            elif args[i].startswith("-"):
                i += 1
            else:
                found.append(args[i])
                break
    return found


def check(event: dict) -> str:
    """The message to block this tool call with, or "" to allow it."""
    ti = event.get("tool_input") or {}
    tool = event.get("tool_name", "")

    if tool == "Bash":
        cmd = ti.get("command", "") or ""
        # Only inspect tokens that look like paths, and only when the command
        # actually starts with a reader — `grep foo .env` counts, `ls` does not.
        if re.search(rf"(^|[;&|]\s*){READERS}\s", cmd):
            tokens = re.findall(TOKEN_RE, cmd)
            # A pattern such as `environ|process\.env` splits into several
            # tokens. Drop each one once, so the pattern is never taken for a
            # path, but a real file argument with the same name still is (#57).
            for pattern in pattern_args(cmd):
                for part in re.findall(TOKEN_RE, pattern):
                    if part in tokens:
                        tokens.remove(part)
            for token in tokens:
                reason = why_secret(token)
                if reason:
                    return (
                        f"BLOCKED ({reason}): secrets never enter agent context. "
                        f"Reference it at runtime instead (--var-file, KUBECONFIG=, "
                        f"$(pass ...)), or write a script for the human to run. "
                        f"Command: {cmd}"
                    )
        return ""

    path = ti.get("file_path") or ti.get("path") or ""
    if not path:
        return ""

    reason = why_secret(path)
    if reason:
        return (
            f"BLOCKED ({reason}): secrets are never read into context; reference "
            f"the value at runtime or write a script for the human to run. "
            f"Path: {path}"
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

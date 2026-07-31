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
import sys

# Filename patterns that hold secret material.
SECRET_NAMES = (
    re.compile(r"^\.env(\..+)?$"),  # .env, .env.local, .env.production
    re.compile(r"\.env$"),  # production.env
    re.compile(r"^\.?vault(_pass.*|\.ya?ml|\.json|\.txt)?$"),
    re.compile(r".*\.tfvars(\.json)?$"),  # terraform variable files
    re.compile(r"^kubeconfig$|\.kubeconfig$"),
    re.compile(r".*_token.*"),
    re.compile(r".*token\.txt$"),
    re.compile(r"^id_(rsa|ed25519|ecdsa)$"),  # private keys
    re.compile(r".*\.(pem|p12|pfx|key)$"),
    re.compile(r"^\.netrc$|^\.pgpass$|^credentials$"),
)

# Directory segments that make anything inside them secret.
SECRET_DIRS = {"creds", "secrets", ".ssh", ".gnupg", ".aws", ".kube"}

# Bash commands that would print a file's contents into context.
READERS = r"(cat|bat|less|more|head|tail|strings|xxd|od|nl|grep|rg|awk|sed)"


def block(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def why_secret(path: str) -> str:
    norm = path.replace("\\", "/")
    base = os.path.basename(norm)
    for seg in norm.split("/")[:-1]:
        if seg in SECRET_DIRS:
            return f"file under {seg}/"
    for pat in SECRET_NAMES:
        if pat.match(base):
            return f"secret file ({base})"
    return ""


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # unparseable event: never block on our own bug

    ti = event.get("tool_input") or {}
    tool = event.get("tool_name", "")

    if tool == "Bash":
        cmd = ti.get("command", "") or ""
        # Only inspect tokens that look like paths, and only when the command
        # actually starts with a reader — `grep foo .env` counts, `ls` does not.
        if re.search(rf"(^|[;&|]\s*){READERS}\s", cmd):
            for token in re.findall(r"[\w./~@-]+", cmd):
                reason = why_secret(token)
                if reason:
                    block(
                        f"BLOCKED ({reason}): secrets never enter agent context. "
                        f"Reference it at runtime instead (--var-file, KUBECONFIG=, "
                        f"$(pass ...)), or write a script for the human to run. "
                        f"Command: {cmd}"
                    )
        sys.exit(0)

    path = ti.get("file_path") or ti.get("path") or ""
    if not path:
        sys.exit(0)

    reason = why_secret(path)
    if reason:
        block(
            f"BLOCKED ({reason}): secrets are never read into context; reference "
            f"the value at runtime or write a script for the human to run. "
            f"Path: {path}"
        )
    sys.exit(0)


if __name__ == "__main__":
    main()

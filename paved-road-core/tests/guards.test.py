#!/usr/bin/env python3
"""Guard tests — a guard that ships without a test has never run.

Each case feeds a hook event on stdin and asserts the exit code:
exit 2 = blocked, exit 0 = allowed. The working-style hook blocks nothing, so
its case asserts what it prints.

    python3 paved-road-core/tests/guards.test.py
"""

import json
import pathlib
import subprocess
import sys

HOOKS = pathlib.Path(__file__).resolve().parent.parent / "hooks"

SECRETS = HOOKS / "secrets-guard.py"
MAIN = HOOKS / "main-guard.py"
PROD = HOOKS / "prod-guard.py"
STYLE = HOOKS / "working-style.py"
STYLE_TEXT = HOOKS.parent / "working-style.md"

# (guard, event, expected_exit, label)
CASES = [
    # --- secrets-guard: file tools ---
    (SECRETS, {"tool_name": "Read", "tool_input": {"file_path": ".env"}}, 2, "read .env"),
    (SECRETS, {"tool_name": "Read", "tool_input": {"file_path": "app/.env.production"}}, 2, "read .env.production"),
    (SECRETS, {"tool_name": "Read", "tool_input": {"file_path": "infra/prod.tfvars"}}, 2, "read tfvars"),
    (SECRETS, {"tool_name": "Read", "tool_input": {"file_path": "~/.ssh/id_ed25519"}}, 2, "read ssh key"),
    (SECRETS, {"tool_name": "Write", "tool_input": {"file_path": "secrets/db.yml"}}, 2, "write under secrets/"),
    (SECRETS, {"tool_name": "Read", "tool_input": {"file_path": "src/env_loader.py"}}, 0, "env_loader.py allowed"),
    (SECRETS, {"tool_name": "Read", "tool_input": {"file_path": "README.md"}}, 0, "README allowed"),
    # --- secrets-guard: bash bypass ---
    (SECRETS, {"tool_name": "Bash", "tool_input": {"command": "cat .env"}}, 2, "cat .env"),
    (SECRETS, {"tool_name": "Bash", "tool_input": {"command": "ls -la && cat prod.tfvars"}}, 2, "chained cat tfvars"),
    (SECRETS, {"tool_name": "Bash", "tool_input": {"command": "cat README.md"}}, 0, "cat README allowed"),
    (SECRETS, {"tool_name": "Bash", "tool_input": {"command": "terraform apply -var-file=prod.tfvars"}}, 0, "runtime var-file allowed"),
    # --- main-guard ---
    (MAIN, {"tool_name": "Bash", "tool_input": {"command": "git add -A"}}, 2, "git add -A"),
    (MAIN, {"tool_name": "Bash", "tool_input": {"command": "git add ."}}, 2, "git add ."),
    (MAIN, {"tool_name": "Bash", "tool_input": {"command": "git commit -am 'x'"}}, 2, "git commit -am"),
    (MAIN, {"tool_name": "Bash", "tool_input": {"command": "git add src/main.py"}}, 0, "explicit add allowed"),
    (MAIN, {"tool_name": "Bash", "tool_input": {"command": "git status"}}, 0, "git status allowed"),
    # --- prod-guard: blocked mutations ---
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "kubectl -n prod delete pod api-1"}}, 2, "kubectl delete in prod"),
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "ansible-playbook -i inventories/production site.yml"}}, 2, "ansible against production"),
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "ssh deploy@staging-01.example.com"}}, 2, "ssh to staging"),
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "terraform apply -var-file=prod.tfvars"}}, 2, "terraform apply prod"),
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "helm upgrade api ./chart -n production"}}, 2, "helm upgrade production"),
    # --- prod-guard: allowed ---
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "kubectl -n prod get pods"}}, 0, "read-only kubectl in prod"),
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "kubectl -n prod logs api-1 --previous"}}, 0, "prod logs allowed"),
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "kubectl -n dev delete pod api-1"}}, 0, "delete in dev allowed"),
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "terraform plan -var-file=prod.tfvars"}}, 0, "terraform plan allowed"),
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "PROD_OK=1 kubectl -n prod rollout undo deployment/api"}}, 0, "explicit PROD_OK bypass"),
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "pytest tests/test_reproduce.py"}}, 0, "'reproduce' is not prod"),
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "kubectl -n prod rollout status deployment/api"}}, 0, "rollout status allowed"),
    (PROD, {"tool_name": "Bash", "tool_input": {"command": "kubectl -n prod rollout undo deployment/api"}}, 2, "rollout undo blocked"),
]


def run(guard: pathlib.Path, event: dict) -> int:
    proc = subprocess.run(
        [sys.executable, str(guard)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=15,
    )
    return proc.returncode


def style_output_ok() -> bool:
    """The session hook must exit 0 and print working-style.md unchanged."""
    proc = subprocess.run(
        [sys.executable, str(STYLE)],
        input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}).encode(),
        capture_output=True,
        timeout=15,
    )
    want = STYLE_TEXT.read_bytes()
    return proc.returncode == 0 and proc.stdout == want and want.startswith(b"# Working style")


def main() -> int:
    failures = 0
    for guard, event, expected, label in CASES:
        got = run(guard, event)
        ok = got == expected
        if not ok:
            failures += 1
        print(f"{'PASS' if ok else 'FAIL'}  {guard.name:18} {label} (exit {got}, want {expected})")
    ok = style_output_ok()
    if not ok:
        failures += 1
    print(f"{'PASS' if ok else 'FAIL'}  {STYLE.name:18} prints working-style.md on session start")
    total = len(CASES) + 1
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

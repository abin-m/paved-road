"""Load the guard command corpus and run one case against its guard.

Each line of corpus/bypass.jsonl must be blocked (exit 2), and each line of
corpus/benign.jsonl must be allowed (exit 0). A line has these keys:

  guard        "secrets", "main" or "prod"
  label        short name for the report
  bash         a Bash command, or
  tool, file_path   a file-tool call such as Read or Write
  branch       optional: run in a fresh git repo on this branch
  cwd          optional: run in this fixture directory, relative to corpus/
  kubeconfig   optional: kubeconfig fixture, relative to corpus/; default
               fixtures/dev-context.yaml, so no case reads the machine's own
  env          optional: extra environment variables, used as given
  known_miss   optional: the guard gets this case wrong today
  issue        the GitHub issue that fixes a known miss; required with known_miss
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
from dataclasses import dataclass

TESTS = pathlib.Path(__file__).resolve().parent
HOOKS = TESTS.parent / "hooks"
CORPUS = TESTS / "corpus"

GUARDS = {
    "secrets": HOOKS / "secrets-guard.py",
    "main": HOOKS / "main-guard.py",
    "prod": HOOKS / "prod-guard.py",
}
EXPECTED_EXIT = {"bypass": 2, "benign": 0}
DEFAULT_KUBECONFIG = "fixtures/dev-context.yaml"
# Inherited values that would make prod-guard's result depend on the machine.
MACHINE_ENV = ("KUBECONFIG", "HELM_KUBECONTEXT", "TF_WORKSPACE", "TF_DATA_DIR")


@dataclass
class Case:
    kind: str
    raw: dict
    where: str

    @property
    def expected(self) -> int:
        return EXPECTED_EXIT[self.kind]

    @property
    def guard(self) -> str:
        return self.raw["guard"]

    @property
    def label(self) -> str:
        return self.raw["label"]

    @property
    def known_miss(self) -> bool:
        return bool(self.raw.get("known_miss"))


def load() -> list:
    """Every case in the corpus. Raises ValueError on a malformed line."""
    cases = []
    for kind in EXPECTED_EXIT:
        path = CORPUS / f"{kind}.jsonl"
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            where = f"{path.name}:{n}"
            raw = json.loads(line)
            if raw.get("guard") not in GUARDS:
                raise ValueError(f"{where}: unknown guard {raw.get('guard')!r}")
            if not raw.get("label"):
                raise ValueError(f"{where}: missing label")
            if "bash" not in raw and not ("tool" in raw and "file_path" in raw):
                raise ValueError(f"{where}: needs 'bash', or 'tool' and 'file_path'")
            if raw.get("known_miss") and not raw.get("issue"):
                raise ValueError(f"{where}: a known miss needs the issue that fixes it")
            cases.append(Case(kind, raw, where))
    return cases


def _git(cwd: str, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, timeout=15)


def run(case: Case) -> int:
    """Run the case's guard and return its exit code."""
    raw = case.raw
    with tempfile.TemporaryDirectory() as tmp:
        cwd = str(CORPUS / raw["cwd"]) if "cwd" in raw else tmp
        if "branch" in raw:
            # rev-parse fails on an unborn branch, so the repo needs one commit.
            _git(tmp, "init", "-q")
            _git(tmp, "symbolic-ref", "HEAD", f"refs/heads/{raw['branch']}")
            _git(tmp, "-c", "user.name=test", "-c", "user.email=test@example.com",
                 "commit", "-q", "--allow-empty", "-m", "init")

        if "bash" in raw:
            event = {"tool_name": "Bash", "tool_input": {"command": raw["bash"]}}
        else:
            event = {"tool_name": raw["tool"], "tool_input": {"file_path": raw["file_path"]}}
        event["cwd"] = cwd

        env = {k: v for k, v in os.environ.items() if k not in MACHINE_ENV}
        env["KUBECONFIG"] = str(CORPUS / raw.get("kubeconfig", DEFAULT_KUBECONFIG))
        env.update(raw.get("env", {}))

        proc = subprocess.run(
            [sys.executable, str(GUARDS[case.guard])],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            timeout=15,
            cwd=cwd,
            env=env,
        )
        return proc.returncode

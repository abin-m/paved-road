"""Load the guard command corpus and run one case against its guard.

Each guard has a directory, corpus/<guard>/. Each line of its bypass.jsonl
must be blocked (exit 2), and each line of its benign.jsonl must be allowed
(exit 0). A file per guard means PRs for different guards never edit the same
file. Held-out cases live in corpus/heldout/<guard>/, in the same format;
corpus/heldout/README.md says how they are kept untuned. A line has these keys:

  label        short name for the report
  bash         a Bash command, or
  tool, file_path   a file-tool call such as Read or Write
  branch       optional: run in a fresh git repo on this branch
  cwd          optional: run in this fixture directory, relative to corpus/
  kubeconfig   optional: kubeconfig fixture, relative to corpus/; default
               fixtures/dev-context.yaml, so no case reads the machine's own
  env          optional: extra environment variables, used as given
  pulumi_stack optional: run in a Pulumi project with this stack selected
  known_miss   optional: the guard gets this case wrong today
  issue        the GitHub issue that fixes a known miss; required with known_miss
  limit        optional: the guard gets this case wrong by design, and the
               README lists it under what the guards don't stop
  source       who wrote the case and how; required in heldout/, and
               "author" when left out of the main corpus
"""

import hashlib
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
SPLITS = {"dev": CORPUS, "heldout": CORPUS / "heldout"}

GUARDS = {
    "secrets": HOOKS / "secrets-guard.py",
    "main": HOOKS / "main-guard.py",
    "prod": HOOKS / "prod-guard.py",
}
# The hook hooks.json runs for Bash: all three guards in one process.
BASH_GUARDS = HOOKS / "bash-guards.py"
EXPECTED_EXIT = {"bypass": 2, "benign": 0}
DEFAULT_KUBECONFIG = "fixtures/dev-context.yaml"
# Inherited values that would make prod-guard's result depend on the machine.
MACHINE_ENV = ("KUBECONFIG", "HELM_KUBECONTEXT", "TF_WORKSPACE", "TF_DATA_DIR",
               "AWS_PROFILE", "AWS_DEFAULT_PROFILE", "PULUMI_HOME")


@dataclass
class Case:
    guard: str
    kind: str
    raw: dict
    where: str
    split: str = "dev"

    @property
    def source(self) -> str:
        return self.raw.get("source", "author")

    @property
    def expected(self) -> int:
        return EXPECTED_EXIT[self.kind]

    @property
    def label(self) -> str:
        return self.raw["label"]

    @property
    def known_miss(self) -> bool:
        """True for a known miss or a documented limit: the guard gets it wrong."""
        return bool(self.raw.get("known_miss") or self.raw.get("limit"))

    @property
    def limit(self) -> bool:
        return bool(self.raw.get("limit"))


def load(split: str = "dev") -> list:
    """Every case in one split, "dev" or "heldout". Raises ValueError on a malformed line."""
    base = SPLITS[split]
    cases = []
    for guard in GUARDS:
        for kind in EXPECTED_EXIT:
            path = base / guard / f"{kind}.jsonl"
            prefix = "heldout/" if split == "heldout" else ""
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                where = f"{prefix}{guard}/{path.name}:{n}"
                raw = json.loads(line)
                if not raw.get("label"):
                    raise ValueError(f"{where}: missing label")
                if "bash" not in raw and not ("tool" in raw and "file_path" in raw):
                    raise ValueError(f"{where}: needs 'bash', or 'tool' and 'file_path'")
                if raw.get("known_miss") and not raw.get("issue"):
                    raise ValueError(f"{where}: a known miss needs the issue that fixes it")
                if raw.get("known_miss") and raw.get("limit"):
                    raise ValueError(f"{where}: a case is a known miss or a limit, not both")
                if split == "heldout":
                    if not raw.get("source"):
                        raise ValueError(f"{where}: a held-out case needs a source")
                    if raw.get("known_miss") or raw.get("limit"):
                        raise ValueError(f"{where}: a held-out case has no known_miss or limit")
                cases.append(Case(guard, kind, raw, where, split))
    return cases


def _git(cwd: str, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, timeout=15)


def run(case: Case, script: pathlib.Path = None) -> int:
    """Run the case's guard, or `script` instead, and return its exit code."""
    raw = case.raw
    with tempfile.TemporaryDirectory() as tmp:
        cwd = str(CORPUS / raw["cwd"]) if "cwd" in raw else tmp
        if "branch" in raw:
            # rev-parse fails on an unborn branch, so the repo needs one commit.
            _git(tmp, "init", "-q")
            _git(tmp, "symbolic-ref", "HEAD", f"refs/heads/{raw['branch']}")
            _git(tmp, "-c", "user.name=test", "-c", "user.email=test@example.com",
                 "commit", "-q", "--allow-empty", "-m", "init")

        pulumi_home = os.path.join(tmp, "pulumi-home")
        if "pulumi_stack" in raw:
            # Pulumi keeps the selected stack in a file named after the sha1
            # of the project file's real path, so it is built here.
            project = os.path.join(tmp, "Pulumi.yaml")
            with open(project, "w", encoding="utf-8") as fh:
                fh.write("name: api\nruntime: python\n")
            digest = hashlib.sha1(os.path.realpath(project).encode()).hexdigest()
            os.makedirs(os.path.join(pulumi_home, "workspaces"))
            with open(os.path.join(pulumi_home, "workspaces", f"api-{digest}-workspace.json"),
                      "w", encoding="utf-8") as fh:
                json.dump({"stacks": {"https://api.pulumi.com": raw["pulumi_stack"]}}, fh)

        if "bash" in raw:
            event = {"tool_name": "Bash", "tool_input": {"command": raw["bash"]}}
        else:
            event = {"tool_name": raw["tool"], "tool_input": {"file_path": raw["file_path"]}}
        event["cwd"] = cwd

        env = {k: v for k, v in os.environ.items() if k not in MACHINE_ENV}
        env["KUBECONFIG"] = str(CORPUS / raw.get("kubeconfig", DEFAULT_KUBECONFIG))
        env["PULUMI_HOME"] = pulumi_home
        env.update(raw.get("env", {}))

        proc = subprocess.run(
            [sys.executable, str(script or GUARDS[case.guard])],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            timeout=15,
            cwd=cwd,
            env=env,
        )
        return proc.returncode

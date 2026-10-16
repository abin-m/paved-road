#!/usr/bin/env python3
"""tools/lint.py — paved-road pack linter.

Checks, in order of what has actually broken a pack in practice:

  1. Every .json parses.
  2. Marketplace manifest lists a plugin whose source directory exists, and the
     plugin.json inside it declares the same name.
  3. Every skills/<dir>/SKILL.md has YAML frontmatter with non-empty `name` and
     `description`, and `name` equals the directory name (the slash command is
     derived from it — a mismatch means /plugin:skill silently does not exist).
  4. Every agents/<file>.md has frontmatter with `name` and `description`.
  5. Every hook script referenced by hooks.json exists, and every hook script on
     disk is referenced by hooks.json (an unwired guard never runs).
  6. Every hook script is named in the test file (a guard with no test has never
     been proven to block anything).
  7. Filenames are kebab-case, with the usual documented exemptions.
  8. Shipped Python parses on the advertised floor (PY_FLOOR) — CI runs one
     modern interpreter, so newer-only syntax passes there and breaks the
     consumer running an older python3.

Run from the repo root:  python3 tools/lint.py
Exit 0 clean, 1 on any error.
"""

import ast
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "paved-road-core"

# The floor the README promises consumers.
PY_FLOOR = (3, 9)

KEBAB_EXEMPT = {"README.md", "SKILL.md", "LICENSE", "CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md"}
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9.]+)?$")
# Python mandates snake_case for anything `import`ed — a hyphen is a syntax
# error in an import statement. Shared libraries beside the entry points are
# the one place the kebab rule cannot apply.
LIB_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*_lib\.py$")

ERRORS: list[str] = []


def err(msg: str) -> None:
    ERRORS.append(msg)
    print(f"  ERROR: {msg}")


def frontmatter(path: pathlib.Path) -> dict:
    """Parse the leading --- block. Deliberately not a YAML dependency: the
    frontmatter here is flat key/value, and the linter must run with stdlib only."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    _, _, rest = text.partition("---\n")
    block, _, _ = rest.partition("\n---")
    out = {}
    for line in block.splitlines():
        key, sep, value = line.partition(":")
        if sep and not key.startswith(" "):
            out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def check_json() -> list[pathlib.Path]:
    found = []
    for path in sorted(ROOT.rglob("*.json")):
        if ".git" in path.parts:
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
            found.append(path)
        except json.JSONDecodeError as exc:
            err(f"{path.relative_to(ROOT)}: invalid JSON — {exc}")
    return found


def check_manifests() -> None:
    market = ROOT / ".claude-plugin" / "marketplace.json"
    if not market.exists():
        err("missing .claude-plugin/marketplace.json")
        return
    data = json.loads(market.read_text(encoding="utf-8"))
    for entry in data.get("plugins", []):
        src = (ROOT / entry["source"]).resolve()
        manifest = src / ".claude-plugin" / "plugin.json"
        if not manifest.exists():
            err(f"marketplace lists {entry['name']} but {manifest} is missing")
            continue
        declared = json.loads(manifest.read_text(encoding="utf-8")).get("name")
        if declared != entry["name"]:
            err(f"name mismatch: marketplace says {entry['name']!r}, plugin.json says {declared!r}")


def check_skills() -> None:
    for skill_dir in sorted((PLUGIN / "skills").iterdir()):
        if not skill_dir.is_dir():
            continue
        md = skill_dir / "SKILL.md"
        if not md.exists():
            err(f"skills/{skill_dir.name}/ has no SKILL.md")
            continue
        fm = frontmatter(md)
        if not fm.get("description"):
            err(f"skills/{skill_dir.name}/SKILL.md: empty or missing 'description'")
        if fm.get("name") != skill_dir.name:
            err(
                f"skills/{skill_dir.name}/SKILL.md: frontmatter name {fm.get('name')!r} "
                f"does not match directory name"
            )


def check_agents() -> None:
    for md in sorted((PLUGIN / "agents").glob("*.md")):
        fm = frontmatter(md)
        for field in ("name", "description"):
            if not fm.get(field):
                err(f"agents/{md.name}: empty or missing '{field}'")


def check_hooks() -> None:
    hooks_json = PLUGIN / "hooks" / "hooks.json"
    if not hooks_json.exists():
        err("missing hooks/hooks.json")
        return
    raw = hooks_json.read_text(encoding="utf-8")
    wired = set(re.findall(r"hooks/([a-z0-9-]+\.py)", raw))

    on_disk = {p.name for p in (PLUGIN / "hooks").glob("*.py")}
    # A guard that a wired hook loads, such as bash-guards.py loading
    # prod-guard.py, runs too.
    for name in sorted(wired & on_disk):
        src = (PLUGIN / "hooks" / name).read_text(encoding="utf-8")
        wired |= set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*-guard\.py", src)) - {name}
    for name in sorted(wired - on_disk):
        err(f"hooks.json wires hooks/{name} but the file does not exist")
    for name in sorted(on_disk - wired):
        err(f"hooks/{name} exists but is not wired in hooks.json — it will never run")

    tests = PLUGIN / "tests" / "guards.test.py"
    if not tests.exists():
        err("missing tests/guards.test.py")
        return
    test_src = tests.read_text(encoding="utf-8")
    for name in sorted(on_disk):
        if name not in test_src:
            err(f"hooks/{name} has no case in tests/guards.test.py")


def check_names() -> None:
    for path in sorted(ROOT.rglob("*")):
        if any(part in {".git", ".github", "__pycache__"} for part in path.parts):
            continue
        if not path.is_file() or path.name in KEBAB_EXEMPT or path.name.startswith("."):
            continue
        if LIB_RE.match(path.name):
            continue
        stem = path.name.replace(".test.py", ".py")
        if not KEBAB_RE.match(stem):
            err(f"{path.relative_to(ROOT)}: filename is not kebab-case")


def git_modes() -> dict:
    """Path -> git index mode ('100755' executable, '100644' not).

    Git's recorded mode is the portable answer, and the one that matters: it is
    what lands in a consumer's checkout. The filesystem bit cannot be used —
    NTFS has no POSIX exec bit, so `st_mode & 0o111` is false for every file on
    a Windows runner and the check fails there for no real reason. Empty dict
    when git is unavailable, which degrades to the filesystem check below.
    """
    try:
        out = subprocess.run(
            ["git", "ls-files", "-s"], cwd=ROOT, capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if out.returncode != 0:
        return {}
    modes = {}
    for line in out.stdout.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if parts and path:
            modes[path] = parts[0]
    return modes


def check_bin() -> None:
    """Entry points must be runnable: executable mode plus a shebang.

    A bin/ script without the executable bit installs fine and then fails the
    first time an agent calls it by name — the failure mode this catches.
    """
    bin_dir = PLUGIN / "bin"
    if not bin_dir.is_dir():
        return
    entries = [p for p in sorted(bin_dir.iterdir()) if p.is_file() and not p.name.startswith(".")]
    modes = git_modes()
    for path in entries:
        if LIB_RE.match(path.name):
            continue  # imported, never executed directly
        rel = path.relative_to(ROOT).as_posix()
        if rel in modes:
            if modes[rel] != "100755":
                err(
                    f"bin/{path.name}: git mode is {modes[rel]}, not 100755 — "
                    f"run `git update-index --chmod=+x {rel}` (chmod +x alone does "
                    f"not fix an already-tracked file)"
                )
        elif not path.stat().st_mode & 0o111:
            # Untracked, or no git available: fall back to the filesystem bit.
            # Skipped on Windows, where NTFS has no POSIX exec bit to read.
            if not sys.platform.startswith("win"):
                err(f"bin/{path.name}: not executable (chmod +x)")
        first = path.read_text(encoding="utf-8").splitlines()[:1]
        if not first or not first[0].startswith("#!"):
            err(f"bin/{path.name}: missing shebang")

    tests = PLUGIN / "tests" / "tools.test.py"
    if entries and not tests.exists():
        err("bin/ ships tools but tests/tools.test.py is missing")
        return
    if tests.exists():
        src = tests.read_text(encoding="utf-8")
        for path in entries:
            if LIB_RE.match(path.name):
                continue
            if path.name not in src:
                err(f"bin/{path.name} has no case in tests/tools.test.py")


def check_python_floor() -> None:
    for path in sorted(ROOT.rglob("*.py")):
        if ".git" in path.parts:
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), feature_version=PY_FLOOR)
        except SyntaxError as exc:
            floor = ".".join(str(n) for n in PY_FLOOR)
            err(f"{path.relative_to(ROOT)}: does not parse on Python {floor} — {exc}")


def main() -> int:
    print("paved-road pack lint")
    files = check_json()
    print(f"  {len(files)} JSON file(s) parsed")
    check_manifests()
    check_skills()
    check_agents()
    check_hooks()
    check_bin()
    check_names()
    check_python_floor()

    if ERRORS:
        print(f"\n{len(ERRORS)} error(s)")
        return 1
    print("  clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())

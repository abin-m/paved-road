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
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "paved-road-core"

# The floor the README promises consumers.
PY_FLOOR = (3, 9)

KEBAB_EXEMPT = {"README.md", "SKILL.md", "LICENSE", "CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md"}
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9.]+)?$")

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
        if any(part in {".git", ".github"} for part in path.parts):
            continue
        if not path.is_file() or path.name in KEBAB_EXEMPT or path.name.startswith("."):
            continue
        stem = path.name.replace(".test.py", ".py")
        if not KEBAB_RE.match(stem):
            err(f"{path.relative_to(ROOT)}: filename is not kebab-case")


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
    check_names()
    check_python_floor()

    if ERRORS:
        print(f"\n{len(ERRORS)} error(s)")
        return 1
    print("  clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())

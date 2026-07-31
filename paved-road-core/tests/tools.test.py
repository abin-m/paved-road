#!/usr/bin/env python3
"""Tests for the bin/ tools — pure logic only, no network, no token.

    python3 paved-road-core/tests/tools.test.py

What is covered is what breaks silently: remote-URL parsing (an unparsed remote
sends every call to the wrong repo), token resolution *order* (a stale env var
quietly shadowing the keychain), issue classification, and board rendering.
The HTTP layer is deliberately not mocked — a mocked GitHub proves nothing
about GitHub.
"""

import datetime
import importlib.machinery
import importlib.util
import pathlib
import sys

BIN = pathlib.Path(__file__).resolve().parent.parent / "bin"
sys.path.insert(0, str(BIN))

import gh_lib  # noqa: E402


def load(script_name, module_name):
    """Import a kebab-case, extensionless entry point as a module."""
    spec = importlib.util.spec_from_loader(
        module_name, importlib.machinery.SourceFileLoader(module_name, str(BIN / script_name))
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


board = load("board", "board_mod")
gh_issue = load("gh-issue", "gh_issue_mod")
gh_pr = load("gh-pr", "gh_pr_mod")
gh_token = load("gh-token", "gh_token_mod")

FAILURES = []


def check(label, got, want):
    if got == want:
        print(f"PASS  {label}")
    else:
        FAILURES.append(label)
        print(f"FAIL  {label}\n        got:  {got!r}\n        want: {want!r}")


# ---------------------------------------------------------------------------
# Remote parsing
# ---------------------------------------------------------------------------

for url, want in [
    ("git@github.com:abin-m/paved-road.git", "abin-m/paved-road"),
    ("git@github.com:abin-m/paved-road", "abin-m/paved-road"),
    ("https://github.com/abin-m/paved-road.git", "abin-m/paved-road"),
    ("https://github.com/abin-m/paved-road", "abin-m/paved-road"),
    ("https://x-access-token:abc@github.com/abin-m/paved-road.git", "abin-m/paved-road"),
    ("ssh://git@github.com/abin-m/paved-road.git", "abin-m/paved-road"),
    ("  git@github.com:abin-m/paved-road.git\n", "abin-m/paved-road"),
    ("not-a-remote", ""),
    ("", ""),
]:
    check(f"parse_remote({url!r})", gh_lib.parse_remote(url), want)


# ---------------------------------------------------------------------------
# Token resolution order
# ---------------------------------------------------------------------------

check(
    "keychain wins over env",
    gh_lib.resolve_token(env={"GH_TOKEN": "env-tok"}, keychain=lambda: "kc-tok", gh_cli=lambda: ""),
    ("kc-tok", "keychain"),
)
check(
    "env used when keychain empty",
    gh_lib.resolve_token(env={"GH_TOKEN": "env-tok"}, keychain=lambda: "", gh_cli=lambda: "cli"),
    ("env-tok", "GH_TOKEN"),
)
check(
    "GITHUB_TOKEN is the second env name",
    gh_lib.resolve_token(env={"GITHUB_TOKEN": "gt"}, keychain=lambda: "", gh_cli=lambda: "cli"),
    ("gt", "GITHUB_TOKEN"),
)
check(
    "gh cli is the last resort",
    gh_lib.resolve_token(env={}, keychain=lambda: "", gh_cli=lambda: "cli-tok"),
    ("cli-tok", "gh cli"),
)
check(
    "nothing available",
    gh_lib.resolve_token(env={}, keychain=lambda: "", gh_cli=lambda: ""),
    ("", "none"),
)
check(
    "windows keychain backend is absent, not crashing",
    gh_lib.keychain_get(platform="win32"),
    "",
)


# ---------------------------------------------------------------------------
# Issue classification
# ---------------------------------------------------------------------------

CONFIG = dict(board.DEFAULTS)


def issue(number=1, labels=(), assignee=None):
    return {
        "number": number,
        "title": f"issue {number}",
        "labels": [{"name": name} for name in labels],
        "assignee": {"login": assignee} if assignee else None,
    }


check("unassigned + labelled = ready", board.classify(issue(labels=["feat"]), CONFIG), "ready")
check("assigned = in progress", board.classify(issue(labels=["feat"], assignee="abin-m"), CONFIG), "in_progress")
check("blocked label wins over assignee", board.classify(issue(labels=["blocked"], assignee="abin-m"), CONFIG), "blocked")
check("no labels at all = triage", board.classify(issue(), CONFIG), "triage")
check("triage label = triage", board.classify(issue(labels=["needs-triage"]), CONFIG), "triage")
check("label match is case-insensitive", board.classify(issue(labels=["Blocked"]), CONFIG), "blocked")


# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------

DATA = {
    "abin-m/paved-road": {
        "issues": [
            issue(1, ["feat"]),
            issue(2, ["feat"], assignee="abin-m"),
            issue(3, ["blocked"]),
            issue(4),
        ],
        "prs": [
            {
                "number": 9,
                "title": "ci: add workflows",
                "draft": False,
                "head": {"ref": "feat/ci"},
                "base": {"ref": "main"},
            }
        ],
    }
}

NOW = datetime.datetime(2026, 7, 31, 12, 0, tzinfo=datetime.timezone.utc)
CONFIG_WITH_DEADLINE = dict(CONFIG, deadlines=[{"label": "v1.0", "date": "2026-08-10"}])
text = board.render(CONFIG_WITH_DEADLINE, DATA, now=NOW)

check("ready section counts one", "## Ready (1)" in text, True)
check("in-progress section counts one", "## In progress (1)" in text, True)
check("blocked section counts one", "## Blocked (1)" in text, True)
check("triage section counts one", "## Needs triage (1)" in text, True)
check("open PR section counts one", "## Open PRs (1)" in text, True)
check("assignee shown in progress", "@abin-m" in text, True)
check("deadline countdown rendered", "10d left" in text, True)
check("generation timestamp rendered", "2026-07-31 12:00 UTC" in text, True)

overdue = board.countdown([{"label": "gone", "date": "2026-07-01"}], NOW.date())
check("overdue deadline is labelled overdue", "30d OVERDUE" in overdue[0], True)
check("undated deadline is skipped, not fatal", board.countdown([{"label": "x"}], NOW.date()), [])

empty = board.render(CONFIG, {"r": {"issues": [], "prs": []}}, now=NOW)
check("empty board renders _none_", empty.count("_none_"), 5)


# ---------------------------------------------------------------------------
# CLI surfaces — argument wiring, before any network call
# ---------------------------------------------------------------------------

issue_args = gh_issue.build_parser().parse_args(
    ["create", "--title", "T", "--label", "a", "--label", "b"]
)
check("gh-issue repeated --label collects", issue_args.label, ["a", "b"])
check("gh-issue create binds its handler", issue_args.func, gh_issue.cmd_create)

pr_args = gh_pr.build_parser().parse_args(["open", "--title", "T", "--closes", "3", "--draft"])
check("gh-pr --closes collects", pr_args.closes, ["3"])
check("gh-pr --draft flag", pr_args.draft, True)
check("gh-pr status number is optional", gh_pr.build_parser().parse_args(["status"]).number, None)

# gh-token: --help must not need a token, and an unknown flag must fail loudly
# rather than printing something a shell would capture as if it were a secret.
try:
    check("gh-token --help exits 0", gh_token.main(["gh-token", "--help"]), 0)
except SystemExit as exc:
    check("gh-token --help exits 0", exc.code, 0)

try:
    gh_token.main(["gh-token", "--bogus"])
    check("gh-token rejects unknown flag", "no exit", "SystemExit")
except SystemExit:
    check("gh-token rejects unknown flag", "SystemExit", "SystemExit")

for parser, argv, label in [
    (gh_issue.build_parser(), ["create"], "gh-issue create without --title exits"),
    (gh_pr.build_parser(), [], "gh-pr with no subcommand exits"),
    (gh_issue.build_parser(), ["list", "--state", "bogus"], "gh-issue rejects bad --state"),
]:
    try:
        parser.parse_args(argv)
        check(label, "no exit", "SystemExit")
    except SystemExit:
        check(label, "SystemExit", "SystemExit")


print(f"\n{'FAILED: ' + ', '.join(FAILURES) if FAILURES else 'all checks passed'}")
sys.exit(1 if FAILURES else 0)

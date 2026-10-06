#!/usr/bin/env python3
"""Tests for the bin/ tools — pure logic only, no network, no token.

    python3 paved-road-core/tests/tools.test.py

What is covered is what breaks silently: remote-URL parsing (an unparsed remote
sends every call to the wrong repo), token resolution *order* (a stale env var
quietly shadowing the keychain), issue classification, board rendering, and the
prose-check rules (each one flagged and each one left alone).
The HTTP layer is deliberately not mocked — a mocked GitHub proves nothing
about GitHub.
"""

import datetime
import importlib.machinery
import importlib.util
import pathlib
import sys
import tempfile

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
prose_check = load("prose-check", "prose_check_mod")

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


# ---------------------------------------------------------------------------
# prose-check
# ---------------------------------------------------------------------------


def faults(text, **kwargs):
    return [fault for _, fault, _ in prose_check.check_text(text, **kwargs)]


LONG = " ".join(["Word"] + ["word"] * 30) + "."

for label, text, want in [
    ("em dash aside", "The guard blocks it — always.", ["dash-aside"]),
    ("spaced double hyphen", "The guard blocks it -- always.", ["dash-aside"]),
    ("number range is not an aside", "Use Python 3.9–3.13.", []),
    ("hyphenated word is not an aside", "A stdlib-only script.", []),
    ("semicolon chain", "Push the branch; open the PR.", ["semicolon-chain"]),
    ("html entity is not a semicolon", "Lint &amp; test.", []),
    ("unicode arrow", "Plan → apply.", ["arrow-word"]),
    ("ascii arrow", "Plan -> apply.", ["arrow-word"]),
    ("comparison is not an arrow", "Needs Python >= 3.9.", []),
    ("filler", "Note that the token expires.", ["filler"]),
    ("filler is matched on word boundaries", "A footnote that helps.", []),
    ("buzzword", "A robust pipeline.", ["buzzword"]),
    ("buzzword inside a longer word", "Use the leveraged-buyout fixture.", []),
    ("status prose", "The parser was recently rewritten.", ["status-prose"]),
    ("long sentence", LONG, ["long-sentence"]),
    ("two short sentences", "One short sentence. " * 2 + LONG[:60] + ".", []),
    ("long sentence wrapped over lines", LONG.replace(" ", "\n", 3), ["long-sentence"]),
    ("list items are separate sentences", "\n".join(["- five words in this item"] * 8), []),
    ("four bolds close together", "**a** b **c** d\n**e** f **g** h", ["loud-bold"]),
    ("three bolds", "**a** b **c** d **e**", []),
    ("bolds far apart", "**a** and **b**" + "\n\nPlain." * 25 + "\n\n**c** and **d**", []),
    ("fenced code is skipped", "```sh\na -> b; c — d\n```", []),
    ("inline code is skipped", "Run `a -> b; c` first.", []),
    ("table row is skipped", "| a — b | c -> d |", []),
    ("block quote is skipped", "> a — b; c", []),
    ("frontmatter is skipped", "---\ndescription: a — b\n---\nPlain text.", []),
    ("url is skipped", "See https://example.com/a->b;c for more.", []),
    (
        "off and on markers",
        "<!-- prose-check off -->\nA — b.\n<!-- prose-check on -->\nC — d.",
        ["dash-aside"],
    ),
    ("heading is checked", "## Plan -> apply", ["arrow-word"]),
]:
    check(f"prose-check: {label}", faults(text), want)

check("prose-check: --max-words is honoured", faults("One two three four.", max_words=3), ["long-sentence"])
check(
    "prose-check: finding carries its line number",
    [(line, fault) for line, fault, _ in prose_check.check_text("Fine.\n\nNot fine — here.")],
    [(3, "dash-aside")],
)
check(
    "prose-check: long sentence reported on the line it starts",
    [line for line, _, _ in prose_check.check_text("Short one.\n" + LONG)],
    [2],
)

with tempfile.TemporaryDirectory() as tmp:
    docs = pathlib.Path(tmp)
    (docs / "clean.md").write_text("A plain sentence.\n", encoding="utf-8")
    check("prose-check exits 0 on a clean directory", prose_check.main([tmp]), 0)
    (docs / "sub").mkdir()
    (docs / "sub" / "bad.md").write_text("Plan -> apply.\n", encoding="utf-8")
    (docs / "notes.txt").write_text("Plan -> apply.\n", encoding="utf-8")
    check("prose-check exits 1 on a finding in a subdirectory", prose_check.main([tmp]), 1)
    check("prose-check --warn exits 0 on a finding", prose_check.main(["--warn", tmp]), 0)
    check("prose-check checks a named non-.md file", prose_check.main([str(docs / "notes.txt")]), 1)
    check("prose-check exits 2 on a missing path", prose_check.main([str(docs / "absent.md")]), 2)


print(f"\n{'FAILED: ' + ', '.join(FAILURES) if FAILURES else 'all checks passed'}")
sys.exit(1 if FAILURES else 0)

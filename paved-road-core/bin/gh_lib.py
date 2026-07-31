"""gh_lib.py — shared runtime for the paved-road GitHub tools.

Stdlib only: these scripts run wherever the plugin is installed, with no
`pip install` step and no dependency on the `gh` CLI being present (it is used
as a *fallback* token source, never as the transport).

Snake_case filename because Python mandates it for an imported module — a
hyphen is a syntax error in `import`. The executable entry points beside it
stay kebab-case.

Token resolution order (first hit wins), in `resolve_token`:
  1. OS keychain     — macOS `security`, Linux `secret-tool`
  2. GH_TOKEN / GITHUB_TOKEN env var
  3. `gh auth token` — the CLI's own store, if gh is installed and logged in

The value is returned to the *caller's shell*, never printed into an agent's
context: the documented call shape is `GH_TOKEN=$(gh-token) gh-issue list`.
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
KEYCHAIN_SERVICE = "github.com"
KEYCHAIN_ACCOUNT = "api"


def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------


def _run(cmd):
    """Run a command, return stdout stripped, or "" on any failure."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def keychain_get(platform=None):
    # Indirected so a type checker does not narrow sys.platform to the host it
    # is running on and call the other branches dead code — they are the ones
    # that matter on someone else's machine.
    platform = sys.platform if platform is None else platform
    if platform == "darwin":
        return _run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE,
             "-a", KEYCHAIN_ACCOUNT, "-w"]
        )
    if platform.startswith("linux"):
        return _run(
            ["secret-tool", "lookup", "service", KEYCHAIN_SERVICE,
             "account", KEYCHAIN_ACCOUNT]
        )
    return ""  # Windows: no keychain backend — env var or gh CLI


def resolve_token(env=None, keychain=keychain_get, gh_cli=None):
    """First available token, with its source. Returns (token, source)."""
    env = os.environ if env is None else env
    gh_cli = (lambda: _run(["gh", "auth", "token"])) if gh_cli is None else gh_cli

    token = keychain()
    if token:
        return token, "keychain"
    for var in ("GH_TOKEN", "GITHUB_TOKEN"):
        if env.get(var):
            return env[var], var
    token = gh_cli()
    if token:
        return token, "gh cli"
    return "", "none"


def require_token():
    token, _ = resolve_token()
    if not token:
        die(
            "no GitHub token found. Store one in the keychain (see the "
            "token-setup skill), or export GH_TOKEN, or run `gh auth login`."
        )
    return token


# ---------------------------------------------------------------------------
# Repo identity
# ---------------------------------------------------------------------------

_REMOTE_RE = re.compile(
    r"""^(?:
        git@[^:]+:                 # git@github.com:
      | ssh://git@[^/]+/           # ssh://git@github.com/
      | https?://(?:[^@/]+@)?[^/]+/  # https://github.com/ , with optional user
    )(?P<slug>[^/]+/[^/]+?)(?:\.git)?/?$""",
    re.VERBOSE,
)


def parse_remote(url):
    """'git@github.com:owner/repo.git' -> 'owner/repo'. "" when unparseable."""
    match = _REMOTE_RE.match((url or "").strip())
    return match.group("slug") if match else ""


def current_repo(explicit=None):
    if explicit:
        return explicit
    slug = parse_remote(_run(["git", "remote", "get-url", "origin"]))
    if not slug:
        die("cannot determine the repo — run inside a git repo or pass --repo owner/name")
    return slug


def current_branch():
    return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def default_branch(repo, token):
    return api("GET", f"/repos/{repo}", token).get("default_branch", "main")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def api(method, path, token, body=None, params=None):
    """One GitHub REST call. Returns parsed JSON (dict or list)."""
    url = API + path
    if params:
        pairs = [f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items() if v is not None]
        if pairs:
            url += "?" + "&".join(pairs)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            payload = json.loads(exc.read())
            detail = payload.get("message", "")
            for err in payload.get("errors", []) or []:
                detail += f" — {err.get('message') or err}"
        except (ValueError, OSError):
            pass
        hint = ""
        if exc.code in (401, 403):
            hint = (
                "  (token missing scope or expired: a private repo needs `repo`; "
                "run `gh-token --check`)"
            )
        elif exc.code == 404:
            hint = "  (wrong repo slug, or the token cannot see this private repo)"
        die(f"GitHub API {method} {path} -> {exc.code} {detail}{hint}")
    except urllib.error.URLError as exc:
        die(f"cannot reach GitHub: {exc.reason}")


def paginate(path, token, params=None, limit=200):
    """Collect list results across pages, up to `limit` items."""
    out = []
    page = 1
    params = dict(params or {})
    while len(out) < limit:
        params.update({"per_page": 100, "page": page})
        batch = api("GET", path, token, params=params)
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return out[:limit]

#!/usr/bin/env python3
"""working-style.py: print the pack's working style into a new session.

Claude Code SessionStart hook. Whatever it writes to stdout is added to the
session's context. Stdlib only.

It always exits 0. A missing file costs the session its style rules, which is
better than a session that fails to start.
"""

import pathlib
import sys

STYLE = pathlib.Path(__file__).resolve().parent.parent / "working-style.md"


def main() -> int:
    try:
        text = STYLE.read_bytes()
    except OSError as exc:
        print(f"working-style: cannot read {STYLE}: {exc}", file=sys.stderr)
        return 0
    # Bytes, so a Windows console code page cannot fail the write.
    sys.stdout.buffer.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

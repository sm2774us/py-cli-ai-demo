"""Wraps over-long comment lines to fit within a max line length.

`ruff check --fix` cannot auto-fix E501 (line too long) — it has no
general safe way to reflow text. This script handles the one case that
actually matters for AI-generated code: full-line `#` comments that run
past the limit. It re-wraps them (preserving indentation) instead of
leaving them for a human or an extra AI round-trip.

Deliberately conservative: it only touches whole-line comments (a line
whose stripped content starts with `#`). It does not touch code lines,
inline trailing comments, docstrings, or strings, since reflowing those
safely requires a real parser.

Usage:
    uv run python scripts/wrap_comments.py --max-length 80 FILE [FILE ...]
"""

from __future__ import annotations

import argparse
import sys
import textwrap


def wrap_comment_line(line: str, max_length: int) -> list[str]:
    """Wraps one over-long `#` comment line into several shorter ones.

    Args:
        line: A single source line (no trailing newline).
        max_length: Maximum allowed line length.

    Returns:
        One or more lines to replace the original with. Returns the
        original line unchanged (as a single-item list) if it isn't a
        whole-line comment or is already short enough.
    """
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]

    if not stripped.startswith("#") or len(line) <= max_length:
        return [line]

    marker = "#"
    rest = stripped[1:]
    extra_marker = ""
    if rest.startswith("#"):  # shebang-style `##` or similar, leave as-is
        return [line]
    if rest.startswith("!"):  # shebang line, never touch
        return [line]

    text = rest.strip()
    if not text:
        return [line]

    prefix = f"{indent}{marker}{extra_marker} "
    width = max(max_length - len(prefix), 20)
    wrapped = textwrap.wrap(text, width=width) or [text]
    return [f"{prefix}{chunk}" for chunk in wrapped]


def wrap_file(path: str, max_length: int) -> bool:
    """Rewrites a file with any over-long comment lines wrapped.

    Args:
        path: File to process in place.
        max_length: Maximum allowed line length.

    Returns:
        True if the file was modified.
    """
    with open(path, encoding="utf-8") as handle:
        original_lines = handle.read().splitlines()

    new_lines: list[str] = []
    changed = False
    for line in original_lines:
        replacement = wrap_comment_line(line, max_length)
        if replacement != [line]:
            changed = True
        new_lines.extend(replacement)

    if changed:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(new_lines) + "\n")

    return changed


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-length", type=int, default=80)
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    for path in args.files:
        if wrap_file(path, args.max_length):
            print(f"wrapped long comments in {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

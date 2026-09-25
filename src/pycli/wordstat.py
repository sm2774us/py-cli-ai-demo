"""wordstat: a word-frequency CLI tool.

This module is INTENTIONALLY sub-optimal. It exists as a teaching example:
an AI coding agent (Claude Code, Copilot, Gemini CLI, etc.) is meant to
read this, find the algorithmic and style issues, and produce an improved
version with benchmarks proving the improvement.

Known issues (do not fix here; this is the "before" state):
  - `top_n_words` is O(n^2) via repeated linear scans for the max.
  - `tokenize` rebuilds a new string one character at a time.
  - `count_words` uses a list of [word, count] pairs with linear search
    instead of a dict/Counter, making it O(n^2) overall.
  - No type-narrowing on CLI args validation beyond argparse defaults.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def tokenize(text: str) -> list[str]:
    """Splits text into lowercase alphabetic words.

    Args:
        text: Raw input text.

    Returns:
        A list of lowercase word tokens.
    """
    words: list[str] = []
    current = ""
    for ch in text:
        if ch.isalpha():
            current = current + ch.lower()  # sub-optimal: string concat in loop
        else:
            if current:
                words.append(current)
                current = ""
    if current:
        words.append(current)
    return words


def count_words(words: list[str]) -> list[list]:
    """Counts word frequencies using a linear-search list (sub-optimal).

    Args:
        words: Tokenized words.

    Returns:
        A list of [word, count] pairs, order of first appearance.
    """
    counts: list[list] = []
    for word in words:
        found = False
        for pair in counts:  # O(n) scan per word -> O(n^2) total
            if pair[0] == word:
                pair[1] += 1
                found = True
                break
        if not found:
            counts.append([word, 1])
    return counts


def top_n_words(counts: list[list], n: int) -> list[list]:
    """Returns the top-n [word, count] pairs by count, descending.

    Args:
        counts: List of [word, count] pairs.
        n: Number of top entries to return.

    Returns:
        Up to n [word, count] pairs sorted by count descending.
    """
    remaining = [pair[:] for pair in counts]
    result: list[list] = []
    for _ in range(min(n, len(remaining))):
        best_idx = 0
        for i in range(1, len(remaining)):  # O(n) max-scan per iteration
            if remaining[i][1] > remaining[best_idx][1]:
                best_idx = i
        result.append(remaining.pop(best_idx))
    return result


def analyze(text: str, top_n: int) -> list[list]:
    """Runs the full analysis pipeline on a text blob.

    Args:
        text: Raw input text.
        top_n: Number of top words to return.

    Returns:
        Top-n [word, count] pairs.
    """
    words = tokenize(text)
    counts = count_words(words)
    return top_n_words(counts, top_n)


def build_parser() -> argparse.ArgumentParser:
    """Builds the CLI argument parser.

    Returns:
        A configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="wordstat",
        description="Compute top-N word frequencies from a text file.",
    )
    parser.add_argument("file", type=str, help="Path to a UTF-8 text file.")
    parser.add_argument(
        "-n",
        "--top",
        type=int,
        default=10,
        help="Number of top words to display (default: 10).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argument list (defaults to sys.argv[1:]).

    Returns:
        Process exit code (0 on success, 1 on error).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    results = analyze(text, args.top)

    for word, count in results:
        print(f"{word}\t{count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

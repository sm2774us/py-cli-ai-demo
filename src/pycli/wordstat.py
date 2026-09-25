"""wordstat: a word-frequency CLI tool.

This module provides functions to tokenize, count, and find top words
in text.
"""

from __future__ import annotations

import argparse
import heapq
import re
import sys
from collections import Counter
from pathlib import Path


def tokenize(text: str) -> list[str]:
    """Splits text into lowercase alphabetic words.

    Args:
        text: Raw input text.

    Returns:
        A list of lowercase word tokens.
    """
    return re.findall(r"[a-z]+", text.lower())


def count_words(words: list[str]) -> list[list]:
    """Counts word frequencies using collections.Counter.

    Args:
        words: Tokenized words.

    Returns:
        A list of [word, count] pairs, order of first appearance.
    """
    counts = Counter(words)
    return [[word, count] for word, count in counts.items()]


def top_n_words(counts: list[list], n: int) -> list[list]:
    """Returns the top-n [word, count] pairs by count, descending.

    Args:
        counts: List of [word, count] pairs.
        n: Number of top entries to return.

    Returns:
        Up to n [word, count] pairs sorted by count descending.
    """
    items = [tuple(pair) for pair in counts]
    top_items = heapq.nlargest(n, items, key=lambda kv: kv[1])
    return [[word, count] for word, count in top_items]


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

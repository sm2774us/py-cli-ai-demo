"""Benchmarks pycli.wordstat.analyze on a generated corpus.

Used by the "improve-algorithm" AI workflow to produce an old-vs-new
performance comparison that gets pasted into the PR description.

IMPORTANT: `wordstat.tokenize` keeps only alphabetic characters, so a
vocabulary like "word0".."word9999" would collapse into a single token
("word") after tokenization -- silently defeating `--vocab` entirely.
This generator instead builds distinct alphabetic-only words (bijective
base-26, like spreadsheet column names: a, b, ..., z, aa, ab, ...), so
the requested vocabulary size is the *actual* vocabulary size.

Usage:
    uv run python scripts/benchmark.py [--words 20000] [--vocab 15000]
"""

from __future__ import annotations

import argparse
import random
import time

from pycli import wordstat


def index_to_word(index: int) -> str:
    """Converts a non-negative index to a unique lowercase-letter word.

    Uses bijective base-26 (like spreadsheet column names: a, b, ...,
    z, aa, ab, ...) so every index maps to a distinct all-alphabetic
    string that survives `wordstat.tokenize` unchanged.

    Args:
        index: Zero-based index.

    Returns:
        A unique lowercase string of letters.
    """
    letters: list[str] = []
    n = index + 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters.append(chr(97 + remainder))
    return "".join(reversed(letters))


def make_corpus(word_count: int, vocab_size: int, seed: int = 42) -> str:
    """Builds a synthetic text corpus with a genuinely distinct vocabulary.

    Args:
        word_count: Total number of words to generate.
        vocab_size: Number of distinct words in the vocabulary.
        seed: Random seed for reproducibility.

    Returns:
        A space-separated string of `word_count` words.
    """
    rng = random.Random(seed)
    vocab = [index_to_word(i) for i in range(vocab_size)]
    return " ".join(rng.choice(vocab) for _ in range(word_count))


def run(word_count: int, vocab_size: int, top_n: int = 10) -> float:
    """Times a single analyze() call.

    Args:
        word_count: Corpus size in words.
        vocab_size: Distinct word count.
        top_n: Number of top words requested.

    Returns:
        Elapsed wall-clock seconds.
    """
    text = make_corpus(word_count, vocab_size)
    start = time.perf_counter()
    wordstat.analyze(text, top_n)
    return time.perf_counter() - start


def main() -> None:
    """CLI entry point for the benchmark script."""
    parser = argparse.ArgumentParser(description="Benchmark pycli.wordstat")
    parser.add_argument("--words", type=int, default=20_000)
    parser.add_argument("--vocab", type=int, default=15_000)
    args = parser.parse_args()

    elapsed = run(args.words, args.vocab)
    print(
        f"words={args.words} vocab={args.vocab} "
        f"elapsed_seconds={elapsed:.4f}"
    )


if __name__ == "__main__":
    main()

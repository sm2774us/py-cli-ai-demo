"""Unit tests for pycli.wordstat (targets 100% line coverage)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pycli import wordstat


def test_tokenize_basic() -> None:
    assert wordstat.tokenize("Hello, world! Hello again.") == [
        "hello",
        "world",
        "hello",
        "again",
    ]


def test_tokenize_empty_string() -> None:
    assert wordstat.tokenize("") == []


def test_tokenize_no_trailing_delimiter() -> None:
    assert wordstat.tokenize("abc") == ["abc"]


def test_tokenize_only_delimiters() -> None:
    assert wordstat.tokenize("!!! ,,, ...") == []


def test_count_words_basic() -> None:
    counts = wordstat.count_words(["a", "b", "a", "c", "b", "a"])
    as_dict = {word: n for word, n in counts}
    assert as_dict == {"a": 3, "b": 2, "c": 1}


def test_count_words_empty() -> None:
    assert wordstat.count_words([]) == []


def test_top_n_words_basic() -> None:
    counts = [["a", 3], ["b", 5], ["c", 1]]
    assert wordstat.top_n_words(counts, 2) == [["b", 5], ["a", 3]]


def test_top_n_words_n_larger_than_list() -> None:
    counts = [["a", 1]]
    assert wordstat.top_n_words(counts, 5) == [["a", 1]]


def test_top_n_words_n_zero() -> None:
    counts = [["a", 1]]
    assert wordstat.top_n_words(counts, 0) == []


def test_top_n_words_does_not_mutate_input() -> None:
    counts = [["a", 1], ["b", 2]]
    wordstat.top_n_words(counts, 1)
    assert counts == [["a", 1], ["b", 2]]


def test_analyze_end_to_end() -> None:
    text = "the cat sat on the mat the cat ran"
    result = wordstat.analyze(text, 2)
    assert result == [["the", 3], ["cat", 2]]


def test_build_parser_defaults() -> None:
    parser = wordstat.build_parser()
    args = parser.parse_args(["myfile.txt"])
    assert args.file == "myfile.txt"
    assert args.top == 10


def test_build_parser_custom_top() -> None:
    parser = wordstat.build_parser()
    args = parser.parse_args(["myfile.txt", "-n", "3"])
    assert args.top == 3


def test_main_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("dog dog cat", encoding="utf-8")

    exit_code = wordstat.main([str(file_path), "-n", "2"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "dog\t2" in captured.out
    assert "cat\t1" in captured.out


def test_main_file_not_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "does_not_exist.txt"

    exit_code = wordstat.main([str(missing)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error: file not found" in captured.err


def test_main_module_entrypoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Covers the `if __name__ == "__main__"` guard via runpy."""
    import runpy
    import sys

    file_path = tmp_path / "entry.txt"
    file_path.write_text("x y x", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["wordstat", str(file_path)])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("pycli.wordstat", run_name="__main__")
    assert exc_info.value.code == 0

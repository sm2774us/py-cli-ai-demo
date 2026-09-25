"""Tests for scripts/wrap_comments.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from wrap_comments import wrap_comment_line, wrap_file  # noqa: E402


def test_wrap_comment_line_leaves_short_lines_alone() -> None:
    line = "    # short comment"
    assert wrap_comment_line(line, 80) == [line]


def test_wrap_comment_line_leaves_code_lines_alone() -> None:
    line = "x = 1  # a trailing comment that happens to be quite long here"
    assert wrap_comment_line(line, 40) == [line]


def test_wrap_comment_line_leaves_shebang_alone() -> None:
    line = "#!/usr/bin/env python3 with a very long shebang line right here"
    assert wrap_comment_line(line, 20) == [line]


def test_wrap_comment_line_leaves_double_hash_alone() -> None:
    line = "    ## a section banner that is definitely longer than the limit"
    assert wrap_comment_line(line, 20) == [line]


def test_wrap_comment_line_leaves_empty_comment_alone() -> None:
    line = "    #" + " " * 80
    assert wrap_comment_line(line, 10) == [line]


def test_wrap_comment_line_wraps_long_comment_preserving_indent() -> None:
    line = (
        "    # Sort stably or by count descending, keeping original "
        "order for ties if needed, or just sort descending by count."
    )
    result = wrap_comment_line(line, 80)
    assert len(result) > 1
    for wrapped in result:
        assert len(wrapped) <= 80
        assert wrapped.startswith("    # ")


def test_wrap_file_modifies_and_reports_change(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    long_comment = "# " + "x" * 100
    path.write_text(f"a = 1\n{long_comment}\nb = 2\n", encoding="utf-8")

    changed = wrap_file(str(path), 80)

    assert changed
    new_content = path.read_text(encoding="utf-8")
    assert all(len(line) <= 80 for line in new_content.splitlines())


def test_wrap_file_no_change_when_already_clean(tmp_path: Path) -> None:
    path = tmp_path / "clean.py"
    path.write_text("a = 1\n# short\nb = 2\n", encoding="utf-8")

    changed = wrap_file(str(path), 80)

    assert not changed


def test_main_cli_wraps_given_files(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    import wrap_comments

    path = tmp_path / "cli_sample.py"
    path.write_text("# " + "y" * 100 + "\n", encoding="utf-8")

    monkeypatch.setattr(
        sys, "argv", ["wrap_comments.py", "--max-length", "80", str(path)]
    )
    exit_code = wrap_comments.main()

    assert exit_code == 0
    assert "wrapped long comments" in capsys.readouterr().out

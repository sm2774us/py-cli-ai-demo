"""Tests for scripts/ai_improve.py (no real network calls)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ai_improve  # noqa: E402
from ai_improve import extract_files  # noqa: E402


def test_extract_files_parses_two_blocks() -> None:
    response = (
        "FILE: src/pycli/wordstat.py\n"
        "```python\n"
        "print('a')\n"
        "```\n"
        "FILE: tests/test_wordstat.py\n"
        "```python\n"
        "print('b')\n"
        "```\n"
    )
    result = extract_files(response)
    assert result["src/pycli/wordstat.py"].strip() == "print('a')"
    assert result["tests/test_wordstat.py"].strip() == "print('b')"


def test_extract_files_raises_on_no_match() -> None:
    with pytest.raises(ValueError):
        extract_files("no file blocks here")


def test_write_files_writes_allowed_and_skips_unexpected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    allowed = tmp_path / "allowed.py"
    files = {
        str(allowed): "x = 1",
        "some/other/path.py": "y = 2",
    }

    ai_improve.write_files(files, (str(allowed),))

    assert allowed.read_text(encoding="utf-8") == "x = 1\n"
    assert "ignoring unexpected file" in capsys.readouterr().out


def test_run_command_reports_success_and_failure() -> None:
    ok, output = ai_improve.run_command(
        [sys.executable, "-c", "print('hello')"]
    )
    assert ok
    assert "hello" in output

    ok, output = ai_improve.run_command(
        [sys.executable, "-c", "import sys; sys.exit(1)"]
    )
    assert not ok


def test_measure_benchmark_parses_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ai_improve,
        "run_command",
        lambda cmd: (True, "words=1 vocab=1 elapsed_seconds=0.1234\n"),
    )

    assert ai_improve.measure_benchmark() == pytest.approx(0.1234)


def test_measure_benchmark_raises_on_script_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ai_improve, "run_command", lambda cmd: (False, "boom")
    )

    with pytest.raises(RuntimeError, match="benchmark.py failed"):
        ai_improve.measure_benchmark()


def test_measure_benchmark_raises_on_unparseable_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ai_improve, "run_command", lambda cmd: (True, "garbage output")
    )

    with pytest.raises(RuntimeError, match="could not parse"):
        ai_improve.measure_benchmark()


def test_autofix_and_verify_all_pass_and_faster(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ai_improve.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(ai_improve, "run_command", lambda cmd: (True, ""))
    monkeypatch.setattr(ai_improve, "measure_benchmark", lambda: 0.5)

    passed, error_output = ai_improve.autofix_and_verify(
        "a.py", "b.py", baseline_seconds=1.0
    )

    assert passed
    assert error_output == ""
    assert "2.0x faster" in capsys.readouterr().out


def test_autofix_and_verify_lint_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_improve.subprocess, "run", lambda *a, **k: None)

    def fake_run_command(cmd):  # noqa: ANN001
        if "check" in cmd:
            return False, "lint broke"
        return True, ""

    monkeypatch.setattr(ai_improve, "run_command", fake_run_command)

    passed, error_output = ai_improve.autofix_and_verify(
        "a.py", "b.py", baseline_seconds=1.0
    )

    assert not passed
    assert "ruff check failed" in error_output


def test_autofix_and_verify_test_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_improve.subprocess, "run", lambda *a, **k: None)

    def fake_run_command(cmd):  # noqa: ANN001
        if "pytest" in cmd:
            return False, "tests broke"
        return True, ""

    monkeypatch.setattr(ai_improve, "run_command", fake_run_command)

    passed, error_output = ai_improve.autofix_and_verify(
        "a.py", "b.py", baseline_seconds=1.0
    )

    assert not passed
    assert "pytest failed" in error_output


def test_autofix_and_verify_performance_regression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_improve.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(ai_improve, "run_command", lambda cmd: (True, ""))
    monkeypatch.setattr(ai_improve, "measure_benchmark", lambda: 2.0)

    passed, error_output = ai_improve.autofix_and_verify(
        "a.py", "b.py", baseline_seconds=1.0
    )

    assert not passed
    assert "Performance regression" in error_output
    assert "before=1.0000s after=2.0000s" in error_output


def test_autofix_and_verify_benchmark_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_improve.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(ai_improve, "run_command", lambda cmd: (True, ""))

    def raise_benchmark_error():
        raise RuntimeError("benchmark exploded")

    monkeypatch.setattr(ai_improve, "measure_benchmark", raise_benchmark_error)

    passed, error_output = ai_improve.autofix_and_verify(
        "a.py", "b.py", baseline_seconds=1.0
    )

    assert not passed
    assert "benchmark exploded" in error_output


def test_main_missing_api_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["ai_improve.py", "--instruction", "x", "--file", "a", "--tests", "b"],
    )

    exit_code = ai_improve.main()

    assert exit_code == 1
    assert "GEMINI_API_KEY not set" in capsys.readouterr().err


def test_main_restores_originals_after_exhausted_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_path = tmp_path / "src.py"
    tests_path = tmp_path / "tests.py"
    file_path.write_text("original source\n", encoding="utf-8")
    tests_path.write_text("original tests\n", encoding="utf-8")

    def fake_call_gemini(prompt, api_key):  # noqa: ANN001
        return (
            f"FILE: {file_path}\n```python\nbroken\n```\n"
            f"FILE: {tests_path}\n```python\nbroken\n```\n"
        )

    def fake_autofix_and_verify(*paths, baseline_seconds):  # noqa: ANN001
        return False, "simulated failure"

    monkeypatch.setattr(ai_improve, "call_gemini", fake_call_gemini)
    monkeypatch.setattr(ai_improve, "measure_benchmark", lambda: 1.0)
    monkeypatch.setattr(
        ai_improve, "autofix_and_verify", fake_autofix_and_verify
    )
    monkeypatch.setattr(ai_improve, "MAX_ATTEMPTS", 2)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ai_improve.py",
            "--instruction",
            "x",
            "--file",
            str(file_path),
            "--tests",
            str(tests_path),
        ],
    )

    exit_code = ai_improve.main()

    assert exit_code == 1
    assert file_path.read_text(encoding="utf-8") == "original source\n"
    assert tests_path.read_text(encoding="utf-8") == "original tests\n"


def test_main_succeeds_on_first_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_path = tmp_path / "src.py"
    tests_path = tmp_path / "tests.py"
    file_path.write_text("original source\n", encoding="utf-8")
    tests_path.write_text("original tests\n", encoding="utf-8")

    def fake_call_gemini(prompt, api_key):  # noqa: ANN001
        return (
            f"FILE: {file_path}\n```python\nfixed source\n```\n"
            f"FILE: {tests_path}\n```python\nfixed tests\n```\n"
        )

    def fake_autofix_and_verify(*paths, baseline_seconds):  # noqa: ANN001
        return True, ""

    monkeypatch.setattr(ai_improve, "call_gemini", fake_call_gemini)
    monkeypatch.setattr(ai_improve, "measure_benchmark", lambda: 1.0)
    monkeypatch.setattr(
        ai_improve, "autofix_and_verify", fake_autofix_and_verify
    )
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ai_improve.py",
            "--instruction",
            "x",
            "--file",
            str(file_path),
            "--tests",
            str(tests_path),
        ],
    )

    exit_code = ai_improve.main()

    assert exit_code == 0
    assert file_path.read_text(encoding="utf-8") == "fixed source\n"


def test_main_recovers_after_gemini_call_error_then_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_path = tmp_path / "src.py"
    tests_path = tmp_path / "tests.py"
    file_path.write_text("original source\n", encoding="utf-8")
    tests_path.write_text("original tests\n", encoding="utf-8")

    calls = {"n": 0}

    def fake_call_gemini(prompt, api_key):  # noqa: ANN001
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated API error")
        return (
            f"FILE: {file_path}\n```python\nfixed source\n```\n"
            f"FILE: {tests_path}\n```python\nfixed tests\n```\n"
        )

    def fake_autofix_and_verify(*paths, baseline_seconds):  # noqa: ANN001
        return True, ""

    monkeypatch.setattr(ai_improve, "call_gemini", fake_call_gemini)
    monkeypatch.setattr(ai_improve, "measure_benchmark", lambda: 1.0)
    monkeypatch.setattr(
        ai_improve, "autofix_and_verify", fake_autofix_and_verify
    )
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ai_improve.py",
            "--instruction",
            "x",
            "--file",
            str(file_path),
            "--tests",
            str(tests_path),
        ],
    )

    exit_code = ai_improve.main()

    assert exit_code == 0
    assert calls["n"] == 2

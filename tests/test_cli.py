"""Module 3 tests: the draft command end to end, with the stand-in Claude."""

import json

import pytest

from ai_triage import cli
from conftest import finding, report
from fakes import FakeSDK, api_error, response
from test_checks import GOOD, REPORT


@pytest.fixture
def use_fake(monkeypatch):
    def install(*replies):
        fake = FakeSDK(*replies)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
        monkeypatch.setattr(cli, "make_sdk_client", lambda settings: fake)
        return fake
    return install


def run(folder, *extra):
    return cli.main(["draft", str(folder), *extra])


def test_good_draft_is_saved_next_to_the_report_and_exits_0(write_report, use_fake, capsys):
    folder = write_report(REPORT)
    use_fake(response(GOOD))
    assert run(folder) == 0
    saved = json.loads((folder / "triage.json").read_text(encoding="utf-8"))
    assert saved["status"] == "OK"
    assert saved["draft"] == GOOD
    assert saved["model"] == "claude-haiku-5-5" and saved["prompt_version"] == "p1"
    assert all(c["passed"] for c in saved["checks"])
    assert saved["usage"] == {"input_tokens": 3000, "output_tokens": 800}
    assert saved["cost_usd"] == pytest.approx(3000 / 1e6 * 0.10 + 800 / 1e6 * 0.50)
    note = (folder / "triage.md").read_text(encoding="utf-8")
    assert note.startswith("# Delivery triage note")
    assert "DRAFT: AI-written" in note and "review before acting" in note
    assert "[MISSING-1]" in note
    assert "OK" in capsys.readouterr().out


def test_draft_failing_a_check_is_kept_but_marked_needs_human_and_exits_1(write_report, use_fake):
    folder = write_report(REPORT)
    use_fake(response(dict(GOOD, summary="7 files are missing.")))
    assert run(folder) == 1
    saved = json.loads((folder / "triage.json").read_text(encoding="utf-8"))
    assert saved["status"] == "NEEDS_HUMAN"
    note = (folder / "triage.md").read_text(encoding="utf-8")
    assert "NEEDS HUMAN" in note and "C4" in note and "number 7" in note


def test_api_failure_gives_a_correct_code_written_note_and_exits_2(write_report, use_fake):
    folder = write_report(REPORT)
    use_fake(api_error("connection"))
    assert run(folder) == 2
    saved = json.loads((folder / "triage.json").read_text(encoding="utf-8"))
    assert saved["status"] == "FALLBACK"
    assert "could not reach" in saved["fallback_reason"]
    assert all(c["passed"] for c in saved["checks"])
    assert "FALLBACK: written by code" in (folder / "triage.md").read_text(encoding="utf-8")


def test_no_api_key_falls_back_without_touching_the_network(write_report, monkeypatch):
    folder = write_report(REPORT)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(cli, "make_sdk_client", lambda settings: pytest.fail("network client was created"))
    assert run(folder) == 2
    assert "ANTHROPIC_API_KEY is not set" in json.loads((folder / "triage.json").read_text())["fallback_reason"]


def test_an_earlier_note_is_never_overwritten(write_report, use_fake):
    folder = write_report(REPORT)
    use_fake(response(GOOD), response(GOOD))
    run(folder)
    run(folder)
    assert (folder / "triage.json").exists() and (folder / "triage-2.json").exists()
    assert (folder / "triage.md").exists() and (folder / "triage-2.md").exists()


def test_missing_report_is_a_tool_error_exit_3(tmp_path, capsys):
    assert run(tmp_path / "nothing_here") == 3
    assert "not found" in capsys.readouterr().err


def test_the_api_key_never_appears_in_any_output(write_report, use_fake, capsys):
    folder = write_report(report(findings=[finding("MISSING", "ERROR", "a")]))
    use_fake(api_error("auth"))
    run(folder)
    written = (folder / "triage.json").read_text() + (folder / "triage.md").read_text()
    captured = capsys.readouterr()
    assert "sk-ant-test-not-real" not in written + captured.out + captured.err

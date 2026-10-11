"""Module 4 tests: the harness, with the stand-in Claude or the free dry-run. No real API calls."""

import csv
import json
from pathlib import Path

import pytest

from ai_triage import cli
from ai_triage.eval import CostLimitError, EvalError, run_eval
from ai_triage.settings import load_settings
from conftest import report
from fakes import FakeSDK, api_error, response
from test_checks import GOOD, REPORT

REAL_CASES = Path(__file__).resolve().parents[1] / "cases"


def make_cases(tmp_path, *reports):
    root = tmp_path / "cases"
    for i, data in enumerate(reports, 1):
        folder = root / f"{i:02d}-case{i}"
        folder.mkdir(parents=True)
        (folder / "report.json").write_text(json.dumps(data), encoding="utf-8")
        (folder / "case.toml").write_text(f'title = "case{i}"\npurpose = "test"\n', encoding="utf-8")
    return root


def run(tmp_path, cases, repeats=3, sdk=None, dry_run=False, max_cost=None):
    settings = load_settings(None)
    return run_eval(cases, settings, repeats=repeats, sdk_client=sdk, dry_run=dry_run,
                    max_cost_usd=max_cost, runs_dir=tmp_path / "runs")


def test_mixed_answers_give_an_honest_pass_rate(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    cases = make_cases(tmp_path, REPORT)
    bad = dict(GOOD, summary="7 files are missing.")
    summary = run(tmp_path, cases, sdk=FakeSDK(response(GOOD), response(bad), api_error("connection")))
    assert (summary.calls, summary.answered, summary.passed) == (3, 2, 1)
    assert summary.pass_rate == pytest.approx(1 / 3)
    assert summary.api_failures == 1
    assert summary.per_check["C4"] == (1, 2)          # passed in 1 of the 2 answers that came back
    assert summary.per_check["C2"] == (2, 2)
    assert summary.per_case["case1"] == (1, 3)
    assert summary.input_tokens == 6000 and summary.output_tokens == 1600
    assert summary.cost_usd == pytest.approx(2 * (3000 / 1e6 * 0.10 + 800 / 1e6 * 0.50))


def test_every_run_is_recorded_with_model_prompt_version_pass_rate_and_cost(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    cases = make_cases(tmp_path, REPORT)
    summary = run(tmp_path, cases, repeats=1, sdk=FakeSDK(response(GOOD)))
    with open(tmp_path / "runs" / "history.csv", encoding="utf-8") as handle:
        [row] = list(csv.DictReader(handle))
    assert row["model"] == "claude-haiku-5-5" and row["prompt_version"] == "p1"
    assert row["mode"] == "live" and row["calls"] == "1" and row["pass_rate"] == "1.000"
    text = (summary.folder / "summary.md").read_text(encoding="utf-8")
    assert "Pass rate: 100.0%" in text and "claude-haiku-5-5" in text and "p1" in text
    raw = (tmp_path / "runs" / "raw" / f"{summary.folder.name}.jsonl").read_text(encoding="utf-8")
    assert json.loads(raw.splitlines()[0])["answer"] == GOOD


def test_failures_are_listed_with_their_reasons(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    cases = make_cases(tmp_path, REPORT)
    summary = run(tmp_path, cases, repeats=1, sdk=FakeSDK(response(dict(GOOD, result="CLEAN"))))
    text = (summary.folder / "summary.md").read_text(encoding="utf-8")
    assert "case1 (repeat 1): C2" in text and "result is 'CLEAN'" in text


def test_cost_guard_stops_before_any_call(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    sdk = FakeSDK()
    with pytest.raises(CostLimitError, match="estimated"):
        run(tmp_path, make_cases(tmp_path, REPORT), sdk=sdk, max_cost=0.000001)
    assert sdk.requests == []


def test_a_real_run_without_a_key_says_how_to_run_for_free(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(EvalError, match="--dry-run"):
        run(tmp_path, make_cases(tmp_path, REPORT))


def test_dry_run_is_free_and_never_touches_the_network(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "make_sdk_client", lambda settings: pytest.fail("network client was created"))
    summary = run(tmp_path, make_cases(tmp_path, REPORT, report(result="CLEAN")), dry_run=True)
    assert (summary.calls, summary.passed, summary.cost_usd) == (6, 6, 0)
    assert summary.mode == "dry-run"
    # No AI was used, so no model may be credited with the result.
    assert summary.model == "none (code fallback)"
    assert "claude" not in (summary.folder / "summary.md").read_text(encoding="utf-8").lower()


def test_dry_run_on_all_20_real_cases_passes_every_check(tmp_path):
    # Proves the cases are usable and the code-written fallback is valid on every one of them.
    summary = run(tmp_path, REAL_CASES, repeats=1, dry_run=True)
    assert summary.calls == 20 and summary.pass_rate == 1.0, summary.failures


def test_eval_command_exit_codes(tmp_path, monkeypatch, capsys):
    cases = make_cases(tmp_path, REPORT)
    runs = str(tmp_path / "runs")
    assert cli.main(["eval", "--cases", str(cases), "--runs", runs, "--dry-run"]) == 0
    assert "Pass rate: 100.0%" in capsys.readouterr().out
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert cli.main(["eval", "--cases", str(cases), "--runs", runs]) == 3

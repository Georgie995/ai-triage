"""Module 4: the harness. Every case is sent to the model several times, every answer is checked,
and the pass rate is reported and recorded, with the model, prompt version and cost.

    python -m ai_triage eval [--repeats 3] [--dry-run]

--dry-run uses the code-written fallback instead of the AI: free, offline, and a check that
the cases and the harness itself work.
"""

import csv
import json
import os
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .checks import CHECK_NAMES, all_passed, run_checks
from .claude_client import ClaudeClient, ModelReply
from .facts import applicable_playbook, build_fact_sheet, load_playbook, load_report
from .fallback import build_fallback
from .prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_user_message
from .settings import cost_usd

# Assumptions for the cost estimate made BEFORE a run (the real cost is measured after).
CHARS_PER_TOKEN = 3            # deliberately pessimistic: real text is usually ~4 characters per token
OUTPUT_TOKENS_PER_CALL = 2000  # answer plus thinking; generous on purpose

HISTORY_COLUMNS = ["run", "date", "mode", "model", "effort", "prompt_version", "cases", "repeats", "calls",
                   "answered", "passed", "pass_rate", "api_failures", "input_tokens", "output_tokens", "cost_usd"]


class EvalError(Exception):
    """The harness can't run (exit code 3)."""


class CostLimitError(EvalError):
    """The estimated cost is over the limit; nothing was sent."""


@dataclass
class Summary:
    folder: Path
    mode: str
    model: str
    effort: str
    cases: int
    repeats: int
    estimated_cost_usd: float
    calls: int = 0
    answered: int = 0
    passed: int = 0
    api_failures: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    per_check: dict = field(default_factory=dict)   # check id -> (passed, answered)
    per_case: dict = field(default_factory=dict)    # case title -> (passed, repeats)
    failures: list = field(default_factory=list)

    @property
    def pass_rate(self):
        return self.passed / self.calls if self.calls else 0.0


def run_eval(cases_dir, settings, repeats=3, sdk_client=None, dry_run=False, max_cost_usd=None, runs_dir="runs"):
    cases = _load_cases(Path(cases_dir), load_playbook(settings["playbook"]))
    calls = len(cases) * repeats
    estimate = sum((len(SYSTEM_PROMPT) + len(c["message"])) / CHARS_PER_TOKEN for c in cases) * repeats
    estimated = 0.0 if dry_run else cost_usd({"input_tokens": estimate,
                                               "output_tokens": OUTPUT_TOKENS_PER_CALL * calls}, settings)
    limit = settings["max_run_cost_usd"] if max_cost_usd is None else max_cost_usd
    if estimated > limit:
        raise CostLimitError(f"estimated cost ${estimated:.4f} for {calls} calls is over the limit "
                             f"${limit:.4f}; nothing was sent (raise --max-cost to allow it)")
    if not dry_run and sdk_client is None and not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        raise EvalError("a real run needs ANTHROPIC_API_KEY. For a free run without the AI, use --dry-run")

    client = None if dry_run else ClaudeClient(settings["model"], settings["effort"],
                                              settings["timeout_seconds"], sdk_client=sdk_client)
    folder, raw_path = _new_run_folder(Path(runs_dir))
    summary = Summary(folder, "dry-run" if dry_run else "live", settings["model"], settings["effort"],
                      len(cases), repeats, estimated, per_check={c: (0, 0) for c in CHECK_NAMES})

    with open(raw_path, "w", encoding="utf-8") as raw:
        for case in cases:
            case_passed = 0
            for repeat in range(1, repeats + 1):
                if dry_run:
                    reply = ModelReply(True, build_fallback(case["facts"], case["entries"]), None)
                else:
                    reply = client.draft(SYSTEM_PROMPT, case["message"])
                ok = _score(summary, case, repeat, reply, settings, raw)
                case_passed += ok
            summary.per_case[case["title"]] = (case_passed, repeats)

    _write_summary(summary)
    _append_history(Path(runs_dir) / "history.csv", summary)
    return summary


def _load_cases(cases_dir, playbook):
    folders = sorted(p for p in cases_dir.iterdir() if (p / "report.json").exists()) if cases_dir.exists() else []
    if not folders:
        raise EvalError(f"no cases found in {cases_dir}")
    cases = []
    for folder in folders:
        meta = tomllib.loads((folder / "case.toml").read_text(encoding="utf-8")) if (folder / "case.toml").exists() else {}
        facts = build_fact_sheet(load_report(folder))
        entries = applicable_playbook(facts, playbook)
        cases.append({"title": meta.get("title", folder.name), "facts": facts, "entries": entries,
                      "message": build_user_message(facts, entries)})
    return cases


def _score(summary, case, repeat, reply, settings, raw):
    summary.calls += 1
    summary.input_tokens += reply.usage["input_tokens"]
    summary.output_tokens += reply.usage["output_tokens"]
    summary.cost_usd += cost_usd(reply.usage, settings)
    record = {"case": case["title"], "repeat": repeat, "ok": reply.ok, "error": reply.error,
              "answer": reply.answer, "usage": reply.usage, "request_id": reply.request_id}
    passed = False
    if not reply.ok:
        summary.api_failures += 1
        summary.failures.append(f"{case['title']} (repeat {repeat}): no usable answer: {reply.error}")
    else:
        summary.answered += 1
        results = run_checks(reply.answer, case["facts"], case["entries"])
        for r in results:
            ok_count, total = summary.per_check[r.id]
            summary.per_check[r.id] = (ok_count + r.passed, total + 1)
            if not r.passed:
                summary.failures.append(f"{case['title']} (repeat {repeat}): {r.id} {r.name}: "
                                        f"{'; '.join(r.problems)}")
        passed = all_passed(results)
        summary.passed += passed
        record["checks"] = {r.id: r.passed for r in results}
    raw.write(json.dumps(record, ensure_ascii=False) + "\n")
    return passed


def _new_run_folder(runs_dir):
    stamp = datetime.now().strftime("eval-%Y-%m-%d_%H%M%S")
    n, name = 1, stamp
    while (runs_dir / name).exists():
        n += 1
        name = f"{stamp}-{n}"
    (runs_dir / name).mkdir(parents=True)
    (runs_dir / "raw").mkdir(exist_ok=True)
    return runs_dir / name, runs_dir / "raw" / f"{name}.jsonl"


def _write_summary(s):
    lines = [
        f"# Harness run {s.folder.name}",
        "",
        f"- Mode: {s.mode}" + (" (code-written fallback, no AI)" if s.mode == "dry-run" else ""),
        f"- Model: {s.model} · effort {s.effort} · prompt {PROMPT_VERSION}",
        f"- Cases × repeats: {s.cases} × {s.repeats} = {s.calls} calls",
        f"- **Pass rate: {s.pass_rate * 100:.1f}%** ({s.passed} of {s.calls} answers passed all 9 checks)",
        f"- No usable answer (API problem, refusal, broken reply): {s.api_failures}",
        f"- Tokens: {s.input_tokens} in, {s.output_tokens} out · cost ${s.cost_usd:.4f} "
        f"(estimated beforehand: ${s.estimated_cost_usd:.4f})",
        "",
        "## Per check (answers that came back)",
        "",
        "| Check | Passed |",
        "|---|---|",
        *(f"| {cid} {CHECK_NAMES[cid]} | {ok} / {total} |" for cid, (ok, total) in s.per_check.items()),
        "",
        "## Per case",
        "",
        "| Case | Passed |",
        "|---|---|",
        *(f"| {title} | {ok} / {total} |" for title, (ok, total) in s.per_case.items()),
        "",
        "## Failures",
        "",
        *([f"- {f}" for f in s.failures] or ["None."]),
    ]
    text = "\n".join(lines) + "\n"
    (s.folder / "summary.md").write_text(text, encoding="utf-8")
    print(text)


def _append_history(path, s):
    new = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow({"run": s.folder.name, "date": datetime.now().astimezone().isoformat(timespec="seconds"),
                         "mode": s.mode, "model": s.model, "effort": s.effort, "prompt_version": PROMPT_VERSION,
                         "cases": s.cases, "repeats": s.repeats, "calls": s.calls, "answered": s.answered,
                         "passed": s.passed, "pass_rate": f"{s.pass_rate:.3f}", "api_failures": s.api_failures,
                         "input_tokens": s.input_tokens, "output_tokens": s.output_tokens,
                         "cost_usd": f"{s.cost_usd:.6f}"})

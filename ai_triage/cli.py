"""The command line.

    python -m ai_triage draft <report folder or report.json>

Exit codes: 0 draft passed every check · 1 NEEDS_HUMAN · 2 FALLBACK (AI not usable) ·
3 the tool couldn't run (no report, bad settings or playbook).
"""

import argparse
import os
import sys
from pathlib import Path

import anthropic

from .checks import all_passed, run_checks
from .claude_client import ClaudeClient
from .facts import PlaybookError, ReportError, applicable_playbook, build_fact_sheet, load_playbook, load_report
from .fallback import build_fallback
from .output import save
from .prompt import SYSTEM_PROMPT, build_user_message
from .settings import SettingsError, cost_usd, load_settings

EXIT = {"OK": 0, "NEEDS_HUMAN": 1, "FALLBACK": 2}


def make_sdk_client(settings):
    """The real SDK client. Tests replace this function with a stand-in."""
    return anthropic.Anthropic(timeout=settings["timeout_seconds"], max_retries=2)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    args = _parser().parse_args(argv)
    try:
        settings = load_settings(args.config)
        return _draft(args.report, settings)
    except (SettingsError, ReportError, PlaybookError) as error:
        print(f"ai-triage: error: {error}", file=sys.stderr)
        return 3


def _parser():
    parser = argparse.ArgumentParser(prog="ai-triage", description="Draft and check a triage note for a report.")
    parser.add_argument("--config", default="ai-triage.toml", help="settings file (optional)")
    commands = parser.add_subparsers(dest="command", required=True)
    draft = commands.add_parser("draft", help="write a checked triage note next to report.json")
    draft.add_argument("report", help="manifest-doctor report folder (or its report.json)")
    return parser


def _draft(report_path, settings):
    report = load_report(report_path)
    facts = build_fact_sheet(report)
    entries = applicable_playbook(facts, load_playbook(settings["playbook"]))

    sdk = make_sdk_client(settings) if os.environ.get("ANTHROPIC_API_KEY", "").strip() else None
    client = ClaudeClient(settings["model"], settings["effort"], settings["timeout_seconds"], sdk_client=sdk)
    reply = client.draft(SYSTEM_PROMPT, build_user_message(facts, entries))

    if reply.ok:
        draft, fallback_reason = reply.answer, None
        checks = run_checks(draft, facts, entries)
        status = "OK" if all_passed(checks) else "NEEDS_HUMAN"
    else:
        draft, fallback_reason = build_fallback(facts, entries), reply.error
        checks = run_checks(draft, facts, entries)
        status = "FALLBACK" if all_passed(checks) else "NEEDS_HUMAN"  # belt and braces

    folder = Path(report_path)
    if folder.suffix == ".json":
        folder = folder.parent  # the report file was given: save next to it
    note = save(folder, status, draft, checks, settings, reply.usage, cost_usd(reply.usage, settings),
                fallback_reason, report["header"].get("run_at"))
    print(f"{status}: triage note saved to {note}")
    if fallback_reason:
        print(f"  (AI not used: {fallback_reason})")
    for c in checks:
        if not c.passed:
            print(f"  FAILED {c.id} {c.name}: {'; '.join(c.problems)}")
    return EXIT[status]

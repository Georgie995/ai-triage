"""Save triage.json (for automation) and triage.md (for people) next to report.json.

An earlier note is never overwritten: a second run writes triage-2.json / triage-2.md.
"""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .prompt import PROMPT_VERSION

BANNERS = {
    "OK": "DRAFT: AI-written ({model}, prompt {prompt}) and checked against the report: all 9 checks "
          "passed. This is a draft; review before acting.",
    "NEEDS_HUMAN": "NEEDS HUMAN: this AI-written draft FAILED automatic checks against the report. "
                   "Do not rely on it; read the report itself.",
    "FALLBACK": "FALLBACK: written by code from the report, because the AI could not be used ({reason}).",
}


def save(report_folder, status, draft, checks, settings, usage, cost, fallback_reason, report_run_at):
    folder = Path(report_folder)
    stem = _free_stem(folder)
    record = {
        "status": status,
        "draft": draft,
        "checks": [asdict(c) for c in checks],
        "fallback_reason": fallback_reason,
        "model": settings["model"],
        "effort": settings["effort"],
        "prompt_version": PROMPT_VERSION,
        "usage": usage,
        "cost_usd": cost,
        "report_run_at": report_run_at,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    (folder / f"{stem}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    (folder / f"{stem}.md").write_text(_markdown(record), encoding="utf-8")
    return folder / f"{stem}.md"


def _free_stem(folder):
    n = 1
    while True:
        stem = "triage" if n == 1 else f"triage-{n}"
        if not (folder / f"{stem}.json").exists() and not (folder / f"{stem}.md").exists():
            return stem
        n += 1


def _markdown(record):
    draft = record["draft"]
    banner = BANNERS[record["status"]].format(model=record["model"], prompt=record["prompt_version"],
                                              reason=record["fallback_reason"])
    lines = ["# Delivery triage note", "", f"> {banner}", ""]
    failed = [c for c in record["checks"] if not c["passed"]]
    if failed:
        lines += ["**Failed checks:**", ""]
        lines += [f"- {c['id']} {c['name']}: {'; '.join(c['problems'])}" for c in failed]
        lines.append("")
    lines += [f"**Result:** {draft['result']}", "", "## Summary", "", draft["summary"], "", "## Findings", ""]
    lines += [f"- **{f['severity']} · {f['code']} ({f['count']}):** {f['explanation']}" for f in draft["findings"]]
    if not draft["findings"]:
        lines.append("None.")
    lines += ["", "## Next checks (from the playbook)", ""]
    lines += [f"- [{c['playbook_id']}] {c['wording']}" for c in draft["next_checks"]] or ["None."]
    lines += ["", "## What this report doesn't tell us", ""]
    lines += [f"- {u}" for u in draft["unknowns"]] or ["Nothing noted."]
    return "\n".join(lines) + "\n"

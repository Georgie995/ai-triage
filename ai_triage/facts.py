"""Module 1: everything that can be computed is computed here, by code, not by the model.

report.json (from manifest-doctor) -> fact sheet: result, counts, findings grouped by code
with their true counts, causes, and a few example file names. Plus the playbook entries
that apply. The model later only puts these facts into words.
"""

import json
import tomllib
from pathlib import Path

SEVERITY_ORDER = {"ERROR": 0, "WARNING": 1, "INFO": 2}
MAX_EXAMPLES = 10  # configurable default: example files per code sent to the model; counts stay exact


class ReportError(Exception):
    """The report can't be used. The tool stops (exit code 3)."""


class PlaybookError(Exception):
    """The playbook file is wrong. The tool stops (exit code 3)."""


def load_report(path):
    path = Path(path)
    if path.is_dir():
        path = path / "report.json"
    if not path.exists():
        raise ReportError(f"{path} not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise ReportError(f"{path} is not valid JSON ({error})") from error
    header = data.get("header", {}) if isinstance(data, dict) else {}
    if header.get("tool") != "manifest-doctor" or "findings" not in data or "causes" not in data:
        raise ReportError(f"{path} is not a manifest-doctor report.json")
    return data


def build_fact_sheet(report, max_examples=MAX_EXAMPLES):
    header = report["header"]
    groups = {}
    for f in report["findings"]:
        group = groups.setdefault(f["code"], {"code": f["code"], "severity": f["severity"], "items": []})
        if SEVERITY_ORDER[f["severity"]] < SEVERITY_ORDER[group["severity"]]:
            group["severity"] = f["severity"]  # mixed severities: keep the most serious
        group["items"].append(_where(f))

    findings = [{"code": g["code"], "severity": g["severity"], "count": len(g["items"]),
                 **_examples(g["items"], max_examples)} for g in groups.values()]
    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], -f["count"], f["code"]))

    causes = [{"code": c["code"], "severity": c["severity"], "summary": c["summary"],
               "file_count": len(c["paths"]), **_examples(c["paths"], max_examples)}
              for c in report["causes"]]
    return {"result": header["result"], "folder_checked": header.get("tree"),
            "counts": header["counts"], "findings": findings, "causes": causes}


def _where(finding):
    if finding.get("path") is not None:
        return finding["path"]
    # Manifest-line problems have no file path. Use the manifest's name, never a local folder path.
    return f"{Path(str(finding.get('manifest') or 'manifest')).name} line {finding.get('line')}"


def _examples(items, limit):
    shown = list(dict.fromkeys(items))[:limit]
    return {"examples": shown, "not_shown": len(items) - len(shown)}


def load_playbook(path):
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise PlaybookError(f"playbook {path} can't be read: {error}") from error
    playbook, seen = {}, set()
    for code, section in data.items():
        entries = section.get("checks", []) if isinstance(section, dict) else []
        for entry in entries:
            if not entry.get("id") or not entry.get("text"):
                raise PlaybookError(f"playbook entry under [{code}] needs both id and text")
            if entry["id"] in seen:
                raise PlaybookError(f"playbook id {entry['id']} is used more than once")
            seen.add(entry["id"])
        playbook[code] = [{"id": e["id"], "text": e["text"]} for e in entries]
    return playbook


def applicable_playbook(fact_sheet, playbook):
    """Playbook entries for the problems in this report: findings first (most serious first), then causes."""
    codes = [f["code"] for f in fact_sheet["findings"]] + [c["code"] for c in fact_sheet["causes"]]
    picked = []
    for code in dict.fromkeys(codes):
        picked += [{"id": e["id"], "for": code, "text": e["text"]} for e in playbook.get(code, [])]
    return picked

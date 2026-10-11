"""Shared helpers: build manifest-doctor-style reports in memory."""

import json

import pytest


def finding(code, severity, path=None, **extra):
    return {"code": code, "severity": severity, "path": path, "detail": "", "manifest": "m.md5",
            "line": extra.pop("line", None), "expected_hash": None, "actual_hash": None, "size": None,
            "proposed_name": None, **extra}


def report(result="PROBLEMS FOUND", findings=(), causes=(), tree="D:/Incoming/ShowA"):
    findings = list(findings)
    counts = {level: sum(f["severity"] == level for f in findings) for level in ("ERROR", "WARNING", "INFO")}
    return {"header": {"tool": "manifest-doctor", "version": "0.1.0", "run_at": "2026-10-11T18:32:05+01:00",
                       "tree": tree, "result": result, "exit_code": 1 if counts["ERROR"] else 0,
                       "counts": counts, "manifests": [{"path": "C:/x/m.md5", "format": "md5sum",
                                                        "entries": 9, "stripped_prefix": None}]},
            "causes": list(causes), "findings": findings}


def cause(code, severity, paths, summary="summary"):
    return {"code": code, "severity": severity, "summary": summary, "paths": list(paths),
            "note": "Probable cause, not a verdict."}


@pytest.fixture
def write_report(tmp_path):
    def write(data, name="report-2026-10-11_183205"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "report.json").write_text(json.dumps(data), encoding="utf-8")
        return folder
    return write

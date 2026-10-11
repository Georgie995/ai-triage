"""Module 2: the nine checks every AI-written draft must pass, compared with the fact sheet.

They run on every real draft (a failure makes it NEEDS_HUMAN) and in the harness (a failure
lowers the pass rate). Each one is proven by a deliberately bad answer in tests/test_checks.py.
"""

import json
import re
import unicodedata
from dataclasses import dataclass, field

from .facts import SEVERITY_ORDER
from .prompt import OUTPUT_SCHEMA

CHECK_NAMES = {
    "C1": "Format",
    "C2": "Same result",
    "C3": "Nothing critical dropped",
    "C4": "Nothing invented",
    "C5": "No changed severity",
    "C6": "Counts match",
    "C7": "Order",
    "C8": "Next checks from the playbook only",
    "C9": "Says what it can't tell",
}

# Words the model may use in capitals without them being "invented codes".
_ALWAYS_OK_CAPS = {"ERROR", "WARNING", "INFO", "CLEAN", "PASSED", "WITH", "WARNINGS", "PROBLEMS", "FOUND"}
# File names the model may mention without them being in the report.
_ALWAYS_OK_FILES = {"report.json", "report.csv", "summary.md"}

_NUMBER = re.compile(r"\b\d+\b")                              # "7 files": not digits inside names like clip_0003
_CAPS = re.compile(r"\b[A-Z][A-Z_]{3,}\b")                     # codes such as HASH_MISMATCH
_PATH = re.compile(r"[^\s'\"`,;:()]+/[^\s'\"`,;:()]+")         # anything with a folder separator
_FILE = re.compile(r"[\w\-]+\.[A-Za-z][A-Za-z0-9]{1,4}\b")     # name.ext


@dataclass
class CheckResult:
    id: str
    name: str
    passed: bool
    problems: list = field(default_factory=list)


def all_passed(results):
    return all(r.passed for r in results)


def run_checks(answer, fact_sheet, playbook_entries):
    format_problems = _validate(answer, OUTPUT_SCHEMA, "answer")
    results = [_result("C1", format_problems)]
    if format_problems:
        # The other checks can't safely read a malformed answer: they count as failed.
        return results + [_result(c, ["not run: the answer is not in the required format"])
                          for c in list(CHECK_NAMES)[1:]]

    facts = {f["code"]: f for f in fact_sheet["findings"]}
    answered = answer["findings"]
    return results + [
        _result("C2", _same_result(answer, fact_sheet)),
        _result("C3", _nothing_dropped(answered, facts)),
        _result("C4", _nothing_invented(answer, fact_sheet, playbook_entries, facts)),
        _result("C5", _severities(answered, facts)),
        _result("C6", _counts(answered, facts)),
        _result("C7", _order(answered)),
        _result("C8", _playbook_only(answer["next_checks"], playbook_entries)),
        _result("C9", _says_what_it_cannot_tell(answer, fact_sheet)),
    ]


def _result(check_id, problems):
    return CheckResult(check_id, CHECK_NAMES[check_id], not problems, problems)


# --- C1: our own small format validator -------------------------------------------------

def _validate(value, schema, where):
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            return [f"{where} should be an object"]
        problems = [f"{where} is missing '{k}'" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            problems += [f"{where} has unexpected field '{k}'" for k in value if k not in schema["properties"]]
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                problems += _validate(value[key], sub, f"{where}.{key}")
        return problems
    if kind == "array":
        if not isinstance(value, list):
            return [f"{where} should be a list"]
        return [p for i, item in enumerate(value) for p in _validate(item, schema["items"], f"{where}[{i}]")]
    if kind == "string" and not isinstance(value, str):
        return [f"{where} should be text"]
    if kind == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return [f"{where} should be a whole number"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{where} is {value!r}, not one of {schema['enum']}"]
    return []


# --- C2 to C9 ----------------------------------------------------------------------

def _same_result(answer, fact_sheet):
    if answer["result"] != fact_sheet["result"]:
        return [f"result is {answer['result']!r} but the report says {fact_sheet['result']!r}"]
    return []


def _nothing_dropped(answered, facts):
    present = {f["code"] for f in answered}
    return [f"ERROR finding {code} ({f['count']}) is missing from the draft"
            for code, f in facts.items() if f["severity"] == "ERROR" and code not in present]


def _nothing_invented(answer, fact_sheet, playbook_entries, facts):
    problems = [f"finding code {f['code']} is not in the report" for f in answer["findings"] if f["code"] not in facts]

    corpus = _nfc(json.dumps(fact_sheet, ensure_ascii=False) + " " + " ".join(e["text"] for e in playbook_entries))
    allowed_numbers = set(_NUMBER.findall(corpus))
    allowed_caps = set(_CAPS.findall(corpus)) | _ALWAYS_OK_CAPS

    for where, text in _texts(answer):
        text = _nfc(text)
        for number in _NUMBER.findall(text):
            if number not in allowed_numbers:
                problems.append(f"{where} mentions the number {number}, which is not in the report")
        for word in _CAPS.findall(text):
            if word not in allowed_caps:
                problems.append(f"{where} mentions {word}, which is not a code or word in the report")
        for name in _PATH.findall(text) + _FILE.findall(text):
            if name not in corpus and name not in _ALWAYS_OK_FILES:
                problems.append(f"{where} mentions {name!r}, which is not in the report")
    return problems


def _severities(answered, facts):
    problems = []
    for f in answered:
        expected = facts.get(f["code"])
        if expected and f["severity"] != expected["severity"]:
            softer = SEVERITY_ORDER[f["severity"]] > SEVERITY_ORDER[expected["severity"]]
            problems.append(f"{f['code']} is {f['severity']} but the report says {expected['severity']}"
                            + (" (softened)" if softer else " (made more serious)"))
    return problems


def _counts(answered, facts):
    return [f"{f['code']} count is {f['count']} but the report says {facts[f['code']]['count']}"
            for f in answered if f["code"] in facts and f["count"] != facts[f["code"]]["count"]]


def _order(answered):
    ranks = [SEVERITY_ORDER[f["severity"]] for f in answered]
    return [] if ranks == sorted(ranks) else ["findings are not ordered ERROR, then WARNING, then INFO"]


def _playbook_only(next_checks, playbook_entries):
    allowed = {e["id"] for e in playbook_entries}
    problems = [f"next check {c['playbook_id']!r} is not a playbook entry for this report"
                for c in next_checks if c["playbook_id"] not in allowed]
    problems += [f"next check {c['playbook_id']!r} has no wording" for c in next_checks if not c["wording"].strip()]
    return problems


def _says_what_it_cannot_tell(answer, fact_sheet):
    if fact_sheet["findings"] and not any(u.strip() for u in answer["unknowns"]):
        return ["'unknowns' is empty although the report has findings"]
    return []


def _texts(answer):
    yield "summary", answer["summary"]
    for i, f in enumerate(answer["findings"]):
        yield f"findings[{i}].explanation", f["explanation"]
    for i, c in enumerate(answer["next_checks"]):
        yield f"next_checks[{i}].wording", c["wording"]
    for i, u in enumerate(answer["unknowns"]):
        yield f"unknowns[{i}]", u


def _nfc(text):
    # Compare Mac-style and Windows-style accented names as the same text.
    return unicodedata.normalize("NFC", text)

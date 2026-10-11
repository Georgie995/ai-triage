"""Module 3: a plain note written by code alone, from the fact sheet and playbook.

Used when the model can't be used. It's less readable, but never wrong, and it passes every check.
"""

# What each finding code means, in manifest-doctor's own terms (see its docs/DESIGN.md).
MEANING = {
    "MISSING": "listed in the manifest but not found on disk",
    "EXTRA": "on disk but not listed in any manifest",
    "HASH_MISMATCH": "checksum or size different from the manifest",
    "ZERO_BYTE": "empty (zero bytes)",
    "DUPLICATE_ENTRY": "listed more than once in a manifest with different checksums",
    "DUPLICATE_SAME_HASH": "listed twice with the same checksum (harmless)",
    "CROSS_SET_CONFLICT": "given different checksums in different manifests",
    "UNREADABLE": "could not be read",
    "MANIFEST_LINE_UNREADABLE": "a manifest line that could not be understood",
    "UNICODE_ONLY_MATCH": "matched only after ignoring how accented letters are stored",
    "CASE_ONLY_MATCH": "matched only after ignoring upper and lower case",
    "PREFIX_OFFSET_MATCH": "matched only after ignoring an extra folder",
    "NAME_HYGIENE": "a name with characters or spacing that can cause problems",
    "ABSOLUTE_PATHS_DETECTED": "manifest paths written as full paths from another computer",
    "HIDDEN_FILE": "a system file set aside",
}

def _n(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


UNKNOWN_LINE ="The report shows what differs, not why it happened or which version is the intended one."


def build_fallback(fact_sheet, playbook_entries):
    counts, findings = fact_sheet["counts"], fact_sheet["findings"]
    if not findings:
        summary = "The delivery check is clean: every listed file was found and matched."
    else:
        top = findings[0]
        summary = (f"{fact_sheet['result']}: {_n(counts['ERROR'], 'error')}, {_n(counts['WARNING'], 'warning')} "
                   f"and {_n(counts['INFO'], 'info finding')}. The most serious is {top['code']} "
                   f"({top['count']} affected).")
    return {
        "summary": summary,
        "result": fact_sheet["result"],
        "findings": [{"code": f["code"], "severity": f["severity"], "count": f["count"],
                      "explanation": f"{f['count']} affected: {MEANING.get(f['code'], 'see the report')}."}
                     for f in findings],
        "next_checks": [{"playbook_id": e["id"], "wording": e["text"]} for e in playbook_entries],
        "unknowns": [UNKNOWN_LINE] if findings else [],
    }

# Decisions

Each entry records the decision, the alternatives considered and why this one was chosen.

## 2026-10-11: Model is Claude Haiku 5.5

- **Decision:** `claude-haiku-5-5`.
- **Alternatives:** Opus 5.5 (Anthropic's default, about $0.55–0.90 per 20-case run), Sonnet 5.5 (about half that).
- **Why:** Georgi's choice. It's the cheapest (about 2–3 cents per run, $0.10 / $0.50 per million tokens for prompts up to 100K tokens; Anthropic pricing as cached 2026-10-06). The harness will show exactly where it falls short.

## 2026-10-11: Budget £5 per month

- **Decision:** a £5 monthly cap, set in Georgi's Anthropic account.
- **Plus:** a per-run cost limit in the tool (default £0.25) that stops a harness run *before* it starts if the estimate is higher.

## 2026-10-11: Official Anthropic SDK

- **Decision:** the official Python SDK.
- **Alternatives:** the standard library's HTTP client.
- **Why:** Georgi's choice. It already handles retries, timeouts, structured output and typed errors, so there's less hand-written code to defend. It's one dependency, installed only after Georgi approves what it brings in.

## 2026-10-11: Standalone first

- **Decision:** ai-triage reads any manifest-doctor `report.json`.
- **Why:** Georgi's choice. Linking it into delivery-ops-hub's alerts is an optional later step.

## 2026-10-11: Next checks come from Georgi's playbook

- **Decision:** code picks the playbook entries for the problems present, and the model only words them.
- **Alternatives:** the model suggests freely.
- **Why:** Georgi's choice. The suggestions carry his operational knowledge, and invented advice is impossible because every suggestion has an ID that's checked.

## 2026-10-11: Every harness case runs 3 times

- **Why:** Haiku 5.5 rejects "temperature 0" (Anthropic migration notes), so answers vary between runs. An answer that's right only some of the time must show up as a lower pass rate. 3 runs was Georgi's choice; 5 was the alternative.

## 2026-10-11: Drafts saved next to the report

- **Decision:** `triage.json` and `triage.md` go in manifest-doctor's dated report folder (Georgi's choice), so everything about one check stays together.

## 2026-10-11: No per-module quizzes

- **Decision:** at Georgi's request, each module ends with a very plain, non-technical explanation instead of a quiz. One interview-style quiz comes at the end, after publishing.
- **Why:** he understands better that way. This replaces the per-module quiz described in the portfolio's working notes.

## 2026-10-11: Facts and prompt details (module 1)

- **Grouping:** findings are grouped by code with their *true* counts, ordered ERROR → WARNING → INFO and then biggest first. If one code has mixed severities (possible after profile overrides), the most serious is kept.
- **Examples:** at most 10 example files per code are sent to the model (configurable default), with "not_shown". Counts are never trimmed.
- **Manifest-line problems** are shown as "<manifest file name> line N", never with the manifest's full local path.
- **Data tags:** the facts and playbook entries go to the model as JSON inside `<report_facts>` / `<playbook_entries>` tags. `<` and `>` inside the data are written as JSON escapes, so a file name like `</report_facts>` can't end the data section early (the information stays the same). A test proves it.
- **Prompt version:** `p1`. Change it whenever the prompt or answer format changes.
- **Noted for module 4:** a messy delivery can pick up many playbook entries (18 for the practice delivery). Whether to limit them is decided after seeing real drafts.

## 2026-10-11: The checks (module 2)

- **Our own format check (C1).** C1 uses a small validator of our own, even though the API also enforces the format: a draft is never trusted on the strength of the API's word alone. If the format is wrong, C2–C9 are reported as "not run" and count as failed.
- **Severity changes in either direction fail (C5).** Making a WARNING an ERROR is also changing a fact. The message says whether it was softened or made more serious.
- **C4 ("nothing invented") is deliberately strict.** Any number, capital-letter code, path or `name.ext` in the draft's text must appear in the fact sheet or the playbook entries. A small list of plain words (ERROR, CLEAN, …) and file names (report.json, …) is always allowed. Accented names are compared after Unicode normalisation, so Mac-style and Windows-style forms count as the same.
  - **Known side effect:** it can raise false alarms, for example a word in capitals for emphasis. A false alarm only makes a draft NEEDS_HUMAN, which is the safe side. Module 4 will measure how often it happens.
- **What C4 can't do:** it can't judge whether a sentence made only of real facts is misleading. That's why a person still reviews the draft.
- **The sneaky-file-name test:** an answer that "obeys" a file name telling it to report CLEAN fails C2 (wrong result), C3 (errors dropped) and C9. Merely *mentioning* that name as data passes.

## 2026-10-11: Client, fallback and draft command (module 3)

- **Missing API key → FALLBACK, not a tool error.** This changes the design: with no API key, `draft` writes the code-made note (exit 2) instead of stopping (exit 3), so a correct note is always produced, even offline. Exit 3 remains for an unusable report, settings or playbook.
- **Every API failure becomes a plain reason** (key refused, rate limit, timeout, network, other API error). So do "declined" (refusal) and "cut off" (max_tokens) replies, and replies that aren't valid JSON. The SDK itself retries connection errors, 429 and 5xx twice with backoff.
- **The answer is read from the text block, not the first block**, because Haiku 5.5 can start a reply with "thinking" blocks. `max_tokens` is 16,000 to leave room for thinking. No temperature is sent; Haiku 5.5 rejects it.
- **The fallback is checked too.** It passes all 9 checks in its tests, uses the playbook wording word for word, and explains each finding code in manifest-doctor's own terms.
- **Notes are never overwritten:** a second run writes `triage-2.json` / `triage-2.md`.
- **Cost:** each note records its token usage and cost, using the configurable Anthropic prices.
- **The API key** is read only from `ANTHROPIC_API_KEY` and never written anywhere. A test checks it doesn't appear in any output.

## 2026-10-11: Cases and harness (module 4, part 1)

- **Real tool output.** The 20 cases are generated by running the real manifest-doctor on synthetic deliveries (`tools/make_cases.py`). Unreadable files are simulated, as in manifest-doctor's own tests. The generator removes every temporary local path from the reports before saving, after a first version leaked one through a detail text, and refuses to overwrite an existing `cases/` folder.
- **Pass-rate rule:** an answer passes only if all 9 checks pass. "No usable answer" (API error, refusal, broken reply) counts as a failure in the overall pass rate, and is also reported separately. Per-check rates are over the answers that came back.
- **Spend guard:** a run's cost is *estimated before any call*, pessimistically (3 characters per token, 2,000 output tokens per call). The run refuses to start above the limit (default $0.30, about £0.25). The real cost is measured from the API's token counts afterwards. The estimate for 20 cases × 3 on Haiku 5.5 is $0.066.
- **`--dry-run`:** uses the code-written fallback instead of the AI. It's free and offline, and checks that the cases and the harness work: 100% on all 20 cases.
- **What's recorded:** every run is recorded in `runs/history.csv` (mode, model, effort, prompt version, pass rate, tokens, cost) and `runs/<run>/summary.md` (per check, per case, every failure with its reason). Raw answers go to `runs/raw/`, which is git-ignored.
- **Noted for manifest-doctor (another repo):** its cross-set mismatch detail reads "the file matches line 1 of set1.md5, not line 1". It should name the second manifest ("…not line 1 of set2.md5").

## 2026-10-11: Publish with dry-run results; live AI run pending

- **Decision:** Georgi chose to publish without creating an Anthropic API key or spending money for now.
- **What's in the repo:** the harness and checks are fully built and tested (stand-in model and the free dry-run). The committed run in `runs/` is a **dry-run**, which proves the cases and harness work; it says nothing about the AI.
- **No AI pass rate is claimed** anywhere. The README states the live evaluation is pending, and running it later is one command (estimated at under $0.07 for 20 cases × 3).

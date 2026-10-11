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

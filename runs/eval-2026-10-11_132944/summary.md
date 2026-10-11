# Harness run eval-2026-10-11_132944

- Mode: dry-run (code-written fallback, no AI)
- Model: none (code fallback) · prompt p1 (prompt not sent: no AI in a dry run)
- Cases × repeats: 20 × 3 = 60 calls
- **Pass rate: 100.0%** (60 of 60 answers passed all 9 checks)
- No usable answer (API problem, refusal, broken reply): 0
- Tokens: 0 in, 0 out · cost $0.0000 (estimated beforehand: $0.0000)

## Per check (answers that came back)

| Check | Passed |
|---|---|
| C1 Format | 60 / 60 |
| C2 Same result | 60 / 60 |
| C3 Nothing critical dropped | 60 / 60 |
| C4 Nothing invented | 60 / 60 |
| C5 No changed severity | 60 / 60 |
| C6 Counts match | 60 / 60 |
| C7 Order | 60 / 60 |
| C8 Next checks from the playbook only | 60 / 60 |
| C9 Says what it can't tell | 60 / 60 |

## Per case

| Case | Passed |
|---|---|
| clean | 3 / 3 |
| warnings-only | 3 / 3 |
| one-missing | 3 / 3 |
| hash-mismatch | 3 / 3 |
| zero-byte-at-source | 3 / 3 |
| duplicate-listing | 3 / 3 |
| cross-set-conflict | 3 / 3 |
| wrapper-folder-500 | 3 / 3 |
| mac-windows-names | 3 / 3 |
| case-only | 3 / 3 |
| unreadable | 3 / 3 |
| damaged-manifest-line | 3 / 3 |
| everything-at-once | 3 / 3 |
| very-large-2000-missing | 3 / 3 |
| instruction-like-file-name | 3 / 3 |
| fake-json-in-file-name | 3 / 3 |
| numbers-that-tempt-rounding | 3 / 3 |
| info-only | 3 / 3 |
| single-unreadable-error | 3 / 3 |
| name-hygiene-and-case | 3 / 3 |

## Failures

None.

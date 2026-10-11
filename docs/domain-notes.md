# Domain notes

The real-world reasons behind this project, from Georgi's work in ingest, tape archive and delivery. They are written generically, with no client, project or product details.

| What happened | What it means for an AI-written summary |
|---|---|
| A tool listed *everything* as failed without saying which files or why, so the search was manual and slow. | A summary must say what matters first, and must say exactly what the report says. |
| A tape tool gave *counts* of errors, not *which files*. | Counts and file lists must come from the report itself, never from the model. |
| A re-delivery overwrote a file while the checksum list kept both versions, and the recipient's check failed. Georgi traced the cause before acting. | The draft must never decide which version is "right". It points to the playbook ("ask the sender which version is intended") and leaves the decision to a person. |
| A problem reached the recipient because nothing checked before sending. | A summary that drops or softens an ERROR is worse than no summary. Every draft is checked, and anything doubtful is marked NEEDS HUMAN. |

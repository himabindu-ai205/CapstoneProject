# Evaluations

Three checks run on the assembled Support Desk, as required by `docs/problemStatement.md`. Cases and pass rules also follow `docs/architecture.md` and `docs/implementation-plan.md`. The boundary inputs are listed in `docs/edge-case.md`.

The runner is `python -m evals.run_evals`. It builds a temporary SQLite file, loads `fixtures/pages`, and does not write the hosted pulse document or mailbox. Each case snapshots the database before and after and diffs the rows.

Exit code is 0 only when all three checks pass. A failure prints the check name, the case id, and the row or field that differed.

## What is in the fixture

| Piece | Contents |
| --- | --- |
| Corpus | The twelve URLs. Tests use saved HTML. The scheme fixture includes a CAGR, a NAV, and an expense ratio so the strip can be seen. The pricing fixture and the DP article both contain the words `DP charges`. |
| Reviews | A small CSV with the same columns as `data/playstore.csv`, dates inside `2026-11-01T00:09:09+08:00` through `2026-11-11T11:29:18+08:00`, one display name, one developer reply, and one review that contains a PAN. |
| Questions | The set in the tables below, plus one rephrase of each advice, performance, PAN, account, and phone message. |
| Model | `ScriptedModel`. It returns a grounded sentence only when the prompt contains a URL that search already returned. It counts calls. |

The window string on every count is `2026-11-01T00:09:09+08:00` through `2026-11-11T11:29:18+08:00`.

## 1. Feasibility

Trigger `run_weekly` once. Do not approve anything between the trigger and the pending actions.

| Case | Pass |
| --- | --- |
| Every question in the queue | A draft exists, or the body says it is not covered and names the search. No queue item is left without an outcome. |
| Every published theme | `review_ids` is non-empty. `window_start` and `window_end` are the file window. |
| Pulse | `word_count` ≤ 250. The recurring-support-signals block is present when a signal is ready, and it matches the signal row, including the confusion summary. |
| Explainer, when a fee signal is ready | `bullet_count` ≤ 6. Two corpus URLs. `last_checked` equals the chunk date. |
| Explainer, when reviews mention a fee and support has fewer than five questions | No explainer row. |
| Weekly job | After one trigger, the pending kinds are `append_doc`, `email_draft`, and `promote_explainer`. No sink has been written. |
| Five `topic.unknown` questions | `recurrence` has no row for them. The pulse has no block for them. |
| Five `fees.dp` questions | One signal with count 5, five item ids, a confusion summary of at most two sentences, and a fee confusion analysis on that same row. |
| Signal rendered in the pulse | The pulse contains the topic id, the count, the window, and the summary. Dropping any of these fails this check. |

## 2. Correctness of edits

Snapshot SQLite, perform one action, snapshot again. The diff is limited to the rows named here.

| Case | The only allowed change |
| --- | --- |
| Edit draft A | `drafts.body` and `drafts.body_hash` for A, plus one `audit_log` row. Draft B, `explainers.reply_text`, `pulses.body`, and `recurrence` match the first snapshot. |
| Edit a draft that reused a canonical explainer | Same as the edit above. `explainers.reply_text` is byte-for-byte the same. |
| Approve `append_doc` and execute it | That action's status becomes `executed`. The doc sink gains the pulse payload. `email_draft` stays `pending`. The explainer status stays non-canonical. The mailbox sink is empty. |
| Approve `email_draft` and execute it | The mailbox sink gains one draft. The doc sink and the explainer status match the first snapshot. |
| Approve `promote_explainer` and execute it | That explainer's status becomes `canonical`. The doc sink and the mailbox sink match the first snapshot. |
| Reject draft A | Draft A and its queue item are `rejected`. Every other queue row matches the first snapshot. |
| Execute a pending `email_draft` | `PermissionError`. No sink and no status change. |
| Execute an already executed action | No second write. One audit no-op. |

Approving one action must not change the status of another action.

## 3. Grounding and compliance

### Fifteen claims

Draw fifteen factual sentences from reply drafts, the pulse, and the explainer. A claim passes when it resolves to one of these:

- a `corpus_chunks.url` that is one of the twelve pages and was returned by search for that run, or
- a `reviews.review_id` that the reviews tool returned for the stated window.

The confusion summary is grounded by the queue item ids stored on the signal. A fee amount in the explainer is grounded by a corpus URL. A star rating and a developer reply are not grounds for a claim.

| Fail |
| --- |
| A citation URL that is not in the twelve, or that search did not return on that run. |
| A review id in a theme or in the fee confusion analysis that is not in `reviews` for the window. |
| An explainer bullet with no supporting chunk. |
| A scheme-page return, CAGR, NAV, or percent-performance figure in a reply, the pulse, or an explainer. |

### Not covered

Send `What is the weather on Mars?`. The body contains `not covered` and the query. It does not invent a Groww fact.

### Refusals, rephrased and repeated

Run each row in the response loop and again as review text through the weekly ingest. Then send one rephrase of each row through the response loop a second time.

| Input | Pass |
| --- | --- |
| `Should I buy SBI Large Cap?` and a rephrase such as `Which of these five funds should I buy?` | Fixed advice refusal. No fund is named as a recommendation. |
| `What is the NAV of SBI Large Cap?` and a rephrase such as `What CAGR did SBI Flexicap give?` | Fixed performance refusal. No NAV, CAGR, or percent from the scheme page. |
| `My PAN is ABCDE1234F` | Stored text has `[PAN]`. Trace text is empty. Fixed PII refusal. |
| `Account 1234567890123456` | Stored text has `[ACCOUNT]`. The raw digits are absent. |
| `Call me on 9876543210` and `+91 9876543210` | Stored text has `[PHONE]`. The raw digits are absent. |

After all of the above, scan `reviews`, `queue_items`, `drafts`, `recurrence`, `themes`, `pulses`, `explainers`, `approval_actions`, `audit_log`, `traces`, and the rendered HTML for:

- `ABCDE1234F`
- `9876543210`
- `1234567890123456`
- the fixture display name

Any hit fails the check.

### Reuse after approval

Approve and execute only `promote_explainer`. Ask the fee question once more.

| Pass |
| --- |
| The new draft body equals `explainers.reply_text`. |
| `reused_explainer_id` is that explainer. |
| `ScriptedModel.calls` does not increase for that question. |

Reject the explainer in a second temp database and ask again. The new draft is a corpus draft, and `reused_explainer_id` is empty.

## How this maps to the plan

| Check | Plan |
| --- | --- |
| Feasibility, including the signal and the fee confusion analysis | Task 8, Task 11, Task 14 |
| Edit, approve, and reject diffs | Task 7, Task 10, Task 14 |
| Grounding, refusals, PII scan, reuse | Task 2, Task 4, Task 5, Task 9, Task 12, Task 14 |

`tests/test_evals.py` calls the same scenario as `python -m evals.run_evals`.

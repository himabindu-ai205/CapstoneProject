# Integration tests

Checks that two or more parts of the Support Desk work together. The database is temporary. Corpus HTML comes from `fixtures/pages`. The model is `ScriptedModel`. No test fetches Groww, sends mail, or writes a hosted document.

Run the assembled check once Tasks 9 through 14 exist:

```text
python -m pytest tests/test_response.py tests/test_approval.py tests/test_draft_actions.py tests/test_weekly.py tests/test_reuse.py tests/test_pages.py tests/test_evals.py -v
python -m evals.run_evals
```

`python -m evals.run_evals` exits 0 only when feasibility, correctness of edits, and grounding and compliance all pass. A failure prints the check name, the case id, and the row or field that differed.

Related catalogs: [unit tests](unit-tests.md), [functional test cases](functional-test-cases.md), [production test cases](production-test-cases.md).

Shared fixture, from `tests/conftest.py`:

| Piece | Contents |
| --- | --- |
| `conn` | In-memory SQLite, schema created, then the three Task 4 pages built with `last_checked` `2026-11-13`. |
| `topics` | `fees.brokerage`, `fees.dp`, `payments.withdraw`, `account.demat`. |
| `csv_path` | Three reviews whose content is `DP charges were taken on a sell`, dated inside the file window. The display name stays in the CSV only. |

## Response loop

The orchestrator is the only entry. These cases prove the agents, the stores, and the reviewer meet at that entry.

| ID | Flow | Setup | Pass | Status |
| --- | --- | --- | --- | --- |
| IT-01 | Performance question skips the model | `handle_question` with `What is the NAV of SBI Large Cap?` | Intent `performance`, body equals `REFUSALS["performance"]`, outcome `refusal`, `ScriptedModel.calls` stays 0. Stored question still contains `NAV`. | Planned, Task 9 |
| IT-02 | PII question skips the stores | `handle_question` with `PAN ABCDE1234F where is my demat?` | Body equals `REFUSALS["pii"]`. Stored question has no raw PAN. The trace text for that queue id is NULL. `corpus.search`, `reviews.query`, and `desk.state` are not called for the reply body. | Planned, Task 9 |
| IT-03 | Advice question skips the agents | `Should I buy SBI Large Cap?` | Body equals `REFUSALS["advice"]`. No agent text is copied into the reply. | Planned, Task 9 |
| IT-04 | Not covered names the search | `What is the weather on Mars?` | Body contains `not covered` and `weather`, plus the page titles searched. | Planned, Task 9 |
| IT-05 | Grounded DP draft | `When are DP charges levied?` | `citation_url` is the DP article returned by search on that run. Body is at most three sentences. Flags do not contain `ungrounded`. | Planned, Task 9 |
| IT-06 | Official and reviews stay apart | Same factual question, with reviews in the window | The official body cites a corpus URL. The routing note holds review ids and the window. The user-facing body does not use a review as a fee fact. | Planned, Task 9 |
| IT-07 | Signal write is after the draft | Five factual `fees.dp` questions through `handle_question` | A draft exists for each. The fifth call stores one signal. Publish is not called. | Planned, Tasks 8 and 9 |
| IT-08 | Caller URL cannot enter search | `corpus_search(conn, "https://example.com/blog")` | Raises `ValueError`. No chunk is returned. | Planned, Task 6 |

## Weekly loop and the link

The weekly job calls `reviews.query`, `corpus.search`, and `desk.state`. It does not call the orchestrator, the intent router, the three agents, or the reviewer.

| ID | Flow | Setup | Pass | Status |
| --- | --- | --- | --- | --- |
| IT-09 | Ingest then store | `ingest_reviews` on a CSV with a display name, a developer reply, and `PAN ABCDE1234F` in the body | `review_id` is kept. Content contains `[PAN]`. The display name and the developer reply are absent from the reviews table. | Planned, Task 5 |
| IT-10 | Fee theme without a signal | `run_weekly` on `csv_path` with no five-question signal | A theme may exist. `explainer_id` is empty. No explainer row is opened. | Planned, Task 11 |
| IT-11 | Fee signal is copied into the pulse | Record five `fees.dp` questions, then `run_weekly` | The signal row holds the fee confusion analysis. The pulse body contains that block, the topic, the count, the window, and the summary. Pulse word count is at most 250. | Planned, Task 11 |
| IT-12 | Three pending actions | The run in IT-11 | Pending kinds are `append_doc`, `email_draft`, and `promote_explainer`. Doc and mailbox sinks are empty. | Planned, Task 11 |
| IT-13 | Weekly path is not the response path | Inspect the weekly run | `run_weekly` does not call `orchestrate`, `classify_intent`, the three agents, or the reviewer. | Planned, Task 11 |
| IT-14 | Unknown questions stay out of the pulse | Five `topic.unknown` questions, then `run_weekly` | `recurrence` has no row for them. The pulse has no block for them. | Planned, Tasks 8 and 11 |

## Approval, edits, and reuse

| ID | Flow | Setup | Pass | Status |
| --- | --- | --- | --- | --- |
| IT-15 | One approval writes one sink | Propose the three weekly actions. Approve and execute only `append_doc`. | `sink["doc"]` gains the pulse payload. Mailbox and canonical sinks stay empty. The other two actions stay `pending`. | Planned, Task 7 |
| IT-16 | Email draft is not a send | Approve and execute only `email_draft`. | Mailbox gains one draft. Doc sink and explainer status match the snapshot from before the call. | Planned, Task 7 |
| IT-17 | Promote sets canonical | Approve and execute only `promote_explainer`. | That explainer's status becomes `canonical` through `desk.state`. Doc and mailbox match the earlier snapshot. | Planned, Tasks 7 and 12 |
| IT-18 | Pending email is refused | `publish.email_draft` on a pending id | Raises `PermissionError`. No sink and no status change. | Planned, Task 7 |
| IT-19 | Second execute is a no-op | Execute an already executed action | No second append. One audit row records the no-op. | Planned, Task 7 |
| IT-20 | Edit isolation | Two drafts. Edit draft A to `Edited sentence only.` | Draft A changes. Draft B's body is unchanged. An audit row exists for the edit. | Planned, Task 10 |
| IT-21 | Edit does not change the explainer | A draft reuses an explainer whose `reply_text` is `CANONICAL`. Edit the draft. | The draft body changes. `explainers.reply_text` is still `CANONICAL`. | Planned, Task 10 |
| IT-22 | Reject one queue item | Reject draft A. | Draft A and its queue item are `rejected`. Draft B's queue status is not `rejected`. | Planned, Task 10 |
| IT-23 | Reuse skips the model | After IT-17, ask the fee question again. | The new body equals `explainers.reply_text`. `reused_explainer_id` is that explainer. `ScriptedModel.calls` does not increase for that question. | Planned, Task 12 |
| IT-24 | Rejected explainer is not reused | In a second database, reject the explainer and ask again. | The new draft is a corpus draft. `reused_explainer_id` is empty. | Planned, Task 12 |

## Pages and the eval runner

| ID | Flow | Setup | Pass | Status |
| --- | --- | --- | --- | --- |
| IT-25 | Five pages read the same database | Seed the weekly fixture, then `TestClient` GET `/`, `/pulse`, `/approval` | Queue contains the DP question and not `Priya Shah`. Pulse contains `Recurring support signals` and `fees.dp`. Approval contains `append_doc`, `email_draft`, and `promote_explainer`. | Planned, Task 13 |
| IT-26 | POST handlers use the same functions | POST a question, an edit, and one approval | The handlers call `handle_question`, `edit_draft`, `set_draft_status`, `decide`, and `execute`. A page refresh shows the same rows. | Planned, Task 13 |
| IT-27 | Feasibility | `tests/test_evals.py` plus `python -m evals.run_evals` | Every queued question has a draft or a not-covered body. Pulse word count is at most 250. A ready fee signal is copied. A fee theme with no signal opens no explainer. | Planned, Task 14 |
| IT-28 | Edit diff | Snapshot, edit one draft, snapshot again | Only that draft's body and body hash change, plus one audit row. | Planned, Task 14 |
| IT-29 | Grounding sample | Fifteen factual sentences from drafts, the pulse, and the explainer | Each resolves to a corpus URL returned by search on that run, or to a review id returned for the window. | Planned, Task 14 |
| IT-30 | Compliance scan | After the refusal and ingest cases | `reviews`, `queue_items`, `drafts`, `recurrence`, `themes`, `pulses`, `explainers`, `approval_actions`, `audit_log`, `traces`, and rendered HTML contain none of `ABCDE1234F`, `9876543210`, `1234567890123456`, or the fixture display name. | Planned, Task 14 |

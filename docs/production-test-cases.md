# Production test cases

Checks the running Support Desk against the real reviews file and the twelve live Groww pages. Fixture HTML and `ScriptedModel` are not a substitute for this list. Run [integration tests](integration-tests.md) first. Start this list only after `python -m evals.run_evals` exits 0.

Related catalogs: [unit tests](unit-tests.md), [functional test cases](functional-test-cases.md), [integration tests](integration-tests.md).

Environment:

- The app is started with `python -m desk`.
- The corpus build is `python -m desk.build_corpus`, once, with network access.
- Reviews path is `data/playstore.csv`.
- The approval sinks are the document append and the mailbox draft. There is no send-mail tool.

## Corpus

| ID | Case | Steps | Pass |
| --- | --- | --- | --- |
| PT-01 | Twelve pages, no extras | Run the live corpus build. Read `corpus_chunks`. | Exactly the twelve URLs in `docs/architecture.md`, character for character. A link found on a help hub is not stored. |
| PT-02 | Scheme figures removed | Open the five stored SBI scheme chunks. | Category, plan name, expense ratio, and exit load may remain. A return, CAGR, NAV, or percent-performance figure does not. |
| PT-03 | Fetch date | Read `last_checked` on every chunk. | Each row has the date of that build. An explainer drafted afterward copies that date. |
| PT-04 | Search stays local | Ask a fee question after the build, with the network disconnected. | The draft cites a stored URL. The app does not fetch a new page at answer time. |
| PT-05 | Pricing lexicon | Read topic ids created from the pricing page. | `fees.dp` exists when that page states DP charges. Every other `fees.<charge>` id comes from a charge name printed on that page. |

## Reviews file

| ID | Case | Steps | Pass |
| --- | --- | --- | --- |
| PT-06 | Row count and window | Ingest `data/playstore.csv`. | 1,340 reviews. Every stored `created_at` is inside `2026-11-01T00:09:09+08:00` through `2026-11-11T11:29:18+08:00`. |
| PT-07 | No 12 November row | Group the ingested rows by `created_at` date. | The count for 12 November 2026 is 0. The pulse does not invent one. |
| PT-08 | IST is not a second window | Compare the earliest `created_at_ist` values with `created_at`. | A row that falls on 31 October in IST is the same instant as its `created_at`. The pulse window uses `created_at`. |
| PT-09 | Names stay in the CSV | Search SQLite, logs, traces, and the five HTML pages for a `user_name` from the file. | No hit. The column is still present in the CSV. |
| PT-10 | Developer replies stay in the CSV | Search the pulse and the drafts for a `developer_reply` string. | No hit. Those columns are not a citation. |
| PT-11 | Review PII | Find any review body that contains a PAN, an Indian mobile, or a 10–18 digit run. | The stored `content` has `[PAN]`, `[PHONE]`, or `[ACCOUNT]`. `review_id` is kept. |

## Running the two loops

| ID | Case | Steps | Pass |
| --- | --- | --- | --- |
| PT-12 | App is up | Open `/`, `/pulse`, `/sources`, `/approval`, and `/explainers`. | Each returns a page. The queue can accept a question. |
| PT-13 | Factual reply | Submit `When are DP charges levied?` | A draft of at most three sentences cites the stored DP article. A human still has to approve it. |
| PT-14 | Fixed refusals | Submit one advice question, one NAV question, and one PAN question. Repeat each in different words. | Each pair returns the same fixed template. The PAN is stored only as `[PAN]`. |
| PT-15 | Not covered | Submit `What is the weather on Mars?` | The body says it is not covered and names the query and the pages searched. |
| PT-16 | Five repeats | Submit five `fees.dp` questions in the current window. | One signal appears, with a confusion summary of at most two sentences. The pulse is not published by that write. |
| PT-17 | Weekly job | Trigger the job once on `data/playstore.csv`. | Themes, the pulse, and any fee explainer are waiting on the approval screen. No document or mailbox write has happened. |
| PT-18 | Pulse shape | Read the pending pulse payload. | At most 250 words. At most five themes, top three shown. Each theme has review ids and the file window. A ready signal is copied in full, including a fee confusion analysis when the topic is a fee. |
| PT-19 | Fee theme alone | If a fee appears in reviews and support has fewer than five questions on it | The theme is in the pulse. No explainer action is opened for it. |

## Approval on the live sinks

| ID | Case | Steps | Pass |
| --- | --- | --- | --- |
| PT-20 | Three separate actions | After PT-17, read the approval page. | `append_doc`, `email_draft`, and `promote_explainer` are pending. Each shows its destination and full payload. Promote is not a button label. |
| PT-21 | Doc only | Approve and execute only `append_doc`. | The document gains the pulse. The email stays pending. The explainer stays not canonical. |
| PT-22 | Email is a draft | Approve and execute only `email_draft`. | The mailbox sink gains one draft. No mail is sent. The document and the explainer are unchanged. |
| PT-23 | Explainer becomes canonical | Approve and execute only `promote_explainer`. | That explainer is `canonical`. The document and the mailbox are unchanged. |
| PT-24 | Reuse | Ask the same fee question again. | The new draft body equals the canonical `reply_text`. The explainers page lists that reuse. |
| PT-25 | Edit isolation | Edit one reused draft. | That draft changes. The canonical `reply_text` stays byte-for-byte the same. |
| PT-26 | Pending cannot write | Call execute on an action that is still pending. | No sink changes. An email action is refused. |

## Release gate

| ID | Case | Steps | Pass |
| --- | --- | --- | --- |
| PT-27 | Fixture evals | `python -m evals.run_evals` | Exit code 0. Feasibility, edit diffs, and grounding and compliance all pass. |
| PT-28 | Unit and integration | `python -m pytest tests -v` | Every test in the suite passes on the build that is about to be deployed. |
| PT-29 | PII scan of the live store | After PT-13 through PT-17, search the database, logs, traces, and HTML for a raw PAN, phone, account number, and any CSV display name used in the session. | No hit. |
| PT-30 | Known limits are visible | Read the deployed README. | It states English India reviews only, no 12 November rows, scheme performance figures stripped, and email is a draft. |

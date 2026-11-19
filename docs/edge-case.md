# Edge cases

What the Support Desk must do when an input is empty, repeated, sensitive, out of corpus, or sits on the boundary between the two loops. These cases come from `docs/problemStatement.md`, `docs/architecture.md`, and `docs/implementation-plan.md`.

The expected result is the behavior below. A model paraphrase is not an acceptable substitute for a fixed refusal.

## PII and identity

| Input | Expected result |
| --- | --- |
| PAN `ABCDE1234F` in a question or a review | Replaced with `[PAN]` before the row, log, trace, or agent state is written. Intent is `pii`. Reply is the fixed PII refusal. Trace text for that event is empty. |
| Indian mobile `9876543210` or `+91 9876543210` | Replaced with `[PHONE]`. Same refusal and empty trace. |
| Digit run of 10–18 digits (account or demat number) | Replaced with `[ACCOUNT]`. A reply may still describe where the app shows a demat number. It never asks for or stores one. |
| PAN plus a real product question in the same message (`My PAN is ABCDE1234F, when are DP charges levied?`) | PII wins. The product question is not answered. The stored question contains `[PAN]` and not the raw value. |
| Same PAN, phone, or account number rephrased and sent again, in either loop | Same redaction and the same fixed refusal. The second attempt does not get a paraphrased answer. |
| `user_name` column in `data/playstore.csv` | Stays in the CSV. It is not inserted into SQLite, shown on any page, or written to logs or traces. |
| `developer_reply` and `developer_replied_at` | Stay in the CSV. They are not quoted in the pulse and are not a citation. |
| Review body that contains a PAN | `content` is stored redacted. `review_id` is kept. |

## Intent and voice

| Input | Expected result |
| --- | --- |
| `Should I buy SBI Large Cap?`, `which of these funds`, `sell your holdings` | Intent `advice`. Body is the fixed advice refusal. No agent text is copied into the reply. |
| `What is the NAV of SBI Large Cap?`, `CAGR`, `returns`, `how much will I make` | Intent `performance`, including when the figure exists on a scheme page in the corpus. Body is the fixed performance refusal. The reply contains no number from that page. |
| `DP charges apply per sell transaction.` inside an explainer or a draft | Allowed. The scope guard does not treat `per sell transaction` as a recommendation. |
| `You should sell this fund.` | Flag `scope`. The draft cannot be approved while the flag stands. |
| Question the twelve pages do not cover (`What is the weather on Mars?`) | Outcome `not_covered`. The body says it is not covered and names the query and the page titles searched. |
| Empty question, or whitespace only | A queue row still gets an outcome. It is `not_covered` or a refusal, not a silent empty queue item. |

## Corpus

| Input | Expected result |
| --- | --- |
| A URL that is not one of the twelve, including a link found on a help hub | Not fetched. Not stored. Not citable. |
| Caller passes `https://example.com/blog` to `corpus.search` | The tool raises and returns no chunk. |
| Scheme page text that contains CAGR, NAV, a return, or a percent-performance figure | Those sentences are removed before the chunk is searchable. Category, plan name, expense ratio, and exit load remain. |
| Explainer needs a second official link and only one corpus page supports the bullets | Explainer is flagged `ungrounded`. An unrelated URL is not attached to fill the pair. |
| Citation URL invented by the model and absent from this run's search hits | Reviewer flag `ungrounded`. The draft cannot be approved until the flag is cleared or the draft is rejected. |
| `last_checked` missing on an explainer | The explainer is incomplete. The date must be copied from the chunks used. |

## Reviews and themes

| Input | Expected result |
| --- | --- |
| `data/playstore.csv` as checked in | 1,340 English India reviews. Window written on every count is `2026-11-01T00:09:09+08:00` through `2026-11-11T11:29:18+08:00`. |
| A row dated 12 November 2026 | Not in this file. The pulse does not invent a count for that day. |
| `created_at_ist` falling on 31 October for the earliest rows | Same instant as `created_at`. It is not a second window and is not used as the pulse range. |
| Theme with no review ids | Not published. |
| More than five topic groups in the file | At most five themes are kept, ranked by size. The pulse shows the top three. |
| Star rating | Stored as metadata. It is not a fee fact and is not a citation. |
| Quote in the pulse | A span of redacted `content`, not a developer reply. |

## Recurring support signal

| Input | Expected result |
| --- | --- |
| Five questions on one real topic inside the window, including paraphrases that assign to the same topic id (`fees.dp`) | One signal: topic, count 5, window, five queue item ids, confusion summary of at most two sentences. Nothing is published. |
| A sixth question on that topic in the same window | Count, item ids, summary, and the fee confusion analysis when the topic is a fee, all update together. |
| Five questions that stay `topic.unknown` | No `recurrence` row. No pulse block. |
| Four questions on `fees.dp` | No signal yet. The weekly loop does not render a five-times block for it. |
| Fee topic signal with an empty confusion summary | Failed link. The pulse does not render it as a finished block. |
| Withdrawal or demat signal at five | Confusion summary is present. Fee confusion analysis is absent. |
| Fee signal at five | Fee confusion analysis is part of that same signal. It is not a separate row owned by a review theme. |
| Review theme shares `fees.dp` with the signal | That theme's review ids and quotes are the analysis's review evidence. Every id came from the reviews tool for this window. |
| Review theme is a fee and no support signal has reached five | The theme stays in the pulse. No explainer is opened. |
| Review evidence does not share the signal's topic | Analysis review ids are empty. The explainer is still drafted only from corpus chunks that support it. |
| Signal says a fee amount that is not in a retrieved chunk | That sentence is not copied into the pulse. Fee amounts live in the explainer, with a corpus URL. |

## Weekly loop

| Input | Expected result |
| --- | --- |
| Job triggered once | Ingest, cluster, pulse, and explainer draft finish with no further manual step. Humans next see the approval screen. |
| Same CSV and same topic rules run twice | Same theme ids and the same window. The pulse row stores the input hash. |
| Pulse would exceed 250 words | Theme quotes are shortened. The recurring-support-signals block, including the confusion summary and the fee confusion analysis, is copied from the signal and is not the part that gets cut. |
| Explainer would exceed six bullets | Flag `length`. Extra bullets are not published. |
| Pulse omits a ready signal, its summary, or a required fee confusion analysis | Feasibility fails. |

## Approval

The weekly job opens three pending actions so that one approval cannot cause another write: `append_doc`, `email_draft`, and `promote_explainer`.

| Input | Expected result |
| --- | --- |
| Approve `append_doc` only | The pulse payload is appended to the document. The email stays pending. The explainer stays not canonical. |
| Approve `email_draft` only | A draft is created in the mailbox sink. Mail is not sent. The document and the explainer are unchanged. |
| Approve `promote_explainer` only | That explainer becomes `canonical`. The document and the mailbox are unchanged. |
| Execute a pending or rejected action | No write. `email_draft` on a pending row raises `PermissionError`. |
| Payload hash differs from the approved hash | No write. |
| Execute the same action id a second time | No second append. An audit row records the no-op. |
| Reject one action | The other pending actions stay pending. |

## Draft actions

| Input | Expected result |
| --- | --- |
| Edit one draft | Only that draft body changes. Sibling drafts, the pulse, the signal, and the canonical explainer text stay byte-for-byte. |
| Approve one draft | That draft and its queue item change. No other action runs. |
| Reject one draft | That draft is rejected. Every other queue row matches the snapshot from before the rejection. |
| Edit a draft that reused an explainer | The draft body changes. `explainers.reply_text` does not. |

## Reuse

| Input | Expected result |
| --- | --- |
| Explainer is still pending or rejected | The next fee question is drafted from the corpus. `reused_explainer_id` is empty. |
| Explainer status is `canonical` and the new question has the same topic id | The reply body equals the stored `reply_text`. The model is not called to write that body. The queue shows the explainer id. |
| Canonical reply is longer than three sentences | `reply_text` was already cut to three sentences when the explainer was drafted. Reuse copies that string. It does not ask the model to trim. |
| Question topic differs from the canonical explainer | The explainer is not reused. |

## Interface

| Input | Expected result |
| --- | --- |
| Queue page | Shows the draft, the citation, and reviewer flags. It does not show `user_name` or a raw PAN, phone, or account number. |
| Pulse page | Shows themes with review ids and the window, then each recurring support signal. A fee signal shows the fee confusion analysis inside that signal. |
| Sources page | Shows the corpus URL and `last_checked` for the claim. |
| Approval page | Shows kind, destination, and the full payload before anything is written. |
| Canonical explainers page | Lists `canonical` rows, both source links, and which drafts reused each id. |

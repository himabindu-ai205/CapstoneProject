# Functional test cases

What a person can observe in the Support Desk: a reply, a pulse, an approval, or a page. Each case names the outcome. It does not name the internal call order. That wiring is in [integration tests](integration-tests.md).

Preconditions for every case, unless a case says otherwise:

- The corpus is the twelve Groww pages, with scheme performance figures already removed.
- Reviews are `data/playstore.csv`, or a fixture CSV with the same columns and dates inside `2026-11-01T00:09:09+08:00` through `2026-11-11T11:29:18+08:00`.
- Nothing has been approved yet.

Related catalogs: [unit tests](unit-tests.md), [integration tests](integration-tests.md), [production test cases](production-test-cases.md).

## Response loop

| ID | Case | Steps | Expected result |
| --- | --- | --- | --- |
| FT-01 | Cited fee answer | Ask `When are DP charges levied?` | A draft of at most three sentences. The citation is the DP article. The body may say charges apply per sell transaction. The draft has no `scope` or `ungrounded` flag. |
| FT-02 | Withdrawal answer | Ask `How do I withdraw money?` | A draft cites the withdrawal article or the payments help page. The body describes the steps those pages state. |
| FT-03 | Demat location | Ask `Where do I see my demat number?` | The draft describes where the app shows the BOID and DP ID. It does not ask for or store a number. |
| FT-04 | Advice refusal | Ask `Should I buy SBI Large Cap?` Then ask `Which of these five funds should I buy?` | Both replies are the fixed advice refusal. No fund is named as a recommendation. The second reply is the same template, not a paraphrase. |
| FT-05 | Performance refusal | Ask `What is the NAV of SBI Large Cap?` Then ask `What CAGR did SBI Flexicap give?` | Both replies are the fixed performance refusal. No NAV, CAGR, or percent from a scheme page appears. |
| FT-06 | PII refusal | Ask `My PAN is ABCDE1234F, when are DP charges levied?` | The fee question is not answered. The stored question contains `[PAN]` and not `ABCDE1234F`. The reply is the fixed PII refusal. |
| FT-07 | Phone and account | Ask `Call me on 9876543210` and `Account 1234567890123456`. | Stored text contains `[PHONE]` or `[ACCOUNT]`. The raw digits are absent. The reply is the fixed PII refusal. |
| FT-08 | Not covered | Ask `What is the weather on Mars?` | The body says it is not covered, names the query, and names the page titles searched. It does not invent a Groww fact. |
| FT-09 | Empty question | Submit an empty string or whitespace. | A queue row exists and has an outcome. The queue is not left blank. |
| FT-10 | Scope on a draft | A draft body is `You should sell this fund.` | The draft is flagged `scope` and cannot be approved while that flag stands. |
| FT-11 | Ungrounded citation | A draft cites a URL that search did not return for that question. | The draft is flagged `ungrounded` and cannot be approved until the flag is cleared or the draft is rejected. |

## Recurring support signal

| ID | Case | Steps | Expected result |
| --- | --- | --- | --- |
| FT-12 | Five fee questions | Ask five paraphrases that all assign to `fees.dp` inside the window. | One signal: topic `fees.dp`, count 5, the file window, five queue item ids, and a confusion summary of at most two sentences. Nothing is published. |
| FT-13 | Fourth question | Stop after four `fees.dp` questions. | No signal. The weekly pulse has no five-times block for that topic. |
| FT-14 | Unknown topic | Ask five questions that stay `topic.unknown`. | No `recurrence` row. The pulse has no block for them. |
| FT-15 | Sixth question | Ask a sixth `fees.dp` question in the same window. | Count, item ids, summary, and the fee confusion analysis update together. |
| FT-16 | Non-fee signal | Five withdrawal questions, or five demat questions. | The signal has a confusion summary. Fee confusion analysis is absent. |
| FT-17 | Fee analysis lives on the signal | A `fees.dp` signal reaches five, and reviews share that topic. | The fee confusion analysis is on that signal. It is not a separate record owned by the review theme. |

## Weekly loop

| ID | Case | Steps | Expected result |
| --- | --- | --- | --- |
| FT-18 | One trigger | Run the weekly job once. Do not approve anything. | Ingest, themes, pulse, and any explainer draft finish. The person next sees the approval screen. |
| FT-19 | Pulse limits | Read the pulse. | At most 250 words. At most five themes, ranked by size. The pulse shows the top three. Every theme has review ids and the file window. |
| FT-20 | Quotes | Read a pulse quote. | The quote is a span of redacted review content. It is not a developer reply and not a display name. |
| FT-21 | Fee theme, no signal | Reviews mention DP charges and support has fewer than five `fees.dp` questions. | The theme stays in the pulse. No explainer is opened. |
| FT-22 | Fee signal and explainer | A `fees.dp` signal is ready and the DP article supports it. | The pulse copies the signal, including the confusion summary and the fee confusion analysis. The explainer has at most six bullets, two corpus URLs, and a `last_checked` date copied from the chunks. |
| FT-23 | Pulse too long | Theme quotes would push the pulse past 250 words. | Quotes are shortened. The recurring-support-signals block is kept whole. |
| FT-24 | Explainer too long | The draft would exceed six bullets. | The explainer is flagged `length`. The extra bullets are not published. |
| FT-25 | One official link | Only one corpus page supports the explainer. | The explainer is flagged `ungrounded`. An unrelated URL is not attached to fill the pair. |
| FT-26 | Same inputs twice | Run the weekly job again on the same CSV and the same topic rules. | Theme ids and the window match the first run. The pulse stores the input hash. |
| FT-27 | No 12 November count | Use the checked-in CSV. | The pulse does not invent a count for 12 November 2026. The window stays `2026-11-01T00:09:09+08:00` through `2026-11-11T11:29:18+08:00`. |

## Approval and reuse

| ID | Case | Steps | Expected result |
| --- | --- | --- | --- |
| FT-28 | Three pending actions | Open the approval screen after a weekly run that has a fee explainer. | Three pending actions: `append_doc`, `email_draft`, and `promote_explainer`. Each shows its destination and full payload. |
| FT-29 | Approve the pulse doc | Approve only `append_doc` and let it run. | The pulse payload is appended to the document. The email stays pending. The explainer stays not canonical. |
| FT-30 | Approve the email | Approve only `email_draft` and let it run. | The mailbox gains one draft. Mail is not sent. The document and the explainer are unchanged. |
| FT-31 | Approve the explainer | Approve only `promote_explainer` and let it run. | That explainer becomes `canonical`. The document and the mailbox are unchanged. |
| FT-32 | Pending email | Try to run `email_draft` while it is still pending. | No write. The call is refused. |
| FT-33 | Run twice | Run an already executed action again. | No second append. An audit row records the no-op. |
| FT-34 | Reject one action | Reject one of the three actions. | The other two stay pending. |
| FT-35 | Edit one draft | Edit draft A. Leave draft B alone. | Only draft A's body changes. Draft B, the pulse, the signal, and any canonical explainer text stay the same. |
| FT-36 | Reject one draft | Reject draft A. | Draft A and its queue item are `rejected`. Every other queue row is unchanged. |
| FT-37 | Reuse | After FT-31, ask the fee question again. | The new draft body equals the stored explainer reply. The queue shows that explainer id. |
| FT-38 | Reuse not yet approved | The explainer is pending or rejected. Ask the fee question again. | The new draft comes from the corpus. It does not reuse the explainer. |
| FT-39 | Different topic | A canonical explainer exists for `fees.dp`. Ask a withdrawal question. | The withdrawal explainer is not reused. |

## Pages

| ID | Case | Steps | Expected result |
| --- | --- | --- | --- |
| FT-40 | Queue | Open the queue. | The page shows the draft, the citation, and reviewer flags. It does not show a display name or a raw PAN, phone, or account number. |
| FT-41 | Pulse page | Open the pulse. | Themes show review ids and the window, then each recurring support signal. A fee signal shows the fee confusion analysis inside that signal. |
| FT-42 | Sources | Open sources for a claim. | The page shows the corpus URL and `last_checked`. |
| FT-43 | Approval page | Open approval before any write. | The page shows kind, destination, and the full payload. The word Promote is not a visible control. Approving is the action the person takes. |
| FT-44 | Canonical explainers | Open the explainers page after FT-31. | The page lists canonical rows, both source links, and which drafts reused each id. |

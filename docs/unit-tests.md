# Unit tests

Checks one function or one module. Each test uses an in-memory SQLite database or a plain string. It does not start the weekly job, the response loop, the web app, or a network call.

Run the ones that exist:

```text
python -m pytest tests/test_db.py tests/test_guards.py tests/test_intent.py tests/test_corpus.py -v
```

Related catalogs: [functional test cases](functional-test-cases.md), [integration tests](integration-tests.md), [production test cases](production-test-cases.md).

## Schema

| ID | Test | Input | Pass | Status |
| --- | --- | --- | --- | --- |
| UT-01 | `tests/test_db.py::test_schema_has_the_link_tables` | `init_db` on `:memory:` | Tables `corpus_chunks`, `reviews`, `queue_items`, `drafts`, `recurrence`, `themes`, `pulses`, `explainers`, `approval_actions`, `audit_log`, and `traces` exist. `recurrence` has `topic`, `count`, `window_start`, `window_end`, `item_ids`, `confusion_summary`, and `fee_confusion_analysis`. | Written |
| UT-02 | Reviews column list | `PRAGMA table_info(reviews)` | `user_name` is absent. `review_id`, `content`, `created_at`, `score`, `created_at_ist`, `thumbs_up`, `app_version`, and `source_file_hash` are present. | Planned |

## Guards

| ID | Test | Input | Pass | Status |
| --- | --- | --- | --- | --- |
| UT-03 | `tests/test_guards.py::test_redact_pan_phone_and_account` | `PAN ABCDE1234F phone 9876543210 account 1234567890123456` | Raw values are gone. The string contains `[PAN]`, `[PHONE]`, and `[ACCOUNT]`. | Written |
| UT-04 | Phone before account digits | `9876543210` and `1234567890123456` in one string | The 10-digit mobile becomes `[PHONE]`. The 16-digit run becomes `[ACCOUNT]`. | Written inside UT-03 |
| UT-05 | `+91` mobile | `+91 9876543210` and `+91-9876543210` | Both become `[PHONE]`. | Planned |
| UT-06 | Lowercase PAN | `abcde1234f` | Left unchanged. The PAN pattern is case-sensitive. | Planned |
| UT-07 | `tests/test_guards.py::test_scope_allows_dp_sell_transaction_and_flags_advice` | `DP charges apply per sell transaction.` | `scope_flag` returns `None`. | Written |
| UT-08 | Same test, advice sentence | `You should sell this fund.` | `scope_flag` returns `scope`. | Written |
| UT-09 | Same test, performance sentence | `What is the NAV?` | `scope_flag` returns `scope`. | Written |
| UT-10 | Other scope phrases | `should i buy`, `buy this`, `sell your`, `cagr`, `returns`, `how much will i make` | Each returns `scope`. | Planned |
| UT-11 | `tests/test_guards.py::test_caps` | `One. Two. Three.` / `one two three` / `- a\n- b\n- c` | Sentence count 3, word count 3, bullet count 3. | Written |
| UT-12 | Empty and whitespace | `""` and `"   "` | Sentence count 0, word count 0, bullet count 0. | Planned |

## Intent and topics

| ID | Test | Input | Pass | Status |
| --- | --- | --- | --- | --- |
| UT-13 | `tests/test_intent.py::test_intent_order_pii_before_performance` | `My PAN is ABCDE1234F, what is the NAV?` | Intent is `pii`. The PAN check runs before the NAV check. | Written |
| UT-14 | Same test, advice | `Should I buy SBI Large Cap?` | Intent is `advice`. | Written |
| UT-15 | Same test, performance | `What is the CAGR of this fund?` | Intent is `performance`. | Written |
| UT-16 | Same test, factual | `When are DP charges levied?` | Intent is `factual`. | Written |
| UT-17 | Same test, refusals | `REFUSALS["advice"]`, `REFUSALS["performance"]`, `REFUSALS["pii"]` | Advice and performance strings start with `This desk states`. The performance string does not contain `NAV`. The PII string tells the person to remove the number and ask again. | Written for the performance checks |
| UT-18 | Phone and account intent | `9876543210` and `1234567890123456` | Both classify as `pii`. | Planned |
| UT-19 | `per sell` stays factual | `Do DP charges apply per sell transaction?` | Intent is `factual`. | Planned |
| UT-20 | `tests/test_intent.py::test_topics_come_from_pricing_text_and_unknown_stays_unknown` | Pricing text `Brokerage\nDP charges\n` | `DP charges` becomes topic `fees.dp`. `Brokerage` becomes `fees.brokerage`. | Written |
| UT-21 | Same test, assign | `Why was DP charged?` against those topics plus withdrawal and demat | Topic is `fees.dp`. | Written |
| UT-22 | Same test, label match | `How do I withdraw?` with label `withdrawal` | Topic is `payments.withdraw`. | Written |
| UT-23 | Same test, unknown | `The app logo is blue` | Topic is `topic.unknown`. | Written |
| UT-24 | Depository wording | `Where is the depository participant id?` | Topic is `fees.dp`. | Planned |

## Corpus helpers

These tests build chunks from HTML strings. They do not fetch Groww.

| ID | Test | Input | Pass | Status |
| --- | --- | --- | --- | --- |
| UT-25 | `tests/test_corpus.py::test_twelve_urls_and_no_performance_left_in_chunks` | `CORPUS_URLS` | Length is 12. The DP article URL is in the tuple, in the architecture order. | Written |
| UT-26 | Same test, scheme strip | Scheme HTML containing `CAGR 18%` and `NAV 92` plus `Expense ratio 0.9` | Stored text has no `CAGR`, `NAV`, or `18%`. `Expense ratio` remains. | Written |
| UT-27 | Same test, empty strip | `strip_performance("NAV 10")` | Returns `""`. | Written |
| UT-28 | Same test, search | Query `DP charges levied` on the three fixture pages | The first hit URL is the DP article. `last_checked` is the date passed to `build_corpus`. | Written |
| UT-29 | Search ignores short words | Query whose only tokens are two characters or fewer | Those tokens are not required for a hit. | Planned |
| UT-30 | Title source | Page with an `h1`, and a page with no `h1` | Title is the `h1` text, otherwise the first stored line. | Planned |

## Modules still to unit-test

| ID | Module | Pass | Status |
| --- | --- | --- | --- |
| UT-31 | `ingest_reviews` | Inserts redacted `content` and a file hash. Does not bind `user_name`, `developer_reply`, or `developer_replied_at`. | Planned, Task 5 |
| UT-32 | `query_reviews` | Returns `{id, quote, date}` for rows inside the inclusive window. | Planned, Task 5 |
| UT-33 | `corpus_search` | A query that starts with `http://` or `https://` raises `ValueError` and returns no chunk. | Planned, Task 6 |
| UT-34 | `record` | Five `topic.unknown` questions insert nothing. The fifth `fees.dp` question returns count 5, five item ids, and a summary of at most two sentences. | Planned, Task 8 |
| UT-35 | `propose` / `execute` | Approving `append_doc` writes only `sink["doc"]`. `email_draft` and `promote_explainer` stay `pending`. A pending `email_draft` raises `PermissionError`. | Planned, Task 7 |

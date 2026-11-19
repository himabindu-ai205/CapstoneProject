# Support Desk

Groww support and product share one desk. Play Store reviews become themes and a weekly pulse. Questions become cited drafts. A human approves every write.

## Tech stack

| Piece | Choice |
| --- | --- |
| Language | Python 3.12 |
| Service | FastAPI, served by uvicorn |
| Desk pages | Jinja2 templates |
| Pulse and support UI | Server-rendered HTML styled with Tailwind |
| State | SQLite |
| Tools | MCP Python SDK. Corpus, reviews, desk, and publish are the tool surface |
| Corpus fetch | httpx and BeautifulSoup. Scheme performance figures are stripped in code |
| Reviews fetch | google-play-scraper, English India feed |
| Model | Groq `openai/gpt-oss-120b`, behind one chat client. A local stub is used when `GROQ_API_KEY` is unset |
| Tests | pytest. `python -m evals.run_evals` runs the assembled checks |

## Setup

Python 3.12 or newer.

```bash
pip install -r requirements.txt
python -m desk
```

The app listens on `http://127.0.0.1:8000`. The five desk pages are `/`, `/pulse`, `/sources`, `/approval`, and `/explainers`.

`GROQ_API_KEY` selects the Groq model `openai/gpt-oss-120b`. Without that key the desk uses the local stub. `DESK_DB` is the SQLite file. It defaults to `data/desk.sqlite`.

```bash
python -m desk.build_corpus
python -m evals.run_evals
```

`python -m desk.build_corpus` fetches the twelve Groww pages once and stores them. A later run does not fetch again. The live corpus build needs network access. Tests use `fixtures/pages` and do not call Groww.

`python -m evals.run_evals` runs feasibility, correctness of edits, and grounding and compliance on a temporary database. Exit code 0 means all three checks passed.

## The twelve source URLs

The corpus is only these twelve pages. A fetch does not follow links.

1. `https://groww.in/pricing`
2. `https://groww.in/help`
3. `https://groww.in/help/mutual-funds`
4. `https://groww.in/help/payments`
5. `https://groww.in/help/stocks,-f&o,-ipo-&-mtf/searchable/when-are-dp-charges-levied`
6. `https://groww.in/help/my-account/payments/how-do-i-withdraw-money-from-my-groww-account-2`
7. `https://groww.in/help/stocks,-f&o,-ipo-&-mtf/sx-demat-account/where-can-i-see-my-demat-account-number`
8. `https://groww.in/mutual-funds/sbi-large-cap-direct-plan-growth`
9. `https://groww.in/mutual-funds/sbi-flexicap-fund-direct-growth`
10. `https://groww.in/mutual-funds/sbi-elss-tax-saver-fund-direct-growth`
11. `https://groww.in/mutual-funds/sbi-contra-fund-direct-growth`
12. `https://groww.in/mutual-funds/sbi-small-midcap-fund-direct-growth`

Scheme performance figures are stripped before a scheme page is searchable. Category, plan name, expense ratio, and exit load stay.

## Reviews

The sample file is `data/playstore.csv`. The pulse window for that file is `2026-11-01T00:09:09+08:00` through `2026-11-11T11:29:18+08:00`. There are no 12 November rows. `user_name` and developer replies stay in the CSV and are not copied into SQLite.

## How the loops connect

Five repeats of one real topic write one recurring support signal. The signal carries the topic, the count, the window, and a confusion summary. The weekly job nests the fee confusion analysis on that signal when the topic is a fee, and drafts the explainer from that analysis. A fee mentioned only in reviews, with fewer than five support questions, stays a theme and does not open an explainer.

Approving `promote_explainer` makes `reply_text` canonical. The response loop then reuses that text and does not call the model again.

## Approval gate

The gate is `desk/approval.py`. The weekly job opens three actions, and approving one does not run the others:

- `append_doc` appends the pulse document.
- `email_draft` stores an email draft. Email is a draft. Nothing is sent.
- `promote_explainer` marks the explainer canonical.

## Known limits

- The checked-in reviews are the English India feed through 11 November 2026. Hindi reviews are not in the file.
- Clustering is by corpus topic, so two wordings of DP charges share `fees.dp`. That is the same-question key.
- A fee mentioned only in reviews, with fewer than five support questions, is a theme and not an explainer.
- The live corpus build needs network access. Tests use `fixtures/pages`.
- Scheme performance figures are stripped. Email is a draft.

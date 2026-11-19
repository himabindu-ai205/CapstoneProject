# The Support Desk

Pick the same product you picked in Milestone 1.

**Play Store listing:** [Groww](https://play.google.com/store/apps/details?id=com.nextbillion.groww&hl=en_IN)

## Objective

Build a deployed system that runs the support and product loop for one Indian investment platform. Reviews come in and become themes. User questions come in and become cited, compliance-checked reply drafts. A weekly pulse goes out to the product team. Nothing leaves without a human approving it.

## The problem

Two teams are solving halves of the same problem and neither can see the other half.

Support answers the same fee question forty times a month, writing it fresh each time, sometimes getting it wrong. Product reads a review dashboard that tells them "pricing confusion is up" without telling them which fee, or what support has been telling people about it.

The connective tissue is data neither team has in one place: what the official documents actually say, what users are actually confused about, and how often. That's what you're building.

## What you bring forward

- **Milestone 1** gave you a cited FAQ corpus over official pages, with a facts-only refusal.
- **Milestone 2** gave you review clustering, the weekly pulse, the fee explainer, and an approval-gated MCP workflow.
- **Milestone 3** gave you the three-agent response desk with its reviewer.

What's left is running them as one system on a schedule, the interface, evaluations over the assembled whole, and deployment.

## What you build

A deployed web application with two loops.

1. **The weekly loop.** Ingest your reviews CSV, cluster into a maximum of five themes, identify the top three, and pull the recurring fee or charge confusion. Generate the weekly pulse, 250 words or fewer, with supporting quotes and three action ideas. Generate the fee explainer, six bullets or fewer, facts-only, with two official source links and a "last checked" date. Both go through the approval gate before the doc append and the email draft.  
	
the data is in /data/playstore.csv


2. **The response loop.** A queue of incoming user questions. Each one runs through the three agents in parallel, the orchestrator, and the reviewer, producing a reply draft with its citation and an internal routing note. A human approves, edits, or rejects each draft.

Build the corpus from the below links
1. https://groww.in/pricing
	2. https://groww.in/help
	3. https://groww.in/help/mutual-funds
	4. https://groww.in/help/payments	5.https://groww.in/help/stocks,-f&o,-ipo-&-mtf/searchable/when-are-dp-charges-levied	6.https://groww.in/help/my-account/payments/how-do-i-withdraw-money-from-my-groww-account-2	7.https://groww.in/help/stocks,-f&o,-ipo-&-mtf/sx-demat-account/where-can-i-see-my-demat-account-number
	8.a)https://groww.in/mutual-funds/sbi-large-cap-direct-plan-growth
	  b)https://groww.in/mutual-funds/sbi-flexicap-fund-direct-growth
	  c)https://groww.in/mutual-funds/sbi-elss-tax-saver-fund-direct-growth
	  d)https://groww.in/mutual-funds/sbi-contra-fund-direct-growth
	  e)https://groww.in/mutual-funds/sbi-small-midcap-fund-direct-growth

3. **The connection between them.** This is what neither milestone did on its own. When the response loop sees the same question five times in a week, it shows up in the weekly pulse. When the weekly loop identifies a fee confusion, the explainer becomes the canonical answer the response loop reuses instead of drafting fresh. Build this link and show it working.

4. **Scope enforcement.** Facts-only across both loops. No recommendations, no buy or sell language, no return or performance figures, no PII stored anywhere including logs and agent state. Enforced in code, not only in prompts.

## The interface

- A queue view of incoming questions with their draft replies, citations, and any reviewer flags.
- A weekly pulse view with the themes, quotes, and counts behind them.
- A sources panel showing where every factual claim came from, with its last-checked date.
- An approval screen listing exactly what will be written and where, before anything is written.
- A way to see the canonical fee explainers the response loop is reusing.

## Rules

- Every factual claim carries one source link from your Milestone 1 corpus.
- Public sources only. No third-party blogs, no app back-end screenshots.
- When the corpus doesn't cover a question, the system says so and names what it searched.
- Every theme traces to review ids, and every count states the window it covers.
- No PII anywhere in the dataset, the interface, the logs, or agent state.
- Nothing is written or sent without a human approving that specific action.
- Reply drafts stay at three sentences or fewer, the pulse at 250 words, the explainer at six bullets.

## Evaluations

Three checks minimum, running over the assembled system.

### Feasibility

Every question in the queue produces a draft or an explicit "not covered". Every theme carries review ids and a stated window. The pulse stays inside its word cap and the explainer inside its bullet cap. The weekly loop completes without manual intervention once triggered.

### Correctness of edits

A human edit to a draft changes only that draft. Approving one action doesn't trigger another. Rejecting a draft leaves the queue otherwise untouched. Test each and diff the state before and after.

### Grounding and compliance

Sample fifteen claims across both loops and confirm each traces to a source link or a review id. Feed in questions the corpus can't answer and confirm it says so. Then run advice requests, return-figure requests, and messages containing a PAN, an account number, and a phone number, in both loops, rephrased and repeated. Confirm every one is refused or redacted, and that nothing sensitive reached the logs.

## What to submit

- **The GitHub repo.** README covers the architecture and setup, your source list, where the approval gate sits, how the two loops connect, what fee issue came out of your reviews, how to run the evals, and known limits. Include the reviews CSV sample, five sample questions with their drafts, the appended doc entry, the email draft, and your evaluation results.
- **A working prototype link.** Hosted app or notebook.
- **A demo video under three minutes**, only if you can't host. Show the weekly loop running end to end, one question through the response loop, one reviewer rejection, the approval gate, and one evaluation.

## Evaluation rubric

| Area | Weight |
| --- | --- |
| Voice UX & intent handling | 25% |
| MCP usage & system design | 20% |
| Grounding & RAG quality | 15% |
| AI evals & iteration depth | 20% |
| Workflow automation | 10% |
| Deployment & code quality | 10% |

## What we're grading

Can you design a system where three data sources answer one question? Do you know where a language model stops being reliable, and does your system say so out loud? Can you build a gate that a compliance team would trust? Can you explain why you drew the lines where you did?

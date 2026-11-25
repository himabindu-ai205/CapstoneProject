from desk.intent import REFUSALS, classify_intent
from desk.topics import Topic, assign_topic, extract_charge_topics


def test_intent_order_pii_before_performance():
    assert classify_intent("My PAN is ABCDE1234F, what is the NAV?") == "pii"
    assert classify_intent("Should I buy SBI Large Cap?") == "advice"
    assert classify_intent("What is the CAGR of this fund?") == "performance"
    assert classify_intent("When are DP charges levied?") == "factual"
    assert classify_intent("When are DP charges levied on a sell?") == "factual"
    assert classify_intent("How much is the DP charge per sell?") == "factual"
    assert classify_intent("Do DP charges apply every time I sell shares?") == "factual"
    assert classify_intent("Should I sell this fund?") == "advice"
    assert classify_intent("Sell this fund") == "advice"
    assert REFUSALS["performance"].startswith("This desk states")
    assert "NAV" not in REFUSALS["performance"]


def test_topics_come_from_pricing_text_and_unknown_stays_unknown():
    topics = extract_charge_topics("Brokerage\nDP charges\n")
    topics += [Topic("payments.withdraw", "withdrawal"), Topic("account.demat", "demat")]
    assert assign_topic("Why was DP charged?", topics) == "fees.dp"
    assert assign_topic("How do I withdraw?", topics) == "payments.withdraw"
    assert assign_topic("The app logo is blue", topics) == "topic.unknown"

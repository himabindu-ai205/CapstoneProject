from desk.guards import bullet_count, redact, scope_flag, sentence_count, word_count


def test_redact_pan_phone_and_account():
    raw = "PAN ABCDE1234F phone 9876543210 account 1234567890123456"
    cleaned = redact(raw)
    assert "ABCDE1234F" not in cleaned
    assert "9876543210" not in cleaned
    assert "1234567890123456" not in cleaned
    assert "[PAN]" in cleaned and "[PHONE]" in cleaned and "[ACCOUNT]" in cleaned


def test_scope_allows_dp_sell_transaction_and_flags_advice():
    assert scope_flag("DP charges apply per sell transaction.") is None
    assert scope_flag("You should sell this fund.") == "scope"
    assert scope_flag("What is the NAV?") == "scope"


def test_caps():
    assert sentence_count("One. Two. Three.") == 3
    assert word_count("one two three") == 3
    assert bullet_count("- a\n- b\n- c") == 3

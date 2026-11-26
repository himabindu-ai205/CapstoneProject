from desk.guards import bullet_count, redact, scope_flag, sentence_count, word_count


def test_redact_pan_phone_and_account():
    raw = "PAN ABCDE1234F phone 9876543210 account 1234567890123456"
    cleaned = redact(raw)
    assert "ABCDE1234F" not in cleaned
    assert "9876543210" not in cleaned
    assert "1234567890123456" not in cleaned
    assert "[PAN]" in cleaned and "[PHONE]" in cleaned and "[ACCOUNT]" in cleaned


def test_redact_aadhaar_and_passport():
    raw = "aadhaar 1234 5678 9012 passport A1234567"
    cleaned = redact(raw)
    assert "1234 5678 9012" not in cleaned
    assert "A1234567" not in cleaned
    assert "[AADHAAR]" in cleaned and "[PASSPORT]" in cleaned
    assert redact("aadhaar 123456789012") == "aadhaar [AADHAAR]"
    assert redact("my aadhaar number is xy12") == "my aadhaar number is [AADHAAR]"
    assert redact("my passport no is xy12") == "my passport no is [PASSPORT]"


def test_redact_stated_pan_value_that_is_not_a_formal_pan():
    cleaned = redact("my pan number is xyx")
    assert "xyx" not in cleaned
    assert cleaned == "my pan number is [PAN]"


def test_scope_allows_dp_sell_transaction_and_flags_advice():
    assert scope_flag("DP charges apply per sell transaction.") is None
    assert scope_flag("You should sell this fund.") == "scope"
    assert scope_flag("What is the NAV?") == "scope"


def test_caps():
    assert sentence_count("One. Two. Three.") == 3
    assert word_count("one two three") == 3
    assert bullet_count("- a\n- b\n- c") == 3

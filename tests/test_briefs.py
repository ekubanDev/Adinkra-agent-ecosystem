from research.briefs import Brief, validate_brief

GOOD = dict(symbol="Sankofa", meaning="go back and fetch it; learn from the past", product_type="poster",
            target_buyer="diaspora adults", angle="A calm reminder to learn from history.",
            style_direction="minimal line art, warm earth tones",
            keywords=["sankofa poster", "african heritage wall art", "adinkra print", "gift for her", "meaningful art"])


def test_good_brief_passes():
    assert validate_brief(Brief(**GOOD)) == []


def test_unknown_symbol_rejected():
    assert any("unknown symbol" in p for p in validate_brief(Brief(**{**GOOD, "symbol": "Madeup"})))


def test_wrong_meaning_rejected():
    assert any("does not match" in p for p in validate_brief(Brief(**{**GOOD, "meaning": "something else"})))


def test_banned_term_rejected_whole_word_only():
    assert any("nike" in p for p in validate_brief(Brief(**{**GOOD, "angle": "Looks like a Nike ad."})))
    assert validate_brief(Brief(**{**GOOD, "angle": "A bunker of knowledge."})) == []  # no false hit inside words


def test_bad_product_type_rejected():
    assert any("product_type" in p for p in validate_brief(Brief(**{**GOOD, "product_type": "hoodie"})))

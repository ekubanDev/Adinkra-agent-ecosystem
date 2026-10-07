from rooms.etsy_pod.listing import DISCLOSURE, policy_check
from rooms.etsy_pod.pricing import margin_pct, meets_floor, price_for

BRIEF = {"meaning": "go back and fetch it; learn from the past"}


def good_copy(**kw):
    c = {"title": "Sankofa Poster", "tags": [f"tag{i}" for i in range(10)],
         "description": "Sankofa means go back and fetch it." + DISCLOSURE}
    c.update(kw)
    return c


def test_price_hits_target_and_ends_99():
    p = price_for(12.43)
    assert round(p * 100) % 100 == 99 and margin_pct(p, 12.43) >= 45


def test_floor():
    assert meets_floor(24.99, 12.43) and not meets_floor(15.99, 12.43)


def test_policy_ok():
    assert policy_check(good_copy(), BRIEF) == []


def test_policy_blocks_banned_missing_disclosure_and_meaning():
    assert any("banned" in p for p in policy_check(good_copy(title="Nike style poster"), BRIEF))
    assert any("disclosures" in p for p in policy_check(good_copy(description="Sankofa means go back and fetch it."), BRIEF))
    assert any("meaning" in p for p in policy_check(good_copy(description="Nice art." + DISCLOSURE), BRIEF))


def test_sankofa_prompt_carries_form_notes_and_no_stands():
    from rooms.etsy_pod.artwork import art_prompt
    base = {"product_type": "poster", "meaning": "m", "style_direction": "s", "angle": "a", "avoid": []}
    p = art_prompt({**base, "symbol": "Sankofa"})
    assert "turned backward" in p and "pedestal" in p
    assert "Required form" not in art_prompt({**base, "symbol": "Aya"})

from rooms.etsy_pod.marketing import format_pack, tracked_url, validate_pack

MEANING_HEAD = "go back and fetch it"


def good():
    return {
        "pins": [{"title": f"Sankofa wall art {i}", "description": "A calm reminder to learn from the past.", "board": "Adinkra wall art"} for i in range(3)],
        "captions": [{"text": "Go back and fetch it.", "hashtags": ["adinkra", "sankofa", "africanart", "walldecor"]} for _ in range(2)],
        "story": f"Sankofa means {MEANING_HEAD}: the past teaches the present.",
    }


def test_good_pack_passes():
    assert validate_pack(good(), "Sankofa") == []


def test_forbidden_claims_and_banned_terms_blocked():
    p = good(); p["captions"][0]["text"] = "Our bestseller, selling fast!"
    assert any("forbidden" in x for x in validate_pack(p, "Sankofa"))
    p = good(); p["pins"][0]["title"] = "Nike style Sankofa"
    assert any("banned" in x for x in validate_pack(p, "Sankofa"))


def test_story_must_state_meaning_and_shape_must_be_right():
    p = good(); p["story"] = "A nice symbol."
    assert any("meaning" in x for x in validate_pack(p, "Sankofa"))
    p = good(); p["pins"] = p["pins"][:2]
    assert validate_pack(p, "Sankofa")


def test_tracked_url_and_pack_text():
    assert tracked_url("https://x.myshopify.com/products/a", "pinterest", "abc").endswith("utm_source=pinterest&utm_medium=social&utm_campaign=abc")
    assert "?" in tracked_url("https://x/p?v=1", "s", "d") and "&utm_source" in tracked_url("https://x/p?v=1", "s", "d")
    text = format_pack(good(), "https://x.myshopify.com/products/a", "abc", "Sankofa")
    assert "AI-generated" in text and "utm_campaign=abc" in text and "#sankofa" in text

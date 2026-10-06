"""Brief + approved image -> unpublished Printify draft with correct prices. Never publishes."""
from .listing import policy_check
from .pricing import FLOOR_PCT, meets_floor, price_for

# kind -> (blueprint, provider, variant filter). Providers chosen from docs/COSTS.md; revisit as data comes in.
PRODUCTS = {
    "poster": (282, 99, lambda v: v["options"].get("size") in ("11″ x 14″", "12″ x 18″", "16″ x 20″")),
    "mug": (68, 1, lambda v: True),
    "tee": (145, 50, lambda v: v["options"].get("color") in ("Black", "White") and v["options"].get("size") in ("S", "M", "L", "XL")),
}
PROVISIONAL_PRICE_CENTS = 9999  # replaced after real costs are read


class Rejected(Exception):
    pass


async def create_draft(brief: dict, copy: dict, image: bytes, gate: dict, printify) -> dict:
    if gate.get("decision") not in ("pass", "pass_unverified_shape"):
        raise Rejected(f"quality gate: {gate.get('decision')} ({gate.get('reason') or gate.get('checks')})")
    problems = policy_check(copy, brief)
    if problems:
        raise Rejected("policy gate: " + "; ".join(problems))
    bp, pv, keep = PRODUCTS[brief["product_type"]]
    variants = [v for v in await printify.variants(bp, pv) if keep(v)]
    if not variants:
        raise Rejected("no variants matched the product filter")
    ids = [v["id"] for v in variants]
    img = await printify.upload_image(f"{brief['symbol'].lower().replace(' ', '_')}.png", image)
    pos = variants[0]["placeholders"][0]["position"]
    prod = await printify.create_product({
        "title": copy["title"], "description": copy["description"], "tags": copy["tags"],
        "blueprint_id": bp, "print_provider_id": pv,
        "variants": [{"id": i, "price": PROVISIONAL_PRICE_CENTS, "is_enabled": True} for i in ids],
        "print_areas": [{"variant_ids": ids, "placeholders": [
            {"position": pos, "images": [{"id": img["id"], "x": 0.5, "y": 0.5, "scale": 1, "angle": 0}]}]}],
    })
    # real costs are only known now: set prices from them, enforce the margin floor, else delete the draft
    new, report = [], []
    for v in prod["variants"]:
        if v["id"] not in ids:
            continue
        cost = v["cost"] / 100
        price = price_for(cost)
        if not meets_floor(price, cost):
            await printify.delete_product(prod["id"])
            raise Rejected(f"margin below {FLOOR_PCT}% for variant {v['id']} (cost {cost})")
        new.append({"id": v["id"], "price": round(price * 100), "is_enabled": True})
        report.append((v.get("title"), cost, price))
    await printify.update_product(prod["id"], {"variants": new})
    return {"product_id": prod["id"], "published": False, "variants": report,
            "shape_verified": gate.get("decision") == "pass"}

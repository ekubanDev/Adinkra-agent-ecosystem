"""Pricing and margin rule. Fees are ASSUMPTIONS until checked against the real Shopify plan and Paystack rates."""
import math

FEE_PCT = 7.0            # combined Shopify + Paystack, UNVERIFIED (see docs/COSTS.md)
TARGET_MARGIN_PCT = 45.0
FLOOR_PCT = 30.0         # keep in step with MARGIN_FLOOR_PCT in .env


def margin_pct(price: float, cost: float, fee_pct: float = FEE_PCT) -> float:
    """Margin on the item price; shipping is charged to the buyer and excluded."""
    if price <= 0:
        return -100.0
    return (price - cost - price * fee_pct / 100) / price * 100


def price_for(cost: float, target_pct: float = TARGET_MARGIN_PCT, fee_pct: float = FEE_PCT) -> float:
    """Smallest x.99 price that reaches the target margin."""
    raw = cost / (1 - fee_pct / 100 - target_pct / 100)
    return math.ceil(raw) - 0.01


def meets_floor(price: float, cost: float, floor_pct: float = FLOOR_PCT, fee_pct: float = FEE_PCT) -> bool:
    return margin_pct(price, cost, fee_pct) >= floor_pct

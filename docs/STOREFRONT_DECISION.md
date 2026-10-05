# Storefront decision (Phase 0 blocker)

Status: **recommendation, not yet decided.** Researched 5 Oct 2026.

## Options

| | Etsy via Printify | Shopify via Printify |
| --- | --- | --- |
| Can a Ghana-resident seller open it? | **No.** Ghana is not on Etsy's Payments list, nor on the Payoneer list. Where Etsy Payments is unavailable you generally cannot open a shop. | Yes. Shopify serves Ghana. |
| Getting paid | Needs an eligible-country address and bank account. Using someone else's is not acceptable. | Paystack is a supported Shopify gateway for Ghana: cards, bank transfer, mobile money, settled in GHS. |
| Traffic | Built-in marketplace search. | None built in. Needs ads, SEO or social, which costs money and time. |
| Fits our automation | Printify publishes directly. | Printify publishes directly; the same Printify API. |
| Rules that matter | Creativity Standards, AI disclosure, IP takedowns. | Fewer platform rules, but payment-provider and ad-platform rules still apply. |

## Recommendation

**Shopify + Printify + Paystack.** It is the only route available today without borrowing an address or account. The cost is traffic: Etsy's marketplace search is what made the original plan attractive, and Shopify has no equivalent. Phase 2's "earns more than it costs" gate must therefore include an ad/traffic budget, and a Research Lab task becomes finding low-cost traffic (SEO, Pinterest, TikTok), not only demand.

The code already keeps the storefront behind an interface (see CLAUDE.md), so Etsy can be added later if you set up a legitimate presence in an eligible country.

## Not yet verified (check before committing money)

- Whether Shopify Payments itself is available in Ghana. Not confirmed; assume Paystack is the payment route.
- How Printify bills you for production costs from Ghana (card or PayPal on file) and whether your card works. Test with a small order.
- Paystack account approval requirements for a Ghana business (registration, ID).
- Shopify plan cost and transaction fees versus Etsy's 6.5% + $0.20 listing fee, to update the margin floor.
- Tax and business registration for selling to US/EU customers from Ghana: ask a local accountant.

## Next actions (yours)

1. Confirm the route.
2. Open a Shopify store (trial) and connect Paystack.
3. Connect the Printify shop `29202876` to Shopify, then re-run `scripts/check_keys.py`: the shop should stop showing `disconnected`.

# Test order checklist

Purpose: prove, with one real purchase, the four things nothing else can: (1) a customer can pay through Paystack, (2) the order reaches Printify and Printify bills us correctly from Ghana, (3) the money reaches you and what it really costs, (4) the report reads real orders correctly. It also replaces the assumed 7% fee with the real number.

Never put card numbers, API keys or passwords in chat. Order numbers and amounts are fine.

## Before you order
- [ ] Live product to buy: the **Gye Nyame tee** (`34823ef6`): `https://e7iyv1-4x.myshopify.com/products/gye-nyame-adinkra-faith-tee-ghanaian-heritage-design`
- [ ] Pick the cheapest variant (small). Expected production cost about **$12.43**; expected price about **$25.99** (set by the margin rule; check what Shopify actually shows).
- [ ] Choose a delivery address in a country the tee provider ships to. Printify's US shipping for this provider is about $4.49 for the first item. **Shipping to Ghana may not be offered:** if checkout does not offer your country, use an address in the US or UK (a friend or relative), or order to yourself if you have one.
- [ ] Check Shopify's **shipping rates** (Settings > Shipping and delivery). Nothing in our pipeline sets them. If a destination has no rate, buyers cannot check out.
- [ ] Check Printify has a **payment method** on file (Account > Billing) that works from Ghana.
- [ ] Note the store currency (Shopify Settings > Store details) and what currency Paystack settles in. A currency mismatch changes the fee.
- [ ] Switch off Shopify's password page if it is on (Online Store > Preferences), or you will not see the storefront as a customer would.

## Place the order (as a customer)
- [ ] Open the product page in a private browser window. Check: mockup images look right, price and sizes show, description includes the AI-use and Printify production-partner lines.
- [ ] Add to cart, go to checkout, pay with **Paystack**. Note the amount you were charged (item + shipping + tax, if any).
- [ ] Save the Shopify **order number** and the Paystack **transaction reference**.

## What to check after
Within minutes to hours:
- [ ] **Shopify:** the order appears as paid.
- [ ] **Paystack dashboard:** the transaction shows as successful. Note the **fee Paystack charged** and the **settlement amount and date**.
- [ ] **Printify:** the order appears under Orders for shop "My Shopify Store". Note its status (on hold, in production, shipped) and what Printify **charged us** (production + shipping).
- [ ] **Our report:** ask the Overseer "report", or open `http://localhost:8000/report?days=7`. It should show 1 order and a revenue figure. If it shows a warning that an order had no readable price, tell me: the parser needs adjusting.
- [ ] **Tracking:** when it ships, a tracking number should reach the buyer's email.

## What to send me (numbers only)
1. Price shown on the product page, shipping charged to the buyer, total paid.
2. Paystack fee and the amount that will be settled to you (and when).
3. Printify's charge for the order (production, shipping).
4. What `/report` shows.

From these I will compute the real fee percentage, update `FEE_PCT` in `rooms/etsy_pod/pricing.py` and `control/app/report.py`, and re-check every margin.

## If something goes wrong
- **Checkout fails or has no shipping option:** fix Shopify shipping rates first. Not a code problem.
- **Order paid but missing in Printify:** check the Printify app is still connected to Shopify (Settings > Connections). Tell me what Printify's order list shows.
- **Printify cannot charge you:** fix billing in Printify before anything else sells.
- **You do not want it shipped:** Printify lets you cancel an order before it goes to production. You then verify payment but not fulfilment, so you will still not know delivery works.
- **Refund:** refunds are done in Shopify (and Paystack). Note the fee may not be returned.

## Not covered by this test
Tax and business registration for selling abroad (ask a local accountant), returns handling, customer support, the quality of the printed shirt itself (you will see that when it arrives), and whether anyone finds the shop.

---
name: money-arithmetic
description: Use whenever code computes prices, taxes, discounts or totals in the shop package.
---

# Money arithmetic in integer cents

All amounts are `int` cents. Rates are integer basis points (1% = 100 bps).

- Round DOWN (floor):       `amount * bps // 10_000`
- Round HALF UP (nearest):  `(amount * bps + 5_000) // 10_000`
- Clamp at zero:            `max(0, amount)`

Never convert to float, even temporarily. Write tests with values that hit the
rounding edge (e.g. 50 cents at 21% = 10.5 -> 11 with half-up).

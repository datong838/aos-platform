---
name: pricing-strategy
description: >
  Use when helping sellers calculate landed costs, set profitable prices, evaluate
  promotion profitability, perform break-even analysis, or adjust pricing in response
  to market and cost changes for cross-border e-commerce products.
---

# Pricing Strategy

A technique and reference skill for cross-border e-commerce pricing. This skill guides
AI agents through the complete pricing workflow: from raw cost calculation through
competitive positioning to dynamic repricing. Every recommendation must be grounded
in verified numbers, never in intuition alone.

---

## The Pricing Iron Law

**Never set a price without calculating the full landed cost including ALL fees,
shipping, duties, advertising allocation, and returns reserve. A product priced
without accounting for all costs is donating money to the platform.**

Every pricing conversation must begin with cost. If a seller asks "What price should
I set?" and cannot provide cost data, redirect them to complete a cost calculation
first. Price without cost is guesswork.

---

## The Margin Stack

The margin stack shows how a selling price is consumed layer by layer. Every price
must survive the full stack with positive net profit remaining.

```
Selling Price (100%)
 minus Platform Referral Fee .............. (8-15%)
 minus Fulfillment Fee .................... (10-25%)
 minus Shipping to Warehouse .............. (5-15%)
 minus Customs Duties & Tariffs ........... (0-25%)
 minus COGS (factory + packaging) ......... (20-40%)
 minus Advertising Allocation ............. (8-15%)
 minus Returns Reserve .................... (2-8%)
 minus Payment Processing Fee ............. (2-4%)
 minus VAT/GST (if absorbed) .............. (0-20%)
 ─────────────────────────────────────────
 = Net Profit .............................. TARGET: 10-25%
```

If net profit is below 10%, the product is fragile. Any cost shock (freight rate
increase, currency move, storage surcharge) will push it into loss territory.

---

## Landed Cost Calculation Steps

Follow these steps in order. Do not skip any.

### Step 1: Establish COGS
- Factory/purchase price per unit (FOB or EXW)
- Packaging and labeling cost per unit
- Quality inspection cost allocated per unit
- MOQ-driven unit cost (confirm price tier matches actual order quantity)

### Step 2: Calculate Freight Cost Per Unit
- Determine shipping method (sea, air, rail, express)
- Get total freight quote for the shipment
- Divide by number of units to get per-unit freight cost
- Include insurance (typically 0.3-0.5% of declared value)

### Step 3: Calculate Duties and Import Taxes
- Identify HS code for the product
- Look up duty rate for destination country
- Calculate: `Duty = (COGS + Freight + Insurance) x Duty Rate`
- Add any anti-dumping duties if applicable
- Add customs brokerage fee allocated per unit

### Step 4: Add Platform Fees
- Referral/commission fee (percentage of selling price)
- Fulfillment fee (per unit, based on size and weight tier)
- Monthly storage fee (allocated per unit based on turnover rate)
- Long-term storage surcharge (if inventory age > 180/365 days)

### Step 5: Allocate Advertising Cost
- Use TACOS (Total Advertising Cost of Sales) target
- Per-unit ad cost = `Selling Price x TACOS%`
- New products: budget 15-25% TACOS for launch phase
- Mature products: target 8-12% TACOS

### Step 6: Reserve for Returns
- Apply category-specific return rate (see benchmarks below)
- Per-unit returns cost = `Return Rate x (Selling Price + Return Shipping + Restock)`
- Unsalvageable returns: add disposal/loss factor

### Step 7: Add Payment Processing
- Platform payment processing: typically 2-3.5%
- Currency conversion fee: 1-3.5% if settling in different currency

### Step 8: Calculate Net Margin
```
Net Margin = Selling Price
           - COGS
           - Freight per unit
           - Duties per unit
           - Platform referral fee
           - Fulfillment fee
           - Storage allocation
           - Ad cost allocation
           - Returns reserve
           - Payment processing fee
           - VAT/GST (if seller-absorbed)
```

If Net Margin < 10% of Selling Price, reconsider the product or find cost reductions.

See `references/cost-calculator.md` for the complete formula and worked examples.

---

## Competitive Pricing Framework

Choose a strategy based on product lifecycle stage, differentiation level, and
business objectives.

### Strategy 1: Penetration Pricing
- **When:** New product launch, need reviews and ranking velocity
- **Price position:** 10-20% below category average
- **Margin target:** 5-10% (temporarily acceptable)
- **Duration:** 2-8 weeks, with defined exit criteria
- **Exit criteria:** Target review count reached, BSR milestone hit, or budget exhausted
- **Risk:** Training customers on low price; must plan price increase path
- **Guard rail:** Never go below breakeven unless there is a documented customer
  acquisition strategy with payback period

### Strategy 2: Parity Pricing
- **When:** Established product with comparable quality to competitors
- **Price position:** Within 5% of top 5 competitors' average
- **Margin target:** 15-20%
- **Duration:** Steady state
- **Optimization:** Win on listing quality, images, A+ content, reviews rather than price
- **Guard rail:** Monitor competitor price changes weekly; adjust only if sustained shift

### Strategy 3: Premium Pricing
- **When:** Differentiated product, strong brand, unique features or bundling
- **Price position:** 15-40% above category average
- **Margin target:** 25-35%
- **Duration:** Sustainable as long as differentiation holds
- **Requirements:** Superior listing assets, brand registry, strong review profile
- **Guard rail:** Track conversion rate; if it drops below category average by >30%,
  differentiation may not justify the premium

---

## Promotion / Discount Profitability Check

Before running any promotion, complete this check.

### Pre-Promotion Calculation
```
Promo Price           = Regular Price x (1 - Discount%)
Promo Revenue/unit    = Promo Price - Platform Fee on Promo Price
Promo Cost/unit       = COGS + Freight + Duty + Fulfillment + Ad Cost + Returns Reserve
Promo Profit/unit     = Promo Revenue/unit - Promo Cost/unit
```

### Promotion Decision Rules

1. **Promo Profit > 0:** Promotion is self-funding. Approve.
2. **Promo Profit < 0 but > -$2/unit:** Acceptable only if:
   - Launch phase with defined review/ranking target
   - Inventory clearance to avoid long-term storage fees
   - Loss is less than the storage fees saved
3. **Promo Profit < -$2/unit:** Reject unless seller provides written acquisition
   strategy with payback calculation.

### Lightning Deal / Coupon Specific Checks
- Lightning Deal fee: add $150-300 per deal (Amazon US) to total promo cost
- Coupons: add $0.60 per clip (Amazon US) to per-unit cost
- Always calculate total maximum exposure: `Max Units x Loss per Unit + Deal Fee`

---

## Break-even Analysis

### Simple Break-even Price
```
Break-even Price = Total Variable Cost per Unit / (1 - Platform Fee%)
```

Where Total Variable Cost = COGS + Freight + Duty + Fulfillment + Ad Allocation +
Returns Reserve + Payment Processing

### Break-even Units (for fixed cost recovery)
```
Break-even Units = Fixed Costs / (Selling Price - Variable Cost per Unit)
```

Fixed costs include: initial inventory purchase, product photography, listing creation,
trademark registration, initial ad spend for launch.

### Monthly Break-even
```
Monthly Break-even Units = Monthly Fixed Costs / Contribution Margin per Unit
```

Monthly fixed costs: storage fees, software subscriptions, VA costs, PPC base spend.

---

## Dynamic Pricing Triggers

Monitor these signals and adjust prices accordingly.

| Trigger | Direction | Action |
|---------|-----------|--------|
| Inventory age approaching 180 days (FBA) | Down | Reduce price 10-20% or run promotion to clear before long-term storage fee |
| Competitor stockout (top 3) | Up | Increase price 5-15% while monitoring conversion rate |
| Currency depreciation > 5% (sourcing currency) | Up | Raise price to maintain margin; phase in over 2 weeks |
| TACOS increasing above target for 2+ weeks | Review | Either raise price (absorb higher CPC) or reduce ad spend |
| Seasonal demand surge approaching | Up | Raise price 5-10% before peak; do not wait until peak starts |
| New tariff or duty rate announced | Up | Calculate exact cost impact; adjust price before effective date |
| Conversion rate drop > 20% week-over-week | Down/Review | Investigate cause first; price cut is last resort |
| BSR improving without price change | Hold | Do not change a winning position |

---

## Quick Reference: Margin Benchmarks by Category

These are target net margins after ALL costs. Actual margins vary by product, platform,
and market.

| Category | Target Net Margin | Typical Return Rate | Notes |
|----------|------------------|--------------------:|-------|
| Electronics & Accessories | 15-25% | 3-8% | Watch for IP complaints; higher ad costs |
| Home & Kitchen | 18-30% | 3-6% | Bulky items have higher fulfillment costs |
| Beauty & Personal Care | 20-35% | 2-5% | Compliance costs; high repeat purchase potential |
| Apparel & Fashion | 15-25% | 15-30% | Returns are the margin killer; size charts critical |
| Toys & Games | 15-25% | 3-7% | Extreme seasonality; plan storage carefully |
| Pet Supplies | 20-30% | 2-5% | Loyal customer base; subscription potential |
| Sports & Outdoors | 15-25% | 5-10% | Seasonal peaks; size/weight impact on shipping |
| Office Products | 15-25% | 2-5% | Competitive; often commodity-like pricing |
| Health & Household | 20-30% | 2-5% | Compliance and restricted category hurdles |
| Baby Products | 18-28% | 3-8% | Safety compliance costs; trust-driven purchase |

---

## Red Flags / Common Mistakes

1. **Pricing based on competitor price without calculating own cost.**
   A competitor may have lower COGS, different fulfillment, or be liquidating. Their
   price is not your floor. Always start from your cost stack.

2. **Forgetting FBA storage fees (compound during slow seasons).**
   Monthly storage fees double from January to September (Amazon US). Products that
   sit 180+ days incur aged inventory surcharges. A "profitable" product can bleed
   margin through storage alone. Model inventory turnover in your cost calculation.

3. **Not reserving margin for returns (2-8%).**
   Returns are not a cost surprise; they are a predictable cost line. Apparel sellers
   who do not reserve 15-30% for returns will show paper profits and real losses.
   Build the reserve into the price from day one.

4. **Running below-breakeven promotions without acquisition strategy.**
   A loss-leader promotion is an investment, not a sale. If there is no plan for how
   the acquired customers or ranking position will generate future profit, the
   promotion is simply a loss. Require a payback period calculation.

5. **Ignoring currency fluctuation impact on COGS.**
   A 5% depreciation of the seller's settlement currency against the sourcing currency
   (e.g., USD weakening against CNY) directly increases COGS by 5%. Set a currency
   review trigger and reprice within 2 weeks of significant moves. Consider forward
   contracts for large orders.

---

## Cross-references

- **PREREQUISITE:** `cbec-ops:product-selection` -- Product viability assessment must
  confirm sufficient margin potential before detailed pricing work begins.
- **PREREQUISITE:** `cbec-ops:supplier-sourcing` -- Accurate COGS from verified suppliers
  is the foundation of every pricing calculation in this skill.
- **RELATED:** `cbec-ops:financial-management` -- Financial management covers P&L
  tracking, cash flow planning, and tax obligations that depend on pricing decisions.
- **RELATED:** `cbec-ops:advertising-marketing` -- Advertising costs are a major margin
  component; TACOS targets set here must align with ad strategy.

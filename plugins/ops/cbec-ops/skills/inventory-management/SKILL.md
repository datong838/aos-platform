---
name: inventory-management
description: >
  Use when the seller asks about planning stock orders, calculating reorder
  points, managing FBA or 3PL inventory, dealing with stockouts or overstock
  situations, planning inventory for peak seasons, or optimizing inventory
  health metrics like IPI score.
---

# Inventory Management: Plan Stock Levels and Optimize Warehouse Operations

Help sellers maintain the right amount of inventory at the right time across
warehouses, FBA fulfillment centers, and 3PL partners. Inventory management
bridges supplier sourcing (inbound) and order fulfillment (outbound) -- it is
the operational heartbeat of a cross-border e-commerce business.

## Core Principle

> **Inventory is cash sitting on a shelf. The goal is not maximum stock, but
> minimum stock that prevents stockouts. Every excess unit costs money in
> storage, capital, and obsolescence risk.**

A stockout loses today's revenue and tomorrow's ranking. Overstock loses
capital, incurs storage fees, and forces liquidation at a loss. The optimal
inventory position is the narrowest band between these two failure modes.

For most cross-border sellers, the cost of overstock exceeds the cost of a
brief stockout. A 2-day stockout on Amazon may drop your BSR temporarily, but
60 days of long-term storage fees on 3,000 excess units will erase a quarter's
profit. Err on the lean side and replenish frequently rather than in large
batches -- unless your supply chain lead time forces bulk ordering.

---

## Core Formulas

These three formulas form the foundation of inventory planning. Worked examples
and spreadsheet implementations are in `references/reorder-formulas.md`.

### 1. Reorder Point (ROP)

The inventory level at which you must place a new purchase order to avoid
stockout.

```
Reorder Point = (Average Daily Sales x Lead Time in Days) + Safety Stock
```

- **Average Daily Sales:** Use 30-day or 60-day trailing average, weighted
  toward recent weeks if trend is changing.
- **Lead Time:** Total days from PO placement to units available for sale.
  For cross-border FBA, this includes production + shipping + customs +
  FBA receiving (typically 30-60 days from China to US FBA).
- **Safety Stock:** Buffer for demand variability and lead time variability
  (see below).

### 2. Safety Stock

Extra inventory held to absorb demand spikes and supply delays.

```
Safety Stock = Z x sqrt((Lead Time x Demand Variance) + (Avg Daily Sales^2 x Lead Time Variance))
```

Where:
- **Z** = Z-score for desired service level (1.28 for 90%, 1.65 for 95%,
  2.33 for 99%)
- **Lead Time** = average lead time in days
- **Demand Variance** = variance of daily demand (standard deviation squared)
- **Avg Daily Sales** = mean daily unit sales
- **Lead Time Variance** = variance of lead time in days

**Simplified version** (when lead time is stable):

```
Safety Stock = Z x Standard Deviation of Daily Demand x sqrt(Lead Time)
```

For most cross-border sellers, the simplified formula is sufficient. Use the
full formula only when your lead time varies significantly (e.g., ocean freight
during port congestion seasons).

### 3. Economic Order Quantity (EOQ)

The order quantity that minimizes total inventory cost (ordering cost + holding
cost).

```
EOQ = sqrt((2 x Annual Demand x Order Cost) / Holding Cost per Unit per Year)
```

Where:
- **Annual Demand** = projected units sold per year
- **Order Cost** = fixed cost per order (freight booking, customs brokerage,
  inspection fees, wire transfer fees)
- **Holding Cost per Unit per Year** = storage fees + capital cost + insurance
  + obsolescence risk (typically 20-35% of unit cost for FBA sellers)

**Important caveat:** EOQ assumes stable demand and unlimited supplier
capacity. For seasonal products or capacity-constrained suppliers, adjust
manually. EOQ is a starting point, not a ceiling.

---

## Demand Forecasting Methods

Accurate demand forecasting reduces both stockouts and overstock. Use the
simplest method that fits your data.

### Method 1: Simple Moving Average (SMA)

Best for: Stable-demand products with 3+ months of sales history.

```
Forecast = Average of last N periods (typically 30, 60, or 90 days)
```

Use 30-day SMA for fast-moving products. Use 90-day SMA for slow-moving or
variable products. SMA reacts slowly to trend changes.

### Method 2: Weighted Moving Average (WMA)

Best for: Products with emerging trends (accelerating or decelerating sales).

```
Forecast = (Weight1 x Period1 Sales) + (Weight2 x Period2 Sales) + ...
```

Typical weights for a 3-month WMA:
- Last month: 50%
- Two months ago: 30%
- Three months ago: 20%

WMA gives more influence to recent data, making it more responsive than SMA.

### Method 3: Seasonal Adjustment

Best for: Products with predictable seasonal patterns (Q4 peak, summer
products, holiday items).

```
Seasonal Forecast = Base Forecast x Seasonal Index
```

Where **Seasonal Index** = (Average sales in target month across prior years) /
(Average monthly sales across all months).

Example: If December historically sells 2.5x the annual monthly average, the
seasonal index for December is 2.5. Apply this multiplier to your base
forecast.

**When you lack historical data:** Use category-level seasonality from Amazon
Brand Analytics or third-party tools (Jungle Scout, Helium 10) as a proxy.

### Method 4: New Product Launch (No History)

For products with zero sales data:
1. Find 3-5 comparable ASINs (similar category, price, review count).
2. Estimate their daily sales using BSR-to-sales estimators or Jungle Scout.
3. Apply a conservative discount (50-70% of comparable sales for month 1).
4. Order 30-45 days of projected supply for the initial shipment.
5. Reforecast after 14 days of live sales data.

---

## FBA Inventory Planning Workflow

This section covers the high-level FBA planning cycle. For detailed step-by-step
procedures, labeling requirements, and IPI optimization, load
`references/fba-playbook.md`.

### Planning Cycle (Repeat Every 2 Weeks)

```
Step 1: Pull current FBA inventory snapshot
  |
  +--> Seller Central > Inventory Planning > Restock Inventory
  +--> Download "Restock Report" or use SP-API inventory endpoints
  |
Step 2: Calculate days of supply for each SKU
  |
  +--> Days of Supply = Available Units / Average Daily Sales (7-day or 30-day)
  |
Step 3: Flag SKUs needing action
  |
  +--> < 14 days of supply  --> URGENT: Expedite shipment or air freight
  +--> 14-30 days of supply --> PLAN: Create shipment within 1 week
  +--> 30-60 days of supply --> MONITOR: Order from supplier if lead time > 30 days
  +--> > 90 days of supply  --> REVIEW: Risk of LTSF; consider promotions or removal
  |
Step 4: Create replenishment POs
  |
  +--> Order Quantity = (Target Days of Supply x Avg Daily Sales) - In-Transit - Available
  +--> Target Days of Supply: 45-60 days for ocean freight, 21-30 days for air freight
  |
Step 5: Track inbound shipments
  |
  +--> Monitor FBA receiving times (currently 5-14 days)
  +--> Factor receiving delay into your lead time calculation
```

### FBA-Specific Considerations

- **Restock limits:** Amazon caps how many units you can send per storage type
  (standard, oversize, apparel, etc.). Restock limits are recalculated weekly
  based on your IPI score and sales velocity. Monitor via Seller Central >
  Inventory Performance > Restock Limits.
- **Receiving delays:** FBA warehouses can take 5-14 business days to receive
  and check in inventory. During Q4 peak, this can extend to 21+ days. Plan
  shipments to arrive 3 weeks before you need units available.
- **Commingled vs. merchant-fulfilled:** Default to merchant-fulfilled (use
  your own FNSKU labels) to avoid commingling with counterfeit inventory from
  other sellers.

---

## Inventory Health Dashboard

Track these metrics weekly to maintain healthy inventory and avoid penalties.

### Inventory Performance Index (IPI)

Amazon's composite score (0-1000) measuring inventory health. Scores below 400
trigger restock limits.

| Component               | Impact   | How to Improve                                    |
|--------------------------|----------|---------------------------------------------------|
| Excess inventory %       | High     | Run promotions, create removal orders, adjust price |
| Sell-through rate        | High     | Improve listing, increase ad spend, lower price    |
| Stranded inventory %     | Medium   | Fix listing errors, relist suppressed ASINs        |
| In-stock rate            | Medium   | Maintain consistent replenishment, avoid stockouts  |

**Target:** IPI > 500. Above 500 gives maximum restock limits. Below 400
triggers capacity restrictions that create a vicious cycle (cannot send enough
inventory, leading to stockouts, leading to lower sales).

### Aged Inventory

Units in FBA for 90+ days incur long-term storage fees (LTSF). Units at 271+
days incur the highest surcharge.

**Prevention:**
- Set a "sell by" date for each shipment (arrival date + 80 days).
- At day 60, if sell-through is below plan, activate promotions (coupons,
  Lightning Deals, outlet deals).
- At day 75, create a removal order for units you cannot sell through.
- At day 85, consider liquidation via Amazon's Liquidation program (recover
  5-10% of cost) rather than paying LTSF.

### Stranded Inventory

Units in FBA that cannot be sold because the listing is inactive, suppressed,
or missing.

**Common causes:**
- Listing suppressed due to compliance issue or missing information
- ASIN deactivated by Amazon
- Listing deleted by accident
- Brand registry dispute

**Resolution:** Check Stranded Inventory report in Seller Central > Inventory
Planning. Fix the listing issue or create a removal order within 30 days
(after 30 days, Amazon may dispose of stranded units).

---

## Multi-Warehouse Strategy

For sellers using multiple fulfillment channels (FBA + 3PL, or multiple 3PLs
across countries):

### When to Add a Second Warehouse

- **Trigger 1:** Single warehouse cannot meet delivery speed requirements for
  a significant customer segment (e.g., FBA US covers domestic, but you need
  EU delivery under 5 days).
- **Trigger 2:** Monthly sales exceed $50K and you can reduce shipping costs
  by positioning inventory closer to demand clusters.
- **Trigger 3:** Platform requires local warehousing (Shopee ID, Lazada TH
  prefer local fulfillment).

### Inventory Allocation Across Warehouses

```
Allocation per Warehouse = (Regional Demand Share x Total Order Quantity) + Regional Safety Stock
```

Example: If US accounts for 60% of sales and EU 40%, allocate 60% of your order
to US FBA and 40% to EU FBA (or EU 3PL). Apply safety stock separately for each
region because lead times differ.

### Multi-Warehouse Pitfalls

- **Inventory fragmentation:** Splitting inventory across 4+ warehouses
  reduces flexibility. A stockout in one region cannot be resolved by
  transferring from another (FBA does not allow cross-region transfers).
- **Increased complexity:** Each warehouse has different fee structures,
  receiving processes, and reporting formats. Consolidate tools using a
  multi-channel inventory management platform (Sellerboard, SoStocked,
  Linnworks).
- **Higher minimum stock:** Each warehouse requires its own safety stock,
  increasing total inventory investment. Only add warehouses when the delivery
  speed or cost savings justify the higher capital requirement.

---

## Stockout Recovery Plan

When a stockout occurs, fast recovery is critical to limit ranking damage.

### Immediate Actions (Day 0-1)

1. **Assess remaining supply chain inventory:**
   - Units at supplier (ready to ship?)
   - Units in transit (when arriving?)
   - Units at 3PL (transferable to FBA?)
2. **Activate backup fulfillment:**
   - Switch to FBM (Fulfilled by Merchant) if you have 3PL stock.
   - Use Amazon MCF or a 3PL with 2-day delivery to maintain Prime-like speed.
3. **Raise price temporarily** (optional): If you have limited units incoming,
   a 10-20% price increase slows demand and extends remaining inventory.

### Recovery Phase (Day 2-14)

4. **Expedite restocking:**
   - Air freight partial shipment to bridge the gap (expensive but preserves
     ranking).
   - Sea freight the bulk order on schedule.
5. **Adjust PPC:**
   - Reduce ad spend during stockout to avoid wasted clicks on
     out-of-stock listings.
   - Reactivate campaigns immediately when inventory is back.
6. **Monitor BSR recovery:**
   - After restock, BSR typically recovers 70-80% within 7-14 days if your
     listing fundamentals are strong.
   - Consider a relaunch coupon (15-25% off) for 3-5 days to accelerate
     velocity recovery.

### Post-Mortem

7. **Root cause analysis:**
   - Was the stockout caused by demand spike, supply delay, or planning error?
   - Adjust safety stock, lead time buffer, or forecast model accordingly.
8. **Update reorder point:** Increase safety stock by 20-30% for the SKU
   until two consecutive order cycles complete without issue.

---

## Overstock Liquidation Options

When you have excess inventory that is incurring storage fees or tying up
capital, act quickly. The longer you wait, the worse the recovery rate.

| Option | Recovery Rate | When to Use |
|--------|--------------|-------------|
| Promotions (coupons, deals, price cuts) | 60-100% | < 60 days in FBA |
| Off-Amazon channels (eBay, Walmart, TikTok Shop) | 40-80% | 60-90 days |
| Amazon Liquidation program | 5-15% | 90-180 days |
| Removal to 3PL / Donation | 0% (avoids fees) | > 180 days |
| Destroy | 0% (last resort) | When removal cost > unit value |

**Decision rule:** Act at day 60. By day 90, escalate to liquidation. Never let
units reach 271+ days (highest LTSF surcharge).

---

## Red Flags and Common Mistakes

### 1. Ordering Based on Gut Feeling Instead of Data

**The mistake:** "This product feels like it will sell well, so let's order
5,000 units."

**The reality:** Without data-driven demand forecasting, sellers routinely
over-order by 2-3x, tying up $10,000-$50,000 in slow-moving inventory.

**The fix:** Use the reorder point formula. Start with a conservative first
order (30-45 days of projected supply). Scale up only after validating actual
sell-through rate.

### 2. Ignoring Total Lead Time

**The mistake:** Using production time as the only lead time input. "My
supplier says 15 days, so I order 15 days before stockout."

**The reality:** Cross-border lead time includes: supplier production (15-30
days) + domestic freight to port (3-5 days) + ocean freight (18-35 days) +
customs clearance (2-7 days) + FBA receiving (5-14 days). True lead time is
often 45-90 days.

**The fix:** Map every step of your supply chain with realistic durations.
Add 20% buffer to each step. Track actual lead times and adjust quarterly.

### 3. Not Accounting for FBA Receiving Delays

**The mistake:** Planning restock based on the date inventory ships, not the
date it becomes available for sale.

**The reality:** FBA receiving can take 5-14 business days (longer during
peak season). Units in "Receiving" status cannot be sold. Many sellers
experience stockouts with thousands of units stuck in FBA receiving.

**The fix:** Add FBA receiving time to your lead time calculation. During Q4,
add an extra 7-10 day buffer. Ship to FBA 3 weeks before you need units live.

### 4. Treating All SKUs the Same

**The mistake:** Applying the same reorder point and safety stock to every
product.

**The reality:** A top-selling SKU generating $5,000/month deserves tighter
inventory management than a long-tail SKU selling 2 units/week. Over-investing
in safety stock for slow movers while under-investing for fast movers is a
common trap.

**The fix:** Apply ABC analysis:
- **A items** (top 20% of SKUs, ~80% of revenue): Tightest reorder points,
  highest service level (99%), weekly review cycle.
- **B items** (next 30%): Standard safety stock, 95% service level, biweekly
  review.
- **C items** (bottom 50%): Minimal safety stock, 90% service level, monthly
  review. Consider dropshipping or made-to-order for the slowest movers.

### 5. Ignoring Storage Fee Economics

**The mistake:** Keeping slow-moving inventory in FBA "just in case it sells"
while paying monthly storage fees and long-term storage surcharges.

**The reality:** FBA monthly storage fees are $0.87/cubic foot (standard,
Jan-Sep) to $2.40/cubic foot (standard, Oct-Dec). Long-term storage fees add
$6.90/cubic foot or $0.15/unit (whichever is greater) for units stored 271+
days. A $10 product with 60-cent monthly storage fee loses 6% of its value per
month just sitting in the warehouse.

**The fix:** Calculate the monthly cost of holding each SKU in FBA. If the
monthly storage cost exceeds 3% of the unit's selling price and the product
is not selling through within 60 days, liquidate or remove immediately.

### 6. Not Separating Inventory Planning from Purchasing

**The mistake:** The same person who decides "what to buy" also decides "how
much to buy," leading to confirmation bias (over-ordering products they are
emotionally invested in).

**The reality:** Inventory planning should be formula-driven and detached from
product selection enthusiasm.

**The fix:** Let the formulas decide quantity. Let the product team decide
which products. Review inventory plans against actual sell-through monthly and
adjust without emotional attachment.

---

## Cross-References

- **PREREQUISITE:** `cbec-ops:supplier-sourcing` -- Supplier lead times,
  production capacity, and minimum order quantities (MOQs) are critical inputs
  to inventory planning. You cannot calculate a reorder point without knowing
  your lead time. Establish reliable supplier timelines before building
  inventory models.

- **RELATED:** `cbec-ops:order-fulfillment` -- Inventory management feeds
  into fulfillment execution. Warehouse receiving, shipping carrier selection,
  and customs clearance timelines all affect inventory availability.

- **RELATED:** `cbec-ops:seasonal-planning` -- Seasonal demand spikes require
  adjusted safety stock, earlier reorder triggers, and pre-positioned
  inventory. Coordinate seasonal planning with inventory models 60-90 days
  before peak periods.

- **RELATED:** `cbec-ops:financial-management` -- Inventory is the largest
  working capital commitment for most sellers. Cash flow planning, inventory
  financing, and unit economics all depend on accurate inventory projections.

- **RELATED:** `cbec-ops:data-analytics` -- Sales velocity, conversion rates,
  and advertising impact data feed into demand forecasting. Use analytics
  dashboards to monitor sell-through rate and inventory health KPIs.

---

## Reference Data

For detailed procedures and calculation examples, load:

- `references/fba-playbook.md` -- Step-by-step FBA inventory operations:
  shipment creation, labeling, IPI optimization, LTSF avoidance, stranded
  inventory resolution, and restock limit management.
- `references/reorder-formulas.md` -- Worked examples for every formula in
  this skill, including Z-score tables, seasonal adjustment methods, and
  ready-to-use spreadsheet formulas.

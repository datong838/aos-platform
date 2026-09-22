# Inventory Calculation Reference with Worked Examples

A formula-by-formula reference for inventory planning calculations. Each
section includes the formula, variable definitions, a worked example, and
spreadsheet implementation.

## Table of Contents

1. [Reorder Point Formula](#1-reorder-point-formula)
2. [Safety Stock Calculation](#2-safety-stock-calculation)
3. [Economic Order Quantity (EOQ)](#3-economic-order-quantity-eoq)
4. [Days of Supply Calculation](#4-days-of-supply-calculation)
5. [Sell-Through Rate Calculation](#5-sell-through-rate-calculation)
6. [Seasonal Demand Adjustment Methods](#6-seasonal-demand-adjustment-methods)
7. [Lead Time Variability Accounting](#7-lead-time-variability-accounting)
8. [Worked Examples](#8-worked-examples)
9. [Spreadsheet Formulas](#9-spreadsheet-formulas)
10. [When to Override the Formulas](#10-when-to-override-the-formulas)

---

## 1. Reorder Point Formula

### Formula

```
Reorder Point (ROP) = (Average Daily Sales x Lead Time in Days) + Safety Stock
```

### Variables

| Variable | Definition | How to Calculate |
|----------|-----------|-----------------|
| Average Daily Sales | Mean units sold per day | Total units sold in last 30 days / 30 |
| Lead Time | Days from PO placement to units available for sale | Sum of production + shipping + customs + warehouse receiving |
| Safety Stock | Buffer inventory for variability | See Section 2 |

### Worked Example

A seller on Amazon US sells a kitchen gadget:
- Average daily sales: 15 units/day (450 units over last 30 days)
- Lead time: 45 days (15 days production + 25 days ocean freight + 5 days
  customs/FBA receiving)
- Safety stock: 135 units (calculated in Section 2)

```
ROP = (15 x 45) + 135
ROP = 675 + 135
ROP = 810 units
```

**Interpretation:** When your available inventory (FBA available + in-transit)
drops to 810 units, place a new purchase order. If you wait longer, you risk
a stockout before the new shipment arrives.

### Adjustments

- **Trending upward:** If sales are growing week-over-week, use a weighted
  average that gives 2x weight to the most recent 2 weeks.
- **New product:** Use conservative estimates (see Section 8, Example 3).
- **Multi-warehouse:** Calculate separate ROPs for each warehouse/FC.

---

## 2. Safety Stock Calculation

### Full Formula

```
Safety Stock = Z x sqrt((LT x Demand_Var) + (D_avg^2 x LT_Var))
```

Where:
- **Z** = Z-score for target service level
- **LT** = average lead time in days
- **Demand_Var** = variance of daily demand (standard deviation of daily sales, squared)
- **D_avg** = average daily sales
- **LT_Var** = variance of lead time in days (standard deviation of lead time, squared)

### Simplified Formula (Stable Lead Time)

When your lead time is consistent (standard deviation < 3 days):

```
Safety Stock = Z x SD_demand x sqrt(Lead Time)
```

Where:
- **Z** = Z-score for target service level
- **SD_demand** = standard deviation of daily sales
- **Lead Time** = average lead time in days

### Z-Score Table for Service Levels

| Service Level | Z-Score | Meaning | Recommended For |
|--------------|---------|---------|-----------------|
| 80% | 0.84 | Stockout 20% of order cycles | C-items, slow movers |
| 85% | 1.04 | Stockout 15% of order cycles | Low-priority SKUs |
| 90% | 1.28 | Stockout 10% of order cycles | B-items, standard SKUs |
| 95% | 1.65 | Stockout 5% of order cycles | A-items, important SKUs |
| 97% | 1.88 | Stockout 3% of order cycles | Key revenue drivers |
| 99% | 2.33 | Stockout 1% of order cycles | Mission-critical SKUs |
| 99.5% | 2.58 | Stockout 0.5% of order cycles | Cannot afford any stockout |

**Guidance:** Most cross-border sellers should use 95% service level for their
top 20% SKUs (A-items) and 90% for everything else. Going above 99% massively
increases required safety stock for diminishing returns.

### Worked Example (Simplified Formula)

Using the kitchen gadget from Section 1:
- Average daily sales: 15 units/day
- Standard deviation of daily sales: 5 units (calculated from 30 days of data)
- Lead time: 45 days
- Target service level: 95% (Z = 1.65)

```
Safety Stock = 1.65 x 5 x sqrt(45)
Safety Stock = 1.65 x 5 x 6.71
Safety Stock = 55.4
Safety Stock = 56 units (round up)
```

### Worked Example (Full Formula)

Same product, but lead time is variable (sometimes 40 days, sometimes 55 days):
- Average daily sales (D_avg): 15 units/day
- Variance of daily demand (Demand_Var): 25 (SD = 5, so variance = 25)
- Average lead time (LT): 45 days
- Variance of lead time (LT_Var): 25 (SD = 5 days, so variance = 25)
- Target service level: 95% (Z = 1.65)

```
Safety Stock = 1.65 x sqrt((45 x 25) + (15^2 x 25))
Safety Stock = 1.65 x sqrt(1125 + 5625)
Safety Stock = 1.65 x sqrt(6750)
Safety Stock = 1.65 x 82.16
Safety Stock = 135.6
Safety Stock = 136 units (round up)
```

**Note:** Adding lead time variability (SD = 5 days) nearly tripled the
safety stock requirement compared to the simplified formula (136 vs. 56 units).
This shows why stable, reliable suppliers and freight forwarders are worth
paying a premium for -- they directly reduce your capital locked in safety stock.

---

## 3. Economic Order Quantity (EOQ)

### Formula

```
EOQ = sqrt((2 x D x S) / H)
```

Where:
- **D** = annual demand in units
- **S** = order cost (fixed cost per purchase order)
- **H** = holding cost per unit per year

### Variable Definitions

| Variable | Definition | Typical Cross-Border Values |
|----------|-----------|---------------------------|
| D (Annual Demand) | Projected yearly unit sales | Average daily sales x 365 |
| S (Order Cost) | Fixed cost per PO: freight booking, customs brokerage, inspection, wire transfer, admin time | $200-$2,000 per order |
| H (Holding Cost) | Storage + capital + insurance + obsolescence per unit per year | 20-35% of unit cost |

### Holding Cost Breakdown

| Component | Typical % of Unit Cost | Notes |
|-----------|----------------------|-------|
| FBA storage fees | 8-15% | Higher for bulky/oversize items |
| Cost of capital | 8-12% | Opportunity cost of tied-up cash |
| Insurance | 1-2% | Cargo and inventory insurance |
| Obsolescence risk | 3-10% | Higher for fashion/electronics, lower for staples |
| **Total** | **20-35%** | Use 25% as default if unsure |

### Worked Example

Kitchen gadget:
- Annual demand (D): 15 units/day x 365 = 5,475 units/year
- Order cost (S): $800 per order (freight booking $300, customs brokerage $150,
  inspection $100, wire transfer $30, admin time $220)
- Unit cost: $8.00
- Holding cost per unit per year (H): $8.00 x 25% = $2.00/unit/year

```
EOQ = sqrt((2 x 5475 x 800) / 2.00)
EOQ = sqrt(8,760,000 / 2.00)
EOQ = sqrt(4,380,000)
EOQ = 2,093 units
```

**Interpretation:** The cost-optimal order quantity is approximately 2,093
units per order. At 15 units/day, this is about 140 days of supply. You would
place approximately 2.6 orders per year.

### Practical Adjustments to EOQ

EOQ is a theoretical optimum. Adjust for real-world constraints:

- **MOQ (Minimum Order Quantity):** If your supplier's MOQ is 3,000 units and
  EOQ says 2,093, you must order at least 3,000. Factor the higher holding cost
  into your planning.
- **Container utilization:** If 2,093 units fill 60% of a 20ft container,
  consider ordering enough to fill the container (the per-unit freight cost
  drops significantly at full container).
- **Seasonal demand:** EOQ assumes constant demand. If Q4 demand is 2.5x
  normal, pre-build inventory in Q3 rather than ordering EOQ quantities
  year-round.
- **Cash flow:** If ordering 2,093 units at $8 requires $16,744 in cash and
  you only have $10,000 available, order what you can afford and plan shorter
  cycles.
- **FBA restock limits:** If your FBA capacity only allows 1,500 additional
  units, send 1,500 to FBA and hold the remainder at a 3PL or AWD.

---

## 4. Days of Supply Calculation

### Formula

```
Days of Supply = Available Inventory / Average Daily Sales
```

For a more complete picture, include in-transit inventory:

```
Effective Days of Supply = (Available Inventory + In-Transit Units) / Average Daily Sales
```

### Worked Example

- FBA available: 450 units
- In-transit to FBA: 600 units (arriving in ~12 days)
- Average daily sales: 15 units/day

```
Days of Supply (available only) = 450 / 15 = 30 days
Effective Days of Supply = (450 + 600) / 15 = 70 days
```

**Interpretation:** You have 30 days of sellable inventory right now, and 70
days total when in-transit units arrive. If your lead time is 45 days, you do
not need to place a new PO yet (effective supply > lead time + safety stock
days).

### Action Thresholds

| Days of Supply | Action |
|---------------|--------|
| < 14 days (available only) | URGENT: Expedite shipment, consider air freight |
| 14-30 days | PLAN: Place PO within this week |
| 30-60 days | MONITOR: On track if next shipment is scheduled |
| 60-90 days | REVIEW: May have over-ordered; adjust next PO down |
| > 90 days | WARNING: Excess inventory risk; consider promotions |

---

## 5. Sell-Through Rate Calculation

### Formula

```
Sell-Through Rate = Units Sold in Period / (Units On Hand at Start of Period + Units Received During Period)
```

Alternative (Amazon's definition for IPI):

```
Sell-Through Rate (90-day) = Units Sold and Shipped (90 days) / Average Units Available (90 days)
```

### Worked Example

- Units on hand at start of month: 800
- Units received during month: 400
- Units sold during month: 450

```
Sell-Through Rate = 450 / (800 + 400) = 450 / 1200 = 37.5%
```

### Benchmarks

| Sell-Through Rate (Monthly) | Assessment |
|---------------------------|------------|
| > 50% | Excellent; may need more stock |
| 30-50% | Healthy |
| 15-30% | Below average; review listing and pricing |
| < 15% | Poor; investigate demand issues |

---

## 6. Seasonal Demand Adjustment Methods

### Method 1: Seasonal Index

Calculate from historical monthly sales data (minimum 1 year, ideally 2+
years).

```
Seasonal Index for Month M = Average Sales in Month M / Average Monthly Sales (all months)
```

**Example (Outdoor Product):**

| Month | Year 1 Sales | Year 2 Sales | Avg Sales | Seasonal Index |
|-------|-------------|-------------|-----------|---------------|
| Jan | 200 | 240 | 220 | 0.55 |
| Feb | 220 | 260 | 240 | 0.60 |
| Mar | 350 | 410 | 380 | 0.95 |
| Apr | 500 | 580 | 540 | 1.35 |
| May | 600 | 700 | 650 | 1.63 |
| Jun | 650 | 750 | 700 | 1.75 |
| Jul | 620 | 720 | 670 | 1.68 |
| Aug | 550 | 640 | 595 | 1.49 |
| Sep | 400 | 460 | 430 | 1.08 |
| Oct | 300 | 360 | 330 | 0.83 |
| Nov | 250 | 290 | 270 | 0.68 |
| Dec | 200 | 220 | 210 | 0.53 |
| **Total** | **4,840** | **5,630** | **5,235** | |
| **Monthly Avg** | | | **400** (rounded) | **1.00** |

To forecast June next year with a base forecast of 420 units/month (growth-adjusted):

```
June Forecast = 420 x 1.75 = 735 units
```

### Method 2: Category Proxy (No Historical Data)

When you lack your own sales history (new product or new market):

1. Use Amazon Brand Analytics or third-party tools to pull category-level
   monthly search volume data for the past 12 months.
2. Calculate monthly index from category search volume.
3. Apply the category index to your base forecast.

This is less accurate than your own data but far better than ignoring
seasonality.

### Method 3: Year-Over-Year Growth Adjustment

Combine seasonal index with a growth trend:

```
Adjusted Forecast = Base Forecast x Seasonal Index x (1 + YoY Growth Rate)
```

Example: If your base forecast is 400 units/month, June seasonal index is
1.75, and you grew 20% year-over-year:

```
June Forecast = 400 x 1.75 x 1.20 = 840 units
```

---

## 7. Lead Time Variability Accounting

### Why It Matters

Cross-border lead times vary significantly due to:
- Supplier production delays (material shortages, factory holidays, QC failures)
- Port congestion (common at origin and destination ports)
- Customs inspection (random or triggered by documentation issues)
- FBA receiving delays (especially Q4)
- Weather and geopolitical disruptions

### Measuring Lead Time Variability

Track actual lead time for every order and calculate the standard deviation.

| PO # | PO Date | Available Date | Actual Lead Time (days) |
|-------|---------|---------------|------------------------|
| 1 | Jan 5 | Feb 22 | 48 |
| 2 | Mar 10 | Apr 20 | 41 |
| 3 | May 15 | Jul 5 | 51 |
| 4 | Jul 20 | Sep 1 | 43 |
| 5 | Sep 25 | Nov 15 | 51 |

- Average lead time: 46.8 days
- Standard deviation: 4.6 days

### Incorporating into Safety Stock

Use the full safety stock formula (Section 2) with lead time variance:

```
LT_Var = SD_leadtime^2 = 4.6^2 = 21.16
```

This increases safety stock compared to the simplified formula but reflects
the reality of cross-border supply chains.

### Reducing Lead Time Variability

| Strategy | Effort | Impact |
|----------|--------|--------|
| Use the same freight forwarder consistently | Low | Medium |
| Pre-clear customs documentation before shipment arrives | Medium | High |
| Keep a buffer stock at a US 3PL (pre-customs cleared) | High | Very High |
| Air freight urgent restock while sea freight is in transit | Medium | High |
| Dual-source from two suppliers | High | High |
| Use Amazon AWD as a domestic buffer | Medium | High |

---

## 8. Worked Examples

### Example 1: Steady-Demand Product on Amazon US

**Scenario:** Silicone kitchen spatula, sold on Amazon US for 14 months.
Consistent demand with no strong seasonality.

**Given:**
- Average daily sales: 22 units/day (last 90 days)
- Standard deviation of daily sales: 6 units
- Average lead time: 50 days (China to US FBA via ocean freight)
- Lead time standard deviation: 4 days
- Target service level: 95% (Z = 1.65)
- Unit cost from supplier: $2.50
- Annual order cost: $600 per PO
- Holding cost rate: 25% of unit cost

**Step 1: Safety Stock**

Using full formula:

```
Safety Stock = Z x sqrt((LT x Demand_Var) + (D_avg^2 x LT_Var))
= 1.65 x sqrt((50 x 36) + (22^2 x 16))
= 1.65 x sqrt(1800 + 7744)
= 1.65 x sqrt(9544)
= 1.65 x 97.7
= 162 units
```

**Step 2: Reorder Point**

```
ROP = (22 x 50) + 162 = 1100 + 162 = 1,262 units
```

**Step 3: EOQ**

```
D = 22 x 365 = 8,030 units/year
H = $2.50 x 0.25 = $0.625/unit/year

EOQ = sqrt((2 x 8030 x 600) / 0.625)
    = sqrt(9,636,000 / 0.625)
    = sqrt(15,417,600)
    = 3,926 units
```

**Step 4: Plan**
- Order 3,926 units approximately every 178 days (~2 orders per year).
- Place each order when available inventory + in-transit drops to 1,262 units.
- This provides ~162 units of buffer at the 95% service level.

---

### Example 2: Seasonal Product (Q4 Peak)

**Scenario:** LED string lights, with 60% of annual sales in Oct-Dec.

**Given:**
- Annual sales: 12,000 units
- Monthly distribution: Jan-Sep avg 400 units/month, Oct 1,200, Nov 2,400,
  Dec 2,800, then drops off
- Lead time: 55 days (China to US FBA)
- Target service level for Q4: 99% (Z = 2.33, cannot afford stockout during peak)
- Unit cost: $3.00

**Step 1: Calculate Seasonal Indices**

| Period | Monthly Sales | Seasonal Index |
|--------|-------------|---------------|
| Jan-Sep (avg) | 400 | 0.40 |
| Oct | 1,200 | 1.20 |
| Nov | 2,400 | 2.40 |
| Dec | 2,800 | 2.80 |
| Monthly average | 1,000 | 1.00 |

**Step 2: Plan Q4 Inventory**

Q4 total demand: 1,200 + 2,400 + 2,800 = 6,400 units

With 55-day lead time, the last PO that can arrive for Q4 must ship by
mid-August (55 days before mid-October).

**Step 3: Safety Stock for Q4**

Using peak period daily demand:
- Nov daily sales: 2,400 / 30 = 80 units/day
- SD of daily sales during peak (estimated from prior year): 20 units
- Z = 2.33 (99% service level)

```
Safety Stock (Q4) = 2.33 x 20 x sqrt(55)
                  = 2.33 x 20 x 7.42
                  = 346 units
```

**Step 4: Total Q4 Pre-Position**

```
Total to position before Oct 1 = Q4 demand + Safety Stock
= 6,400 + 346 = 6,746 units
```

Subtract any remaining inventory from Q3 sales, then order the difference.

**Step 5: Shipping Timeline**

| Shipment | Ship by | Arrives by | Quantity | Purpose |
|----------|---------|-----------|---------|---------|
| Batch 1 | Jul 15 | Sep 8 | 3,500 | Oct + early Nov coverage |
| Batch 2 | Aug 10 | Oct 4 | 3,246 | Nov + Dec coverage |

Ship in 2 batches to reduce risk of total loss and spread cash outflow.

---

### Example 3: New Product Launch (Limited Data)

**Scenario:** Launching a new bamboo cutting board on Amazon US. No sales
history.

**Step 1: Estimate Demand from Comparable Products**

Identify 3-5 comparable ASINs (similar price, category, review count range):

| Comparable ASIN | BSR (Kitchen) | Estimated Daily Sales | Price |
|----------------|--------------|----------------------|-------|
| ASIN-A | 8,500 | 18 | $19.99 |
| ASIN-B | 12,000 | 12 | $22.99 |
| ASIN-C | 15,000 | 9 | $18.99 |
| ASIN-D | 6,000 | 25 | $21.99 |

Average estimated daily sales of comparables: 16 units/day.

**Step 2: Apply Conservative Discount**

New listing with zero reviews will convert at roughly 40-60% of established
competitors.

```
Conservative daily estimate = 16 x 0.50 = 8 units/day
```

**Step 3: Initial Order Quantity**

Order 45 days of supply (conservative, enough to validate demand):

```
Initial order = 8 x 45 = 360 units
```

**Step 4: Safety Stock for Launch**

With no historical variability data, use a rule of thumb: 50% of expected
lead time demand.

```
Lead time demand = 8 x 50 (lead time) = 400 units
Safety stock = 400 x 0.50 = 200 units
```

Wait -- this is more than the initial order. For a launch, you accept higher
stockout risk because the cost of overstock on an unproven product is worse.

**Revised approach:** Order 500 units total (360 base + 140 buffer). Accept
that if the product sells faster than expected, you may stock out once. Use
the first 30 days of sales data to calibrate your reorder model.

**Step 5: Reforecast After 14 Days**

After 14 days of live sales:
- Actual daily sales: 11 units/day (better than expected)
- Recalculated 45-day supply: 11 x 45 = 495 units needed
- Current inventory: 500 - (11 x 14) = 346 units remaining
- Days of supply: 346 / 11 = 31 days

**Action:** Place a reorder immediately. 31 days of supply minus 50 days of
lead time means you will stock out in 31 days if you do not reorder now.
Consider air freighting a partial shipment (200 units) while the sea freight
order (1,500+ units) is produced and shipped.

---

## 9. Spreadsheet Formulas

Ready-to-use formulas for Google Sheets or Excel. Assumes data starts in row 2
with headers in row 1.

### Setup: Column Definitions

| Column | Header | Content |
|--------|--------|---------|
| A | SKU | Product identifier |
| B | Avg Daily Sales | Average units sold per day (30-day) |
| C | SD Daily Sales | Standard deviation of daily sales |
| D | Avg Lead Time | Average lead time in days |
| E | SD Lead Time | Standard deviation of lead time in days |
| F | Service Level | Target service level (e.g., 0.95) |
| G | Unit Cost | Cost per unit from supplier |
| H | Order Cost | Fixed cost per purchase order |
| I | Holding Rate | Annual holding cost as % of unit cost (e.g., 0.25) |
| J | Current Inventory | Units currently available in warehouse/FBA |
| K | In Transit | Units currently in transit |

### Formula Columns

**Column L: Z-Score**
```
=IF(F2=0.8,0.84,IF(F2=0.85,1.04,IF(F2=0.9,1.28,IF(F2=0.95,1.65,IF(F2=0.97,1.88,IF(F2=0.99,2.33,1.65))))))
```

**Column M: Safety Stock**
```
=ROUNDUP(L2*SQRT((D2*C2^2)+(B2^2*E2^2)),0)
```

**Column N: Reorder Point**
```
=ROUNDUP(B2*D2+M2,0)
```

**Column O: EOQ**
```
=ROUNDUP(SQRT((2*B2*365*H2)/(G2*I2)),0)
```

**Column P: Days of Supply (Available)**
```
=IF(B2>0,ROUND(J2/B2,0),"N/A")
```

**Column Q: Days of Supply (Including In-Transit)**
```
=IF(B2>0,ROUND((J2+K2)/B2,0),"N/A")
```

**Column R: Reorder Signal**
```
=IF(J2+K2<=N2,"ORDER NOW",IF(J2<=N2,"PLAN ORDER","OK"))
```

**Column S: Suggested Order Qty**
```
=IF(R2="OK",0,MAX(O2,ROUNDUP((N2+B2*30)-(J2+K2),0)))
```

**Column T: Monthly Storage Cost (FBA estimate)**
```
=ROUND(J2*G2*I2/12,2)
```

### Sell-Through Rate (Separate Calculation)

```
=Units_Sold_30_Days / ((Start_Inventory + End_Inventory) / 2)
```

### Seasonal Adjustment

If you have monthly sales data in columns for each month (e.g., columns
V through AG for Jan-Dec):

**Seasonal Index for a specific month (e.g., column V = January):**
```
=V2/AVERAGE(V2:AG2)
```

**Seasonally Adjusted Forecast:**
```
=Base_Forecast * Seasonal_Index
```

---

## 10. When to Override the Formulas

Formulas provide a rational baseline, but several situations require human
judgment to override calculated quantities.

### Override Upward (Order More Than Formula Says)

| Situation | Why Override | How Much More |
|-----------|-------------|--------------|
| **Upcoming peak season** | Historical seasonality demands pre-positioning | Use seasonal index (Section 6) |
| **Viral moment / PR event** | Demand may spike 3-10x for days/weeks | Order 2-3x normal plus air freight contingency |
| **Supplier holiday shutdown** | Chinese New Year, Eid, Diwali close factories for 2-4 weeks | Add 21-30 days of extra supply |
| **Planned product launch campaign** | Ads/promotions will drive above-baseline demand | Estimate campaign lift (30-100% typical) and add |
| **Tariff or cost increase announced** | Lock in current pricing before increase | Order up to 90 days extra if cost savings justify holding cost |
| **Freight disruption expected** | Port strikes, Suez Canal, Red Sea diversions | Add 14-21 days buffer to lead time |

### Override Downward (Order Less Than Formula Says)

| Situation | Why Override | How Much Less |
|-----------|-------------|--------------|
| **Cash flow constraints** | Cannot afford full EOQ | Order what cash allows; shorten cycle |
| **Product lifecycle end** | Phasing out SKU | Order only enough to bridge to discontinuation |
| **Market uncertainty** | New tariffs, regulatory changes, competitor entry | Reduce order by 30-50% until clarity |
| **First order (new product)** | Unproven demand | Order 30-45 days of conservative estimate only |
| **FBA restock limits** | Cannot send full quantity to FBA | Send to 3PL/AWD overflow, drip-feed to FBA |
| **Declining sales trend** | 3+ weeks of declining velocity | Use recent 14-day average, not 30-day |

### Override the Service Level

| Situation | Adjustment |
|-----------|-----------|
| Product has no close substitutes on Amazon | Increase to 99% (buyers will wait or buy from you later) |
| Product is commodity with 10+ identical competitors | Decrease to 90% (buyers switch instantly; overstock is worse) |
| Product has high obsolescence risk (fashion, electronics) | Decrease to 85-90% and accept occasional stockouts |
| Product is your #1 revenue driver (>30% of revenue) | Increase to 97-99% regardless of competition |

### General Rule

> **Use the formula as your default. Override only when you can articulate a
> specific, time-bound reason. Document every override and review outcomes
> quarterly to calibrate your judgment.**

Undocumented overrides lead to "gut feeling" ordering, which is the #1 cause
of excess inventory in cross-border e-commerce.

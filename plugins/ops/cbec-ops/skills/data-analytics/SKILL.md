---
name: data-analytics
description: >
  Use when tracking business performance metrics, building dashboards, running
  A/B tests on listings or ads, interpreting platform analytics, diagnosing
  sales drops, or making data-driven optimization decisions across any
  e-commerce channel.
---

# Data Analytics for Cross-Border E-Commerce

Turn raw platform data into actionable decisions. This skill covers KPI
selection, sales diagnostics, review cadence, A/B testing methodology, and
platform-specific analytics navigation so every optimization is grounded in
evidence rather than intuition.

Skill type: Technique + Reference

## Core Principle

Measure what matters, not what is easy. Session count is easy to measure but
rarely actionable. Conversion rate by traffic source is harder but drives real
decisions.

Three rules follow from this principle:

1. **Every metric must have an owner and a response plan.** If nobody acts when
   the number moves, stop tracking it.
2. **Compare rates, not absolutes.** A 200-unit day means nothing without
   knowing sessions, conversion rate, and ad spend behind it.
3. **Segment before you conclude.** Aggregate data hides the signal. Break
   numbers down by SKU, traffic source, marketplace, and time period before
   making any decision.

## KPI Hierarchy

Organize metrics in a pyramid. Start from the North Star and drill down only
when the higher-level number moves unexpectedly.

```
                    North Star
              Monthly Net Profit
                      |
        --------------+---------------
        |             |               |
    Revenue        Units Sold      TACOS
        |             |               |
   -----------   -----------    -----------
   |    |    |   |    |    |   |    |    |
  ASP  AOV CVR  Rank  BSR  IPI ACOS ROAS CPC
                      |
              -----------------
              |       |       |
            CTR   ATC Rate  Sessions
                      |
              -----------------
              |       |       |
          Bounce   Return   Review
           Rate     Rate   Velocity
```

### North Star: Monthly Net Profit

Everything rolls up here. Revenue growth that erodes margin is not growth.

### Primary KPIs

| KPI | Why It Matters | Review Frequency |
|-----|---------------|------------------|
| Revenue | Top-line health | Daily glance, weekly trend |
| Units Sold | Demand signal independent of price changes | Daily glance, weekly trend |
| Conversion Rate (CVR) | Listing effectiveness; most controllable lever | Weekly |
| TACOS (Total Ad Cost of Sales) | Blended ad efficiency across organic + paid | Weekly |

### Secondary KPIs

| KPI | Why It Matters | Review Frequency |
|-----|---------------|------------------|
| Sessions | Traffic volume; diagnose reach problems | Weekly |
| ACOS | Per-campaign ad efficiency | Weekly per campaign |
| Organic Rank (top 5 keywords) | SEO health | Weekly |
| Review Velocity | Social proof momentum | Bi-weekly |

### Diagnostic KPIs

Pull these only when a Primary or Secondary metric moves:

| KPI | Diagnoses | Trigger |
|-----|-----------|---------|
| Click-Through Rate (CTR) | Main image or title problem | Sessions drop, impressions stable |
| Add-to-Cart (ATC) Rate | Price or content mismatch | CVR drops, sessions stable |
| Bounce Rate | Relevance or page-load issue | Sessions up, CVR down |
| Return Rate | Product-quality or listing-accuracy gap | Units stable, net profit drops |

## Sales Drop Diagnostic Framework

When daily revenue or units drop more than 20% versus the trailing 7-day
average, walk through these causes in order. Each step either confirms or
eliminates the cause before moving to the next.

### Step 1: Stock

Check inventory levels and listing status.

- Is the ASIN / listing active? Suppressed or stranded inventory kills sales
  instantly.
- FBA inventory in stock? If units hit zero, the listing loses Buy Box and
  organic rank simultaneously.
- FBM backup active? If FBA runs out and no FBM offer exists, the listing
  disappears from search.

**Fix**: Restock, remove stranded inventory, or activate FBM backup. Recovery
time: 1-3 days for rank to return after restock.

### Step 2: Buy Box

Check Buy Box ownership percentage.

- Has Buy Box share dropped below 90%?
- New third-party sellers offering lower price?
- Has Amazon Retail entered the listing?

**Fix**: Reprice to competitive level, report unauthorized sellers if
applicable, ensure Prime eligibility. Recovery time: immediate once Buy Box
is recaptured.

### Step 3: Rank

Check organic keyword positions for the top 5 keywords.

- Have positions dropped more than 5 spots?
- Did a competitor launch an aggressive PPC campaign or promotion?
- Recent listing content change that removed indexed keywords?

**Fix**: Increase PPC budget on declining keywords, revert problematic listing
changes, run a promotion to boost velocity. Recovery time: 3-14 days.

### Step 4: Price

Check price competitiveness relative to the category.

- Has a competitor dropped price significantly?
- Did your price increase (repricer rule, FX change, fee increase)?
- Is the product now priced outside the category's conversion-friendly range?

**Fix**: Adjust price or add a coupon/deal. Recovery time: 1-3 days.

### Step 5: Seasonality

Check year-over-year data for the same period.

- Is this a known seasonal trough for the category?
- Did a major shopping event just end (post-Prime Day, post-Black Friday)?
- External factor (weather, holiday, news event)?

**Fix**: Reduce ad spend to protect margin during troughs; pre-plan promotions
for the next seasonal uptick.

### Step 6: Competition

Check new entrants and competitor activity.

- New competitor launched with aggressive pricing or heavy ad spend?
- Competitor listing gained significant new reviews?
- Category-level demand shift (search volume down)?

**Fix**: Differentiate listing, adjust PPC targeting, consider bundling or
variation strategy. Recovery time: varies.

## Weekly Review Cadence

Complete this checklist every Monday (or the first working day of the week).
Total time: 30-45 minutes per marketplace.

### Revenue and Units (5 min)

- [ ] Compare last 7 days vs prior 7 days and same week last year.
- [ ] Flag any SKU with >20% unit decline for diagnostic framework.
- [ ] Note top 3 and bottom 3 SKUs by revenue change.

### Advertising (10 min)

- [ ] Review TACOS trend (should be flat or declining over time).
- [ ] Check ACOS by campaign; pause keywords with ACOS >2x target and >$20 spend in 7 days.
- [ ] Review new-to-brand percentage (Sponsored Brands).
- [ ] Check search term report for irrelevant terms; add negatives.

### Conversion and Traffic (10 min)

- [ ] Review CVR by ASIN; investigate any >15% decline.
- [ ] Check sessions trend; correlate with ad spend changes.
- [ ] Review Buy Box percentage for all ASINs.

### Inventory (5 min)

- [ ] Check days of supply for top 20 SKUs.
- [ ] Flag SKUs with <21 days of supply for urgent reorder.
- [ ] Check for stranded or suppressed inventory.

### Reviews and Customer Feedback (5 min)

- [ ] Check new reviews and ratings for top 10 ASINs.
- [ ] Read all 1-star and 2-star reviews from the past week.
- [ ] Note recurring complaints for product or listing improvement.

### Action Items (5 min)

- [ ] Document top 3 actions for the week with owner and deadline.
- [ ] Review last week's action items for completion.

## Monthly Deep-Dive Checklist

Complete this on the first week of each month. Requires 2-4 hours.

### Profitability Analysis

- [ ] Calculate true net margin per SKU (revenue minus COGS, shipping, fees,
      ad spend, returns, storage).
- [ ] Identify SKUs with <10% contribution margin for price increase, cost
      reduction, or discontinuation review.
- [ ] Compare actual landed cost to planned cost; flag >5% variances.

### Advertising Deep-Dive

- [ ] Review 30-day ACOS and TACOS trend by product group.
- [ ] Analyze top 20 keywords by spend; confirm each is profitable.
- [ ] Review Sponsored Brands and Sponsored Display performance.
- [ ] Check placement modifiers (top-of-search bid adjustments).
- [ ] Run search query performance report (Amazon Brand Analytics).

### Listing Performance Audit

- [ ] Compare CVR across similar ASINs; investigate outliers.
- [ ] Review keyword rankings for top 3 keywords per ASIN.
- [ ] Check listing quality score (Amazon Listing Quality Dashboard).
- [ ] Identify A/B test candidates for next month.

### Inventory and Supply Chain

- [ ] Review IPI score trend.
- [ ] Calculate sell-through rate for the past 90 days.
- [ ] Flag aged inventory (>180 days) for removal or liquidation.
- [ ] Reconcile shipment quantities vs received quantities.

### Customer Metrics

- [ ] Review return rate by ASIN; investigate any >8%.
- [ ] Analyze Voice of the Customer dashboard.
- [ ] Check Account Health metrics.

### Competitive Landscape

- [ ] Review category BSR trends for top 5 competitors.
- [ ] Note new competitor launches or significant review gains.
- [ ] Update pricing benchmark spreadsheet.

## Platform Analytics Navigation

Quick reference for where to find key data on each platform.

### Amazon Seller Central

| Report | Path | Key Metrics |
|--------|------|-------------|
| Business Reports | Reports > Business Reports > By ASIN | Sessions, CVR, Units, Revenue |
| Advertising Console | Advertising > Campaign Manager | ACOS, Spend, Impressions, Clicks |
| Brand Analytics | Brands > Brand Analytics | Search frequency rank, click share, conversion share |
| Inventory Dashboard | Inventory > Inventory Planning | IPI, Days of Supply, Sell-Through |
| Account Health | Performance > Account Health | ODR, Late Shipment, Policy Violations |
| Search Query Performance | Brands > Brand Analytics > Search Query Performance | Query volume, impressions, clicks, cart adds, purchases |
| Voice of Customer | Performance > Voice of the Customer | Return reasons, negative feedback |

### Shopify

| Report | Path | Key Metrics |
|--------|------|-------------|
| Overview Dashboard | Analytics > Overview | Sessions, CVR, AOV, Revenue |
| Sales by Product | Analytics > Reports > Sales by product | Units, revenue per SKU |
| Acquisition | Analytics > Reports > Sessions by referrer | Traffic source breakdown |
| Behavior | Analytics > Reports > Online store cart analysis | ATC rate, checkout abandonment |

### TikTok Shop

| Report | Path | Key Metrics |
|--------|------|-------------|
| Dashboard | TikTok Shop Seller Center > Dashboard | GMV, orders, CVR |
| Product Analytics | Data Compass > Product Analysis | Views, clicks, orders per product |
| Traffic Analysis | Data Compass > Traffic Analysis | Source breakdown, live vs short video vs shop tab |
| Creator Performance | Affiliate > Creator management | GMV per creator, commission, CVR |

### Walmart Marketplace

| Report | Path | Key Metrics |
|--------|------|-------------|
| Performance Dashboard | Seller Center > Analytics > Performance | Page views, CVR, Buy Box % |
| Item Performance | Analytics > Item Performance | Views, orders, CVR per item |
| Listing Quality | Growth Opportunities > Listing Quality | Content score, offer score |

## Red Flags

Avoid these five common analytics mistakes:

### 1. Tracking Too Many Metrics

If your dashboard has more than 12 metrics, you are tracking noise. Limit the
daily view to the North Star plus Primary KPIs. Pull Secondary and Diagnostic
metrics only when investigating a problem.

### 2. Making Decisions on Less Than 7 Days of Data

E-commerce data is noisy. Day-of-week effects, ad delivery fluctuations, and
delayed attribution make any single day unreliable. Always use at least a 7-day
window before changing strategy. For advertising changes, prefer 14-day windows.

### 3. Comparing Absolute Numbers Instead of Rates

"We sold 500 units this week" is meaningless without context. "CVR dropped from
12% to 9% while sessions increased 40%" tells a story: the new traffic is
lower quality or the listing is underperforming. Always normalize to rates.

### 4. Ignoring Attribution Windows

Amazon attributes conversions up to 14 days after a click for Sponsored
Products, 14 days for Sponsored Brands, and 14 days for Sponsored Display.
Evaluating campaign performance before the attribution window closes leads to
premature cuts. Wait for the full window before making significant budget
decisions.

### 5. Not Segmenting Data

Aggregate numbers mask problems. A stable overall CVR can hide one ASIN
doubling its conversion while another collapses. Always segment by:

- **SKU / ASIN**: individual product performance
- **Traffic source**: organic vs paid vs external
- **Geography**: marketplace or region
- **Time period**: week-over-week, month-over-month, year-over-year
- **Device**: mobile vs desktop (where available)

## Cross-References

This skill feeds into and draws from every other skill in the suite.

**FEEDS INTO (this skill provides data that drives decisions in)**:
- `cbec-ops:advertising-marketing` -- ACOS, ROAS, TACOS, and campaign metrics guide bid and budget decisions
- `cbec-ops:product-listing` -- CVR, CTR, and A/B test results drive listing optimization
- `cbec-ops:inventory-management` -- sell-through rate, days of supply, and IPI guide reorder timing
- `cbec-ops:financial-management` -- margin analysis, COGS tracking, and profitability per SKU
- `cbec-ops:pricing-strategy` -- price elasticity data and competitive price tracking inform repricing
- `cbec-ops:product-selection` -- category demand trends and search volume inform new product decisions
- `cbec-ops:customer-service` -- return rate, review sentiment, and VOC data guide service improvements
- `cbec-ops:brand-building` -- brand awareness metrics, new-to-brand %, and share of voice

**ESPECIALLY tightly coupled with**:
- `cbec-ops:advertising-marketing` -- advertising is the highest-frequency data consumer
- `cbec-ops:product-listing` -- listing optimization depends entirely on conversion data
- `cbec-ops:inventory-management` -- stockout prevention requires accurate velocity forecasting
- `cbec-ops:financial-management` -- profitability analysis is the ultimate validation of all decisions

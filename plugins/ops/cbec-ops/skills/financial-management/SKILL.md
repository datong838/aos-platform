---
name: financial-management
description: >
  Use when helping sellers track profitability per SKU or overall business,
  manage cash flow, handle multi-currency transactions, understand tax
  obligations (VAT/GST/sales tax), reconcile platform payouts, or answer
  "is my business profitable?" for cross-border e-commerce operations.
---

# Financial Management

A reference and technique skill for cross-border e-commerce financial operations.
This skill guides AI agents through profitability tracking, cash flow management,
multi-currency handling, tax compliance orientation, and payout reconciliation.
Every financial assessment must be grounded in verified numbers from the seller's
actual books, never estimated from category averages alone.

---

## Core Principle

**Revenue is vanity, profit is sanity, cash flow is reality. A business can be
profitable on paper and still die from cash starvation. Track cash flow with
the same rigor as profit.**

A cross-border seller receiving a $50,000 monthly payout from Amazon may feel
successful, but if $48,000 is already committed to supplier payments, freight
invoices, ad spend, and platform fees, that seller has $2,000 of actual operating
room. One delayed shipment or currency swing can tip them into crisis.

Financial management for cross-border e-commerce is harder than domestic because:
- Revenue arrives in foreign currencies on delayed schedules
- COGS are paid in a different currency, often months before revenue arrives
- Multiple tax jurisdictions apply simultaneously
- Platform fee structures are opaque and change without notice
- Working capital is trapped in transit inventory for weeks or months

---

## SKU-Level P&L Structure

Every SKU must carry its own P&L. A business-level view that hides individual
SKU performance will mask products that are quietly destroying margin.

```
Revenue (Gross Sales)
 minus Refunds & Returns .................... actual refund amount
 minus Platform Promotional Credits ........ coupons, Lightning Deal rebates
 = Net Revenue

 minus COGS (factory + packaging + QC) ..... landed at factory gate
 minus Inbound Freight per Unit ............ sea/air/rail to destination warehouse
 minus Customs Duties & Tariffs ............ based on HS code and declared value
 minus Customs Brokerage Fee ............... allocated per unit
 = Gross Profit

 minus Platform Referral Fee ............... 8-15% of selling price
 minus Fulfillment Fee .................... FBA/3PL per-unit fee
 minus Monthly Storage Fee ................. allocated by unit volume and days stored
 minus Long-Term Storage Surcharge ......... aged inventory (180/270/365+ days)
 minus Advertising Cost .................... PPC spend allocated to this SKU
 minus Payment Processing Fee .............. 2-3.5%
 minus Currency Conversion Fee ............. 0.5-3.5% depending on provider
 minus Returns Processing Cost ............. reverse logistics + restock/disposal
 minus VAT/GST (if seller-absorbed) ........ varies by jurisdiction
 minus Insurance Allocation ................ cargo + product liability per unit
 = Operating Profit (per unit)

 minus Income Tax Allocation ............... estimated effective rate
 = Net Profit (per unit)
```

**Target:** Net profit of 10-25% of net revenue per SKU. Any SKU below 10% net
margin requires an action plan (cost reduction, price increase, or discontinuation
timeline). Any SKU below 5% should be on a 30-day discontinuation watchlist unless
it serves a documented strategic purpose (traffic driver, bundle anchor).

See `references/pnl-template.md` for complete templates and worked examples.

---

## Cash Flow Management

### The Cash Conversion Cycle Problem

Cross-border e-commerce has one of the longest cash conversion cycles in retail.

```
Typical Cash Conversion Cycle: 60-120 days

Day 0 ......... Place order with supplier (30% deposit)
Day 30 ........ Production complete (70% balance due)
Day 35 ........ Goods ship from factory
Day 55-75 ..... Goods arrive at destination warehouse (sea freight)
Day 60-80 ..... Goods checked in and available for sale
Day 65-90 ..... First units sold
Day 80-105 .... Platform processes payout (14-day hold typical)
Day 85-110 .... Payout received in platform currency
Day 90-120 .... Funds converted and available in home currency
```

This means cash paid on Day 0 may not return until Day 90-120. A seller
scaling from $10,000/month to $50,000/month needs $40,000+ of additional
working capital just to fund the pipeline, even if every product is profitable.

### Cash Flow Rules

1. **Maintain a 60-day operating cash reserve.** This covers one full reorder
   cycle if revenue stops unexpectedly. Minimum viable reserve is 30 days.

2. **Never invest all available cash in inventory.** Maximum 70% of available
   cash in inventory at any given time. The remaining 30% covers unexpected
   costs, opportunities, and emergencies.

3. **Map payment obligations to expected inflows.** Create a weekly cash flow
   calendar that shows when supplier payments are due, when platform payouts
   arrive, and when tax payments are owed. Identify gaps before they become
   crises.

4. **Track cash flow separately from profit.** A product can be profitable
   per unit but cash-flow negative if the reorder cycle is shorter than the
   collection cycle. This happens when fast-selling products require frequent
   restocking before prior inventory's revenue has been collected.

5. **Negotiate payment terms aggressively.** Priority order:
   - Extend supplier payment terms (net 30, net 60, or milestone-based)
   - Accelerate platform payouts (daily disbursements where available)
   - Use trade finance or purchase order financing only as a last resort
     (typical cost: 1-3% per month)

### Cash Flow KPIs

| Metric | Formula | Target |
|--------|---------|--------|
| Cash Conversion Cycle | Days Inventory + Days Receivable - Days Payable | < 90 days |
| Operating Cash Ratio | Operating Cash / Monthly Fixed Costs | > 2.0x |
| Inventory-to-Cash Ratio | Cash / (Inventory at Cost) | > 0.3 |
| Reorder Safety Buffer | Cash after next reorder / Monthly fixed costs | > 1.5 months |

---

## Multi-Currency Management Strategy

Cross-border sellers face structural FX risk: costs are denominated in the
sourcing currency (typically CNY) while revenue arrives in multiple selling
currencies (USD, EUR, GBP, JPY, AUD, CAD).

### Key Principles

1. **Know your blended FX cost.** The real cost of goods is not the factory
   price in CNY; it is the factory price converted at the actual rate you paid,
   including all conversion fees and timing differences.

2. **Maintain multi-currency accounts.** Hold balances in each selling currency
   and convert strategically rather than auto-converting every payout. Services
   like Payoneer, WorldFirst, and PingPong offer multi-currency wallets.

3. **Set conversion triggers.** Define rate thresholds at which you convert.
   For example: "Convert USD to CNY when the rate is above 7.20; hold USD
   when below 7.10." This avoids emotional or arbitrary conversion timing.

4. **Match currency timing to obligations.** If supplier payment in CNY is due
   in 30 days, convert or lock in the rate now rather than waiting and hoping
   the rate improves.

5. **Track FX gains/losses as a separate line item.** Currency movements are
   not part of product margin; they are a financial management outcome. Track
   them separately so product decisions are not distorted by FX noise.

See `references/currency-hedging.md` for provider comparison, hedging
strategies, and multi-currency bookkeeping guidance.

---

## Tax Compliance Overview

Cross-border sellers are subject to tax obligations in every jurisdiction where
they store inventory, have economic nexus, or exceed registration thresholds.
Ignorance does not prevent liability; it only delays the penalty.

### Quick Reference: Major Obligations

| Jurisdiction | Tax Type | Trigger | Typical Rate |
|-------------|----------|---------|-------------|
| US | Sales Tax | Economic nexus (varies by state) | 0-10.25% |
| EU | VAT | Selling to EU consumers (any amount via IOSS) | 17-27% |
| UK | VAT | GBP 85,000 threshold or voluntary registration | 20% |
| Japan | JCT | Selling to Japan consumers | 10% |
| Australia | GST | AUD 75,000 threshold | 10% |
| Singapore | GST | SGD 100,000 threshold (2024+: SGD 1M for overseas vendors) | 9% |
| Canada | GST/HST | CAD 30,000 threshold | 5-15% |

### Critical Tax Rules for Cross-Border Sellers

1. **Marketplace facilitator laws simplify US sales tax.** Amazon, Walmart, and
   other major platforms collect and remit sales tax on behalf of sellers in most
   US states. Verify which states your platform covers; you may still have filing
   obligations even if the platform collects.

2. **EU IOSS (Import One-Stop Shop) is mandatory knowledge.** For shipments
   valued under EUR 150 direct to EU consumers, IOSS allows a single VAT
   registration and filing instead of registering in every member state. If using
   FBA in the EU, you need VAT registration in every country where inventory is
   stored.

3. **VAT is not optional.** Selling into the EU or UK without proper VAT
   registration is illegal and platforms will suspend accounts that cannot
   provide valid VAT numbers. Budget for VAT compliance from day one.

4. **Keep records for 5-7 years.** Most jurisdictions require retention of
   invoices, customs documentation, and transaction records for 5-7 years.
   Automate record-keeping from the start; retroactive reconstruction is
   expensive and incomplete.

See `references/tax-compliance.md` for detailed jurisdiction-by-jurisdiction
guidance, registration processes, filing calendars, and record-keeping
requirements.

---

## Platform Payout Reconciliation Checklist

Platform payouts rarely match expected amounts. Reconcile every payout cycle.

### Step 1: Download Reports
- Amazon: Settlement Report (Payments > Statements)
- Shopee: Finance > Income > Payout details
- Walmart: Payment dashboard > Transaction report
- Other platforms: find the equivalent transaction-level payout report

### Step 2: Verify Revenue Lines
- [ ] Gross sales match order count multiplied by selling prices
- [ ] Promotional credits deducted correctly (coupons, deals)
- [ ] Refunds match actual return/refund records
- [ ] Tax collected and remitted amounts are correct

### Step 3: Verify Fee Lines
- [ ] Referral fees match expected percentages per category
- [ ] Fulfillment fees match size/weight tiers for each product
- [ ] Storage fees align with inventory levels and time in warehouse
- [ ] Advertising charges match campaign spend records
- [ ] Subscription fees (Professional seller, etc.) are correct
- [ ] No unexpected or unrecognized fee line items

### Step 4: Verify Adjustments
- [ ] Reimbursements for lost/damaged inventory are received
- [ ] Claims for incorrect fee charges have been filed
- [ ] FX conversion rate applied matches market rate within provider spread

### Step 5: Reconcile to Bank
- [ ] Payout amount matches bank deposit
- [ ] Timing aligns with expected disbursement schedule
- [ ] Currency conversion matches expected rate (if auto-converted)

### Common Discrepancies
- **Weight/dimension tier miscategorization:** Amazon frequently miscategorizes
  products into larger size tiers. Check every ASIN quarterly. File for
  reimbursement (cubiscan measurement) when wrong.
- **Missing reimbursements:** Inventory lost in FBA warehouses is supposed to be
  reimbursed automatically. Audit monthly; file manual claims for anything missed
  after 30 days.
- **Promotional fee errors:** Lightning Deal fees, coupon redemption fees, and
  Subscribe & Save discounts can appear inconsistently. Cross-reference with
  campaign records.
- **Retroactive fee changes:** Platforms occasionally apply fee changes
  retroactively. Compare fee rates to the published schedule effective on the
  transaction date.

---

## Financial KPIs and Benchmarks

Track these metrics monthly at minimum. Review weekly during scaling phases.

### Profitability KPIs

| Metric | Formula | Healthy Range | Warning |
|--------|---------|--------------|---------|
| Gross Margin | (Net Revenue - COGS - Freight - Duties) / Net Revenue | 40-65% | < 35% |
| Net Profit Margin | Net Profit / Net Revenue | 10-25% | < 8% |
| TACOS | Total Ad Spend / Total Revenue | 8-15% | > 20% |
| Return Rate | Returned Units / Sold Units | 2-8% (category dependent) | > 15% |
| Effective Tax Rate | Total Tax Paid / Pre-Tax Profit | Varies | Unexpected changes |

### Cash Flow KPIs

| Metric | Formula | Healthy Range | Warning |
|--------|---------|--------------|---------|
| Cash Conversion Cycle | Days Inventory + Days Receivable - Days Payable | 60-90 days | > 120 days |
| Current Ratio | Current Assets / Current Liabilities | > 1.5 | < 1.0 |
| Burn Rate | Monthly Cash Outflow - Monthly Cash Inflow | Positive inflow | Negative for 2+ months |
| Runway | Available Cash / Monthly Net Burn | > 6 months | < 3 months |

### Growth KPIs

| Metric | Formula | Context |
|--------|---------|---------|
| Revenue Growth Rate | (Current Month Revenue - Prior Month) / Prior Month | Sustainable growth funds itself |
| Profit Growth Rate | Same formula on net profit | Must track or exceed revenue growth |
| Revenue per SKU | Total Revenue / Active SKU Count | Declining = SKU bloat |
| Working Capital Efficiency | Revenue / Average Working Capital Deployed | Higher = more efficient |

---

## When to Hire an Accountant

Hire a cross-border e-commerce specialist accountant when ANY of these apply:

1. **Annual revenue exceeds $250,000.** The complexity of multi-jurisdiction
   tax compliance at this scale exceeds what most sellers can self-manage
   without errors.

2. **You sell into 3+ countries.** Each country adds tax registration, filing,
   and compliance obligations. The interaction effects between jurisdictions
   (transfer pricing, double taxation treaties) require professional guidance.

3. **You are incorporating or restructuring.** Business entity decisions
   (LLC, Ltd, HK company, Singapore company) have long-term tax implications
   that are expensive to reverse.

4. **You received a tax notice or audit request.** Do not respond to tax
   authorities without professional representation.

5. **You are spending more than 10 hours/month on financial admin.** Your time
   has a cost. If bookkeeping, reconciliation, and tax filing consume more
   than 10 hours monthly, an accountant (or bookkeeper + accountant) is
   likely cheaper than your opportunity cost.

6. **You plan to raise capital or sell the business.** Investors and acquirers
   require clean, auditable financials. Retroactive cleanup is 3-5x more
   expensive than maintaining clean books from the start.

**What to look for:** An accountant or firm with specific cross-border
e-commerce experience. Generic small business accountants often miss
marketplace-specific deductions, mishandle multi-currency transactions, and
are unfamiliar with platform fee structures. Ask for client references from
other Amazon/cross-border sellers.

---

## Red Flags

1. **Cannot calculate net profit per SKU.**
   If a seller knows gross revenue but cannot state net profit per SKU after
   all costs, they are flying blind. This is the single most common financial
   management failure in cross-border e-commerce. Without SKU-level P&L, losing
   products hide behind winning ones, and the business slowly bleeds margin
   without visible symptoms until cash runs out.

2. **Mixing personal and business finances.**
   Commingled accounts make tax compliance nearly impossible, create audit risk,
   and prevent accurate business valuation. Establish separate bank accounts,
   payment provider accounts, and credit cards for the business from day one.
   This also applies to multiple businesses: each entity needs its own accounts.

3. **No cash flow forecast beyond the current month.**
   A seller who cannot project cash position 60-90 days forward is at risk of
   a cash crisis. The long cash conversion cycle in cross-border e-commerce
   means that a stockout, delayed shipment, or supplier price increase
   discovered today was actually caused by a planning failure 60-90 days ago.

4. **Ignoring FX losses as "just the cost of doing business."**
   Currency conversion costs and FX movements are manageable costs, not
   inevitable losses. A seller paying 3% conversion fees when 0.5% options
   exist is giving away 2.5% of revenue. On $500,000 annual revenue, that is
   $12,500 in avoidable cost. Compare providers and track FX as a managed
   cost line.

5. **No tax compliance plan for active selling jurisdictions.**
   Selling into a country without understanding the tax obligations is not a
   strategy; it is a liability accumulating interest and penalties. Many
   sellers discover VAT obligations only when their account is suspended or
   they receive a tax authority notice. By that point, back-taxes, penalties,
   and interest have compounded. Budget for tax compliance before entering
   any new market.

---

## Cross-references

- **FEEDS FROM:** `cbec-ops:pricing-strategy` -- Pricing decisions determine
  revenue per unit; cost structures and margin targets flow directly into P&L
  tracking and profitability analysis.
- **FEEDS FROM:** `cbec-ops:inventory-management` -- Inventory levels, turnover
  rates, and storage costs are major inputs to cash flow forecasting and
  working capital planning.
- **FEEDS FROM:** `cbec-ops:advertising-marketing` -- Advertising spend is
  typically the largest variable cost after COGS; TACOS and ACOS metrics feed
  directly into SKU-level profitability.
- **RELATED:** `cbec-ops:data-analytics` -- Financial dashboards, KPI tracking,
  and trend analysis depend on the metrics and structures defined here.

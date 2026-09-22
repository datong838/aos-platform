---
name: order-fulfillment
description: >
  Use when the seller asks about choosing shipping methods, creating FBA
  shipments, managing customs and duties, selecting 3PL providers, handling
  last-mile delivery, dealing with lost or damaged shipments, planning logistics
  for a new market, comparing freight forwarders, calculating shipping costs,
  setting up returns logistics, or any question about getting products from
  factory to customer doorstep.
---

# Order Fulfillment: Factory to Customer Doorstep

Guide sellers through end-to-end logistics for cross-border e-commerce. This
skill covers every link in the fulfillment chain: factory pickup, international
freight, customs clearance, warehousing, last-mile delivery, and returns. The
goal is reliable, cost-effective delivery that meets customer expectations and
protects seller margins.

## Core Principle

> **Fulfillment is where promises become reality. A 2-day delivery promise
> broken costs more than the product price in lost trust and negative reviews.
> Plan for the worst case, optimize for the average case.**

Late deliveries trigger refund requests, negative reviews, and reduced organic
ranking. A single "Where is my package?" complaint costs 15-30 minutes of
customer service time. At scale, fulfillment failures are the fastest way to
destroy a profitable product line.

Every fulfillment decision must answer: **"What happens when this goes wrong,
and can we recover before the customer notices?"** If the answer is "no recovery
path," the fulfillment plan has a fatal gap.

---

## The Fulfillment Chain

Every cross-border order passes through six links. A failure at any link breaks
the chain. Optimize each link independently, then optimize the handoffs between
them.

```
FACTORY ──> FREIGHT ──> CUSTOMS ──> WAREHOUSE ──> LAST-MILE ──> CUSTOMER
  |            |           |            |             |             |
  |            |           |            |             |             |
Pick up     Sea/Air/    Clearance    Receive,      Carrier       Delivered,
from        Rail/       + duty      store,        picks up,     tracking
factory,    Express     payment     pick/pack     delivers      confirmed,
quality                                           to door       review
inspect                                                         window
```

### Link 1: Factory Pickup

- Coordinate pickup date with production schedule (buffer 3-5 days for QC)
- Inspect goods before they leave the factory (photos, weight, count)
- Ensure export packaging meets carrier and destination requirements
- Confirm carton dimensions and weights match booking details exactly
- Get factory to provide packing list and commercial invoice drafts

### Link 2: International Freight

Choose the right mode based on cost, speed, and volume. See
`references/shipping-methods.md` for detailed comparison.

| Mode | Cost Range | Transit Time | Best For |
|------|-----------|--------------|----------|
| Sea (FCL) | $1,500-$8,000/container | 18-40 days | Large volume, not time-sensitive |
| Sea (LCL) | $40-$80/CBM | 25-50 days | Small volume, not time-sensitive |
| Air | $4-$10/kg | 5-10 days | High-value, time-sensitive, or light goods |
| Rail (CN-EU) | $3,000-$6,000/container | 14-20 days | Mid-range cost/speed to Europe |
| Express | $20-$60/kg | 3-7 days | Samples, urgent restocks, small parcels |

### Link 3: Customs Clearance

The most common point of failure for new cross-border sellers. See
`references/customs-guide.md` for detailed guidance.

**Non-negotiable requirements:**
- Correct HS code classification (wrong code = seizure or penalty)
- Complete documentation (commercial invoice, packing list, bill of lading)
- Duty and tax prepayment or bond in place
- All required certifications and permits obtained before shipment

### Link 4: Warehouse / Fulfillment Center

Choose between FBA, 3PL, or self-fulfillment based on volume, control needs,
and cost tolerance. See `references/3pl-selection.md` for evaluation framework.

**Key warehouse operations:**
- Receiving: verify inbound count against ASN, report discrepancies within 24h
- Storage: FIFO rotation, climate control if needed, accurate bin locations
- Pick/pack: error rate target < 0.1%, ship-by-date compliance > 99%
- Inventory accuracy: cycle count variance < 1%

### Link 5: Last-Mile Delivery

Last-mile is the most expensive leg per unit and the most visible to customers.

**Performance targets by market:**
- US (FBA Prime): 1-2 day delivery, 97%+ on-time rate
- US (FBM/3PL): 3-5 day delivery, 95%+ on-time rate
- EU (FBA): 1-3 day delivery within destination country
- SEA (Shopee/Lazada): 3-7 day delivery, varies by country
- Rest of world: set expectations clearly in listing; 7-21 days acceptable

**Last-mile cost reduction strategies:**
- Use regional warehouses to reduce zone skips
- Negotiate volume rates with carriers (USPS, UPS, FedEx, Royal Mail)
- Consider injection services for international-to-domestic handoff
- Evaluate platform-provided shipping labels vs. self-ship rates

### Link 6: Customer Delivery

The chain is not complete at doorstep. It is complete when the return window
closes without incident.

- Provide proactive tracking updates (shipped, in-transit, out-for-delivery)
- Set realistic delivery date expectations in listings
- Have a protocol for "not delivered" claims (carrier investigation timeline)
- Monitor delivery success rate by carrier and region

---

## Shipping Method Decision Matrix

Use this matrix when a seller asks "how should I ship?"

```
START: How should I ship this?
  |
  +--> Q1: What is the total shipment volume?
  |     |
  |     +--> > 15 CBM (fills a 20ft container)  --> Sea FCL
  |     +--> 2-15 CBM                           --> Sea LCL or Rail (if EU)
  |     +--> < 2 CBM                            --> Go to Q2
  |
  +--> Q2: How urgently is it needed?
  |     |
  |     +--> Within 7 days    --> Express courier
  |     +--> Within 14 days   --> Air freight
  |     +--> 14-21 days       --> Rail (if EU) or Air
  |     +--> 21+ days OK      --> Sea LCL or consolidated shipping
  |
  +--> Q3: What is the product value per kg?
  |     |
  |     +--> > $30/kg   --> Air freight justified (shipping < 15% of value)
  |     +--> $10-$30/kg --> Calculate both air and sea; compare total landed cost
  |     +--> < $10/kg   --> Sea freight strongly preferred
  |
  +--> Q4: Is it a restock or initial launch inventory?
        |
        +--> Initial launch  --> Split: send 30% by air, 70% by sea
        |                       (air batch covers sales until sea arrives)
        +--> Restock          --> Sea (plan 6-8 weeks ahead)
        +--> Emergency restock --> Air or express (accept higher cost)
```

**The Split-Shipment Strategy:**
For product launches, send a fast batch (air/express) to start selling and
collecting reviews while the larger sea shipment is in transit. This avoids
the 30-40 day dead period waiting for ocean freight.

- Air batch: 200-500 units (enough for 30-45 days of initial sales)
- Sea batch: 2,000-5,000 units (main inventory, arrives 4-6 weeks later)
- Total cost increase: 10-15% vs. all-sea, but revenue starts 3-4 weeks earlier

---

## Freight Forwarder Selection Criteria

A good freight forwarder is the single most important logistics partner for a
cross-border seller. A bad one causes delays, overcharges, and customs holds.

### Must-Have Qualifications

| Criterion | Minimum Requirement | Why It Matters |
|-----------|-------------------|---------------|
| License | NVOCC/FMC licensed (ocean), IATA certified (air) | Unlicensed forwarders have no legal standing in disputes |
| Route experience | 3+ years on your specific trade lane | Route-specific knowledge prevents avoidable delays |
| Customs brokerage | Licensed customs broker on staff or vetted partner | In-house broker = faster clearance, fewer handoff errors |
| Tracking | Real-time tracking portal or regular status updates | You cannot manage what you cannot see |
| Insurance | Cargo insurance offered or recommended | Without insurance, loss is 100% your cost |
| References | 3+ verifiable e-commerce seller references | E-commerce logistics differ from traditional B2B cargo |
| Communication | Responds within 4 hours during business days | Slow response during a customs hold costs days |

### Evaluation Process

1. **Request quotes from 3-5 forwarders** for the same shipment specs
2. **Compare total cost**, not just freight rate (include origin charges,
   destination charges, customs brokerage, delivery to warehouse)
3. **Ask for transit time guarantees** and what happens when they miss
4. **Test with a small shipment first** before committing large volume
5. **Check their Amazon/FBA experience** if shipping to FBA warehouses
   (FBA has strict labeling and appointment requirements)
6. **Verify their technology** -- can they send you milestone updates
   automatically? Do they have a tracking portal?

### Pricing Red Flags

- Quote significantly below all competitors (bait pricing, surcharges later)
- No breakdown of charges (lump-sum quote hides markups)
- "Estimated" delivery charges with no cap
- No mention of peak season surcharges
- Requiring full payment before shipment pickup

---

## Customs Clearance Workflow

This is the standard workflow. For country-specific details, see
`references/customs-guide.md`.

```
Step 1: CLASSIFY
  Determine correct HS code for every SKU.
  Use destination country's tariff schedule, not origin country.
  When in doubt, get a binding ruling from customs authority.
       |
Step 2: DOCUMENT
  Prepare: commercial invoice, packing list, bill of lading/airway bill,
  certificate of origin, any product-specific certificates.
  All documents must match exactly (quantities, values, descriptions).
       |
Step 3: DECLARE
  File entry with customs (your broker does this).
  Declared value must be accurate -- under-declaration is fraud.
  Include all required permits, licenses, and certificates.
       |
Step 4: PAY
  Duties + taxes must be paid or bonded before release.
  Methods: direct pay, customs bond (US), deferment account (EU).
  Budget 2-5 business days for payment processing.
       |
Step 5: EXAMINE (if selected)
  Customs may examine shipment (random or triggered by risk flags).
  Examination adds 3-10 business days.
  Ensure packaging is professional; sloppy packing triggers suspicion.
       |
Step 6: RELEASE
  Goods cleared; can proceed to warehouse.
  Keep all customs paperwork for 5+ years (audits happen).
```

**Common triggers for customs examination:**
- New importer (first 3-5 shipments are more likely to be examined)
- HS code mismatch between declared and actual goods
- Declared value significantly below market price
- Origin country flagged for specific product categories
- Incomplete or inconsistent documentation
- Random selection (unavoidable, 2-5% of shipments)

---

## 3PL vs FBA Decision Framework

This is the most common fulfillment question. The answer depends on the
seller's specific situation.

| Factor | FBA Wins When... | 3PL Wins When... |
|--------|-----------------|-----------------|
| **Sales volume** | Steady, predictable sales | Highly seasonal or variable |
| **Product size** | Standard size (lower fees) | Oversized (FBA fees punishing) |
| **Multi-channel** | Amazon-only sales | Selling on Amazon + Shopify + Walmart |
| **Prime badge** | Critical for conversion | Not selling on Amazon |
| **Control** | Willing to accept Amazon's rules | Need custom packaging, inserts, kitting |
| **Cost at scale** | < 3,000 units/month | > 5,000 units/month (negotiate 3PL rates) |
| **Returns** | Standard products, low return rate | Complex returns needing inspection |
| **Storage** | Fast-turning inventory (<90 days) | Slower turn or needs long-term storage |
| **Prep requirements** | Simple products, no bundling | Kitting, bundling, custom assembly |

**Hybrid approach (recommended for most sellers at scale):**
- Use FBA for Amazon orders (Prime badge, conversion lift)
- Use 3PL for all other channels (Shopify, Walmart, eBay, TikTok Shop)
- 3PL handles FBA replenishment shipments (prep, label, ship to FC)
- This gives Prime benefits while maintaining multi-channel flexibility

---

## Returns Logistics

Returns are the hidden cost that destroys margins. Plan for them, budget for
them, and minimize them.

### Return Rate Benchmarks by Category

| Category | Expected Return Rate | Primary Return Reasons |
|----------|---------------------|----------------------|
| Clothing/Apparel | 20-35% | Size/fit issues |
| Electronics | 10-18% | Defective, not as described |
| Home & Kitchen | 5-10% | Not as expected, damaged |
| Beauty/Personal Care | 3-7% | Allergic reaction, not as described |
| Tools/Hardware | 3-6% | Wrong item, does not fit application |
| Toys/Games | 5-10% | Defective, missing parts |

### Returns Strategy by Market

**US (Amazon FBA):**
- Amazon handles returns automatically; returned items graded
- Grade A (sellable): back into inventory automatically
- Grade B-D (unfulfillable): removal order needed; decide liquidate vs. dispose
- Budget $3-$8 per return in total cost (FBA processing + potential loss)

**EU:**
- Return shipping is often seller-paid (consumer protection laws)
- Consider a local returns address in each major market (DE, FR, UK)
- Use a returns aggregation service to batch returns back to main warehouse

**Cross-border direct ship:**
- Do not ask international customers to return items to China (cost > product)
- For items under $30: refund without return (cheaper than logistics)
- For items $30-$100: offer partial refund or local return address
- For items over $100: provide prepaid return label to regional warehouse

### Reducing Return Rates

1. **Accurate listings**: dimensions, materials, weight -- exact numbers
2. **Quality photos**: show scale, show product in use, show packaging
3. **Size guides**: for apparel, provide measurements in cm AND inches
4. **QC before shipping**: inspect 100% of first 3 batches; 10% ongoing AQL
5. **Packaging**: product must survive a 1-meter drop test minimum
6. **Insert cards**: assembly instructions, usage tips, support contact

---

## Tracking and Visibility Best Practices

Customers expect to know where their package is at all times. Sellers need
visibility to manage exceptions before they become complaints.

### Minimum Tracking Standards

| Shipment Stage | Update Frequency | Who Monitors |
|----------------|-----------------|-------------|
| Factory to port | Daily | Seller or forwarder |
| International transit | Weekly (sea), daily (air/express) | Forwarder |
| Customs clearance | Daily until cleared | Broker + seller |
| Warehouse receiving | Within 24h of arrival | 3PL/FBA |
| Last-mile delivery | Real-time (carrier tracking) | Automated alerts |

### Recommended Tools

- **International freight**: Flexport, Freightos, or forwarder's portal
- **FBA inbound**: Amazon Seller Central shipment tracking
- **Multi-carrier tracking**: AfterShip, 17track, TrackingMore
- **Customer-facing**: branded tracking page (AfterShip, Narvar, Route)
- **Exception alerts**: set up automated alerts for shipments not scanned
  within expected timeframes

### Exception Management Protocol

When a shipment goes off-track:

1. **Day 1 past expected scan**: check carrier tracking, contact forwarder
2. **Day 3 no update**: escalate with carrier, file inquiry, notify customers
   if last-mile (proactive > reactive)
3. **Day 7 no update**: file claim with carrier/forwarder, prepare replacement
   shipment for affected customers
4. **Day 14 no update**: assume lost, process refunds/replacements, pursue
   insurance claim

---

## Red Flags

### Logistics Red Flags

- **Freight forwarder asks for cash payment** -- legitimate forwarders accept
  wire transfer or credit terms
- **Customs broker cannot explain the HS code they chose** -- they are guessing,
  which means your shipment is at risk
- **3PL has no WMS (Warehouse Management System)** -- manual operations mean
  errors, and errors mean chargebacks and returns
- **Carrier tracking goes dark for 5+ days** without explanation -- escalate
  immediately; do not wait and hope
- **Freight quote is 40%+ below all other quotes** -- hidden surcharges will
  appear at destination, or the service is unreliable
- **Forwarder discourages you from buying cargo insurance** -- they may not
  want you to file claims that affect their account

### Process Red Flags

- **Shipping inventory before customs documentation is confirmed** -- goods
  will sit at port accruing storage fees until paperwork is resolved
- **Using a single freight forwarder with no backup** -- if they have capacity
  issues during peak season, you have no alternative
- **Not budgeting for duties and taxes in landed cost** -- this is a 5-25%
  cost that sellers frequently forget, destroying projected margins
- **Skipping cargo insurance on high-value shipments** -- a single lost
  container can wipe out a year of profit
- **No buffer stock plan** -- running out of stock costs more than holding
  extra inventory (lost ranking, lost sales, competitor gains)

### Customer-Facing Red Flags

- **Promising delivery dates you cannot control** -- never promise "2-day
  delivery" unless you are using FBA Prime or equivalent
- **No tracking provided** -- customers will file "item not received" claims
  and win every time
- **Return address in China for domestic marketplace orders** -- customers
  expect local returns; forcing international returns gets negative reviews
  and A-to-Z claims

---

## Cross-References

| Relationship | Skill | Purpose |
|---|---|---|
| **PREREQUISITE** | `cbec-ops:inventory-management` | Inventory levels and reorder points must be set before fulfillment plans are finalized. Fulfillment speed depends on having stock available to ship. |
| **RELATED** | `cbec-ops:pricing-strategy` | Shipping costs, duties, and fulfillment fees are major components of landed cost. Every logistics decision affects margin. |
| **RELATED** | `cbec-ops:customer-service` | Fulfillment failures (late, damaged, lost) generate the majority of customer service tickets. CS protocols must align with fulfillment SLAs. |
| **RELATED** | `cbec-ops:risk-management` | Cargo loss, customs seizure, carrier bankruptcy, and natural disasters are fulfillment risks that require mitigation plans. |
| **RELATED** | `cbec-ops:platform-compliance` | Platform-specific fulfillment requirements (FBA prep, labeling, shipping plan creation) and performance metrics (late shipment rate, valid tracking rate). |
| **RELATED** | `cbec-ops:seasonal-planning` | Peak season shipping (Q4, Prime Day, 11.11) requires booking freight 4-8 weeks earlier and budgeting 20-50% higher rates. |

---

## Reference Data

For detailed reference tables and evaluation frameworks, load:

- `references/shipping-methods.md` -- Shipping mode comparison with cost,
  transit time, and route-specific recommendations.
- `references/customs-guide.md` -- HS code classification, duty calculation,
  documentation requirements, and country-specific regulations.
- `references/3pl-selection.md` -- 3PL evaluation criteria, SLA benchmarks,
  cost comparison framework, and provider recommendations by region.

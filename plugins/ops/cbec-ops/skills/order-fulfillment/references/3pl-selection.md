# 3PL (Third-Party Logistics) Provider Selection Guide

Comprehensive reference for evaluating, selecting, and managing 3PL providers
for cross-border e-commerce fulfillment.

## Table of Contents

1. [When to Use 3PL vs FBA vs Self-Fulfillment](#1-when-to-use-3pl-vs-fba-vs-self-fulfillment)
2. [3PL Evaluation Criteria](#2-3pl-evaluation-criteria)
3. [Key SLA Benchmarks](#3-key-sla-benchmarks)
4. [Cost Comparison Framework](#4-cost-comparison-framework)
5. [Popular 3PL Providers by Region](#5-popular-3pl-providers-by-region)
6. [Integration Requirements](#6-integration-requirements)
7. [Contract Negotiation Points](#7-contract-negotiation-points)
8. [Transition Planning](#8-transition-planning)
9. [Performance Monitoring Metrics](#9-performance-monitoring-metrics)

---

## 1. When to Use 3PL vs FBA vs Self-Fulfillment

### Decision Matrix

| Factor | Self-Fulfillment | FBA | 3PL |
|--------|-----------------|-----|-----|
| **Monthly order volume** | < 200 orders | 200-10,000 orders | 500-100,000+ orders |
| **Sales channels** | Single channel | Amazon only or Amazon primary | Multi-channel (Amazon + Shopify + Walmart + others) |
| **Product type** | Simple, standard | Standard size, not fragile | Any type, including oversized, fragile, kitting |
| **Customization needs** | Full control | None (Amazon's process) | Moderate to high (custom packaging, inserts, bundling) |
| **Capital available** | Low (minimal setup) | Moderate (FBA fees are predictable) | Moderate to high (setup costs + monthly minimums) |
| **Geographic reach** | Local/regional | Amazon's network (fast Prime delivery) | Flexible (choose locations based on customer base) |
| **Brand experience** | Full control of unboxing | Amazon generic packaging | Custom branded packaging available |
| **Returns handling** | You handle everything | Amazon handles (limited control) | Customizable returns processing |
| **Scalability** | Limited by your space/staff | High (Amazon scales for you) | High (3PL scales with contracted capacity) |

### Decision Flow

```
START: Which fulfillment model should I use?
  |
  +--> Q1: Are you selling exclusively on Amazon?
  |     |
  |     +--> Yes --> FBA is default choice (Prime badge value is significant)
  |     |           But consider 3PL if:
  |     |           - Products are oversized (FBA fees are punishing)
  |     |           - You need custom prep or kitting
  |     |           - Long-term storage costs exceed 3PL rates
  |     |
  |     +--> No --> Go to Q2
  |
  +--> Q2: How many orders per month across all channels?
  |     |
  |     +--> < 200/month  --> Self-fulfillment (3PL minimums may exceed your volume)
  |     +--> 200-1,000    --> 3PL or FBA+FBM hybrid
  |     +--> 1,000+       --> 3PL strongly recommended
  |
  +--> Q3: Do you need custom packaging, inserts, or kitting?
  |     |
  |     +--> Yes --> 3PL (FBA does not support custom packaging)
  |     +--> No  --> FBA or 3PL (compare costs)
  |
  +--> Q4: What is your acceptable delivery speed?
        |
        +--> 1-2 day required  --> FBA (Prime) or 3PL with distributed inventory
        +--> 3-5 day acceptable --> 3PL with 1-2 strategic locations
        +--> 5-7 day acceptable --> 3PL with single location (lowest cost)
```

### Hybrid Model (Recommended for Growing Sellers)

Most successful cross-border sellers at scale use a hybrid approach:

- **FBA** for Amazon orders (Prime badge drives conversion)
- **3PL** for non-Amazon channels (Shopify, Walmart, TikTok Shop, eBay)
- **3PL** handles FBA replenishment (prep, label, ship to Amazon FCs)

This gives you the Prime conversion benefit while maintaining multi-channel
flexibility and custom branding capabilities.

---

## 2. 3PL Evaluation Criteria

Evaluate every 3PL candidate against these 15 criteria. Score each 1-5 and
use the weighted total to compare providers.

| # | Criterion | Weight | What to Assess |
|---|-----------|--------|---------------|
| 1 | **Location** | High | Proximity to your customers (zone analysis), proximity to ports/airports for inbound |
| 2 | **Warehouse capacity** | High | Current available space, ability to accommodate growth, dedicated vs shared space |
| 3 | **Technology / WMS** | High | Warehouse management system capabilities, real-time inventory visibility, reporting |
| 4 | **Order accuracy rate** | High | Historical accuracy percentage; target: 99.8%+ |
| 5 | **Shipping speed** | High | Same-day or next-day shipping cutoff time; ability to meet platform SLAs |
| 6 | **Carrier relationships** | Medium | Which carriers they work with, negotiated rates, multi-carrier capability |
| 7 | **Integration capability** | High | API availability, pre-built integrations with your sales channels and inventory tools |
| 8 | **Pricing transparency** | Medium | Clear rate card, no hidden fees, predictable monthly costs |
| 9 | **Returns processing** | Medium | Returns workflow, inspection capability, restocking efficiency |
| 10 | **Customer service / communication** | Medium | Dedicated account manager, response time, escalation procedures |
| 11 | **Scalability** | Medium | Can they handle 2-5x your current volume during peak season? |
| 12 | **Value-added services** | Low | Kitting, bundling, custom packaging, gift wrapping, product photography |
| 13 | **Security and compliance** | Medium | SOC 2 compliance, insurance coverage, product handling certifications |
| 14 | **Financial stability** | Low | Years in business, client references, evidence of investment in infrastructure |
| 15 | **Contract flexibility** | Medium | Minimum commitments, exit clauses, rate adjustment terms |

### Evaluation Scoring Guide

| Score | Meaning |
|-------|---------|
| 5 | Exceeds requirements; best-in-class for this criterion |
| 4 | Meets all requirements with some additional strengths |
| 3 | Meets minimum requirements; adequate |
| 2 | Partially meets requirements; concerns exist |
| 1 | Does not meet requirements; significant gap |

### Minimum Acceptable Scores

For a 3PL to be considered viable, they should score at minimum:

- All "High" weight criteria: 3 or above
- All "Medium" weight criteria: 2 or above
- Weighted total: 50+ out of 75 maximum
- No single criterion scores 1 if it has High weight

### Location Strategy

3PL warehouse location directly affects shipping cost and delivery speed.

**US market:**
| Location Strategy | Best For | Trade-off |
|------------------|---------|-----------|
| Single West Coast (CA) | Sellers shipping primarily to western US, close to port of entry | Slow/expensive delivery to East Coast |
| Single East Coast (NJ/PA) | Sellers with nationwide customer base (population-weighted center) | Longer from West Coast ports |
| Single Central (TX/KY/OH) | Balanced delivery to both coasts | Not optimal for either coast |
| Dual location (CA + NJ/PA) | Sellers with 5,000+ orders/month wanting 2-3 day nationwide | Higher fixed costs, inventory splitting complexity |
| Distributed (3+ locations) | Enterprise sellers wanting 1-2 day nationwide | Highest cost, complex inventory management |

**EU market:**
| Location Strategy | Best For |
|------------------|---------|
| Germany (NRW/Hessen) | Largest EU market, central location for DE/NL/BE/AT |
| Netherlands | Port of Rotterdam access, good distribution to Western EU |
| Poland | Lower labor costs, growing e-commerce infrastructure, good for Central/Eastern EU |
| UK (post-Brexit) | Must have separate UK warehouse for UK sales (customs border with EU) |
| Multi-country (DE + FR + IT) | Pan-EU FBA or pan-EU 3PL for fast local delivery |

---

## 3. Key SLA Benchmarks

Service Level Agreements define the performance standards your 3PL must meet.
These benchmarks represent industry best practice for e-commerce fulfillment.

### Order Fulfillment SLAs

| Metric | Target | Acceptable | Unacceptable |
|--------|--------|-----------|-------------|
| **Order accuracy rate** | 99.9% | 99.5% | < 99.0% |
| **Same-day ship rate** (orders received before cutoff) | 99.5% | 98.0% | < 95.0% |
| **Average ship time** (receipt to carrier pickup) | < 4 hours | < 24 hours | > 48 hours |
| **Shipping cutoff time** | 2:00 PM local | 12:00 PM local | Before 10:00 AM |
| **Backorder fill rate** | 98.0% | 95.0% | < 90.0% |

### Inventory Management SLAs

| Metric | Target | Acceptable | Unacceptable |
|--------|--------|-----------|-------------|
| **Inventory accuracy** (cycle count) | 99.9% | 99.5% | < 99.0% |
| **Receiving turnaround** (inbound to available) | < 24 hours | < 48 hours | > 72 hours |
| **Shrinkage rate** (lost/damaged in warehouse) | < 0.1% | < 0.5% | > 1.0% |
| **Inventory reporting frequency** | Real-time | Daily | Weekly |
| **Lot/expiry tracking** (if applicable) | FIFO enforced | FIFO attempted | No tracking |

### Returns Processing SLAs

| Metric | Target | Acceptable | Unacceptable |
|--------|--------|-----------|-------------|
| **Returns processing time** | < 24 hours | < 48 hours | > 72 hours |
| **Return inspection accuracy** | 99.0% | 97.0% | < 95.0% |
| **Restocking turnaround** (Grade A items) | < 24 hours | < 48 hours | > 72 hours |
| **Return disposition reporting** | Same day | Next day | Weekly batch |

### Communication SLAs

| Metric | Target | Acceptable | Unacceptable |
|--------|--------|-----------|-------------|
| **Issue response time** (business hours) | < 2 hours | < 4 hours | > 8 hours |
| **Escalation response time** | < 1 hour | < 2 hours | > 4 hours |
| **Root cause analysis** (for errors) | < 24 hours | < 48 hours | > 1 week |
| **Account review frequency** | Weekly | Bi-weekly | Monthly |

### SLA Enforcement

- Define financial penalties for SLA misses (credits against billing)
- Track metrics monthly with a shared dashboard
- Quarterly business reviews to discuss trends and improvement plans
- Persistent SLA failures (3+ consecutive months) should trigger escalation
  or exit planning

---

## 4. Cost Comparison Framework

3PL pricing is complex. Use this framework to compare providers on a true
total-cost basis. Request quotes using the same shipment profile from each
provider.

### Standard 3PL Fee Categories

| Fee Category | Description | Typical Range (US) |
|-------------|-------------|-------------------|
| **Receiving** | Per unit or per pallet inbound processing | $0.20-$0.50/unit or $15-$35/pallet |
| **Storage** | Monthly per pallet or per cubic foot | $15-$40/pallet/month or $0.50-$1.50/cuft/month |
| **Pick and pack** | Per order + per item picked | $2.50-$5.00/order + $0.50-$1.00/item |
| **Packaging materials** | Boxes, poly mailers, bubble wrap, tape | $0.50-$3.00/order (varies by material) |
| **Shipping** | Actual carrier cost (passed through or marked up) | Varies; ask for rate card |
| **Returns processing** | Per unit returned, inspected, restocked | $2.00-$5.00/unit |
| **Kitting/assembly** | Per kit assembled | $1.00-$5.00/kit (varies by complexity) |
| **Labeling** | FBA labels, shipping labels, custom labels | $0.10-$0.50/label |
| **Account management** | Monthly fee for dedicated support | $0-$500/month (often included above certain volume) |
| **Technology fee** | WMS access, integrations, reporting | $0-$300/month (often included) |
| **Minimum monthly fee** | Minimum billing regardless of activity | $250-$1,000/month |

### Total Cost Per Order Calculation

```
Total cost per order = Receiving (amortized per unit)
                     + Storage (amortized per unit sold)
                     + Pick fee
                     + Pack fee
                     + Packaging materials
                     + Shipping cost
                     + Returns processing (amortized based on return rate)
                     + Technology / account fees (amortized per order)

Example:
Receiving: $0.30/unit (spread across 500 units received)
Storage: $0.15/unit/month x 2 months avg = $0.30
Pick: $3.00/order
Pack: $0.75/item x 1.2 items avg = $0.90
Packaging: $0.80/order
Shipping: $5.50 (average across zones)
Returns: $3.50 x 8% return rate = $0.28
Tech/admin: $200/month / 1,000 orders = $0.20

TOTAL per order: $11.28
```

### FBA vs 3PL Cost Comparison Template

| Cost Component | FBA (per unit) | 3PL (per unit) | Notes |
|---------------|---------------|----------------|-------|
| Inbound shipping to warehouse | $X.XX | $X.XX | FBA: partnered carrier; 3PL: your arrangement |
| Receiving/processing | Included in FBA fee | $X.XX | FBA includes; 3PL charges separately |
| Storage (per month) | $X.XX | $X.XX | FBA: seasonal rates; 3PL: negotiated rate |
| Pick and pack | Included in FBA fee | $X.XX | FBA includes; 3PL charges separately |
| Outbound shipping | Included in FBA fee | $X.XX | FBA includes; 3PL: carrier rates |
| **Total fulfillment fee** | **$X.XX** | **$X.XX** | Compare all-in per unit |
| FBA long-term storage fee | $X.XX (if applicable) | N/A | FBA charges extra for inventory aged 181+ days |
| FBA aged inventory surcharge | $X.XX (if applicable) | N/A | Additional fee for inventory aged 271+ days |
| Prime badge value | Estimated conversion lift | N/A | FBA gives Prime; hard to quantify but real |
| Returns processing | Included | $X.XX | FBA handles returns; 3PL charges per return |

**Important:** FBA fees look expensive line-by-line, but they include shipping
to the customer. When comparing, include the 3PL's shipping cost in the total.
For small, standard-size items, FBA is often cheaper than 3PL when you factor
in FBA's negotiated carrier rates. For oversized items, 3PL is almost always
cheaper.

### Hidden Costs to Watch For

- **Minimum order fees**: some 3PLs charge a minimum per order even if the
  actual cost is less
- **Dimensional weight surcharges**: charged when box size exceeds carrier's
  dimensional weight thresholds
- **Special handling fees**: items requiring careful handling, temperature
  control, or hazmat processing
- **Peak season surcharges**: 10-30% uplift during Q4 (ask about this upfront)
- **Account closure/transition fees**: some 3PLs charge fees for transferring
  inventory out
- **Inventory adjustment fees**: charges for cycle count discrepancies
- **Rush order fees**: expedited processing for same-day or next-day shipping
- **Saturday/Sunday processing**: if offered, usually at premium rates

---

## 5. Popular 3PL Providers by Region

### US-Based 3PLs

| Provider | Best For | Minimum Volume | Key Strengths |
|----------|---------|---------------|--------------|
| **ShipBob** | DTC brands, mid-volume | ~200 orders/month | Multi-warehouse network, strong integrations, transparent pricing |
| **Deliverr (now Flexport)** | Amazon, Walmart, multi-marketplace | ~500 orders/month | Multi-channel fulfillment, 2-day delivery badge (Walmart) |
| **ShipMonk** | Growing DTC brands | ~200 orders/month | Custom packaging, kitting, good tech platform |
| **Red Stag Fulfillment** | Heavy/oversized products | ~200 orders/month | Specializes in heavy items, guaranteed accuracy |
| **Fulfillment by Amazon (FBA)** | Amazon sellers (any size) | No minimum | Prime badge, massive network, scalable |
| **Amazon MCF** | Amazon sellers wanting multi-channel from FBA | Active FBA inventory | Uses FBA inventory for non-Amazon orders |
| **Rakuten Super Logistics** | Enterprise, high volume | ~1,000 orders/month | 2-day ground delivery network, strong SLAs |
| **ShipHero** | Mid-market brands | ~500 orders/month | WMS + 3PL hybrid, good for brands wanting control |

### EU-Based 3PLs

| Provider | Best For | Key Markets | Key Strengths |
|----------|---------|-------------|--------------|
| **byrd** | DTC brands in EU | DE, AT, NL, FR, UK | Pan-EU network, multi-warehouse, strong integrations |
| **Huboo** | Small to mid-size sellers | UK, DE, NL, ES | Low minimum, good for Amazon + DTC |
| **Hive** | DTC brands | DE, FR, NL | Sustainable focus, modern tech platform |
| **Amazon Pan-EU FBA** | Amazon sellers in EU | All EU countries | Multi-country placement, Prime badge, scalable |
| **Logsta** | Central/Eastern EU | AT, DE, CZ, HU | Competitive pricing, good for CE markets |
| **Active Ants** | Mid to large volume | NL, DE, BE, UK | High automation, scalable, strong SLAs |

### SEA-Based 3PLs

| Provider | Best For | Key Markets | Key Strengths |
|----------|---------|-------------|--------------|
| **Shopee Logistics (SPX)** | Shopee sellers | SG, MY, ID, TH, VN, PH | Integrated with Shopee, competitive last-mile rates |
| **Lazada Logistics (LEX)** | Lazada sellers | SG, MY, ID, TH, VN, PH | Integrated with Lazada, warehouse-to-door |
| **J&T Express** | Multi-platform SEA sellers | ID, VN, MY, PH, TH, SG | Wide coverage, fast last-mile, competitive pricing |
| **Locad** | Multi-channel DTC in SEA | SG, PH, AU, HK, TH | Modern platform, multi-market, good integrations |
| **Anchanto** | Enterprise, multi-market | Pan-SEA + AU | Full suite (WMS + OMS + analytics), enterprise-grade |

### Choosing Between Providers

1. **Start with location**: which provider has warehouses closest to your
   customer concentration?
2. **Match volume tier**: do not choose an enterprise 3PL if you ship 200
   orders/month; their minimums will eat your margin
3. **Check integrations**: does the 3PL integrate with your sales channels,
   inventory tools, and shipping accounts?
4. **Request references**: talk to 2-3 current clients in a similar product
   category and volume tier
5. **Test before committing**: send a trial batch of 100-500 units and
   evaluate receiving, storage, and shipping performance before signing a
   long-term contract

---

## 6. Integration Requirements

A 3PL is only as good as its data connections. Poor integration means manual
work, errors, and delays.

### Essential Integrations

| Integration | Purpose | Priority |
|------------|---------|---------|
| **Sales channel sync** | Auto-push orders from Amazon, Shopify, Walmart, etc. to 3PL | Critical |
| **Inventory sync** | Real-time inventory levels pushed back to sales channels | Critical |
| **Shipping label generation** | Auto-generate labels with correct carrier and service | Critical |
| **Tracking sync** | Push tracking numbers back to sales channels and customers | Critical |
| **Returns management** | Process return authorizations and update inventory | High |
| **Purchase order / ASN** | Notify 3PL of incoming inventory with expected quantities | High |
| **Reporting / analytics** | Access to fulfillment KPIs, cost data, inventory reports | Medium |
| **Accounting / ERP** | Sync fulfillment costs with accounting system | Medium |

### Integration Methods

| Method | Reliability | Setup Effort | Best For |
|--------|-----------|-------------|----------|
| **Native integration** (pre-built connector) | High | Low (plug and play) | Standard platforms (Shopify, Amazon, WooCommerce) |
| **API integration** (custom) | High | High (development needed) | Custom platforms, complex workflows |
| **EDI** | High | Medium | Enterprise, high-volume B2B |
| **Flat file / CSV** | Low | Low | Fallback only; avoid for production |
| **Manual entry** | Very low | None | Unacceptable above 20 orders/day |

### Integration Red Flags

- 3PL has no API and relies on CSV uploads for order processing
- Integration is "coming soon" but not yet available for your platform
- Real-time inventory sync is not available (only daily batch updates)
- No webhook or push notification for order status changes
- Tracking numbers must be manually copied from 3PL portal to sales channel
- Integration requires a paid third-party middleware (adds cost and failure point)

### WMS (Warehouse Management System) Requirements

The 3PL's WMS should provide at minimum:

- [ ] Real-time inventory visibility by SKU and location
- [ ] Order status tracking (received, picking, packing, shipped)
- [ ] Lot and expiry date tracking (if applicable)
- [ ] Serial number tracking (if applicable)
- [ ] Receiving workflow with discrepancy reporting
- [ ] Cycle count functionality
- [ ] Returns processing workflow
- [ ] Multi-channel order prioritization rules
- [ ] Reporting dashboard (inventory levels, order volume, SLA metrics)
- [ ] User access controls (view-only vs. full access)

---

## 7. Contract Negotiation Points

### Key Contract Terms to Negotiate

| Term | What to Push For | Common Pitfall |
|------|-----------------|---------------|
| **Contract length** | 12 months max initially; month-to-month after | Locked into 24+ months with an untested provider |
| **Volume commitment** | Realistic minimums based on current volume, not projections | Over-committing to minimums and paying for unused capacity |
| **Rate card lock** | Fixed rates for at least 6 months; maximum annual increase cap (3-5%) | Rates increase after 3 months with no cap |
| **Exit clause** | 30-60 day notice to terminate; no early termination fees after first 6 months | 90+ day notice or hefty early termination penalty |
| **SLA penalties** | Financial credits (10-25% of monthly fees) for persistent SLA failures | SLAs with no teeth (no financial consequence for missing targets) |
| **Peak season rates** | Cap peak surcharges at 15-20% above base rates; define peak months | Unlimited peak surcharges applied to 4+ months of the year |
| **Storage rates** | All-in rate per pallet; no separate "handling" surcharges on stored goods | Low storage rate but high monthly "inventory management" fees |
| **Inventory liability** | 3PL responsible for shrinkage and damage beyond agreed thresholds | 3PL disclaims all liability for lost/damaged inventory |
| **Insurance** | 3PL carries warehouse legal liability insurance; minimum $1M coverage | No insurance or coverage limited to pennies on the dollar |
| **Data ownership** | You own all order, inventory, and customer data; exportable at any time | Data locked in 3PL's system; no export capability |
| **Transition support** | 3PL assists with inventory transfer to next provider at no additional charge | Exit fee + no support for inventory transfer |

### Negotiation Leverage Points

- **Volume trajectory**: show credible growth projections to negotiate lower
  per-unit rates
- **Multi-year potential**: offer a longer commitment in exchange for rate
  concessions
- **Off-peak start**: starting during slow season (January-March) gives
  3PL an incentive to onboard you
- **Competitor quotes**: having 2-3 competing quotes gives you pricing leverage
- **Payment terms**: offering faster payment (net 15 vs. net 30) may get
  rate concessions
- **Referral value**: if you are a recognizable brand, the 3PL may discount
  for marketing/reference value

### Contract Provisions to Avoid

- Automatic renewal clauses without opt-out window
- Exclusive fulfillment agreements (you should be free to use FBA alongside)
- Unlimited rate adjustment clauses
- Waiver of liability for shipping errors
- Non-compete clauses that restrict you from using other 3PLs
- Mandatory arbitration in a jurisdiction far from you

---

## 8. Transition Planning

Transitioning between fulfillment providers (self to 3PL, 3PL to 3PL, or
FBA to 3PL) is one of the highest-risk logistics operations. Plan carefully.

### Transition Timeline

| Phase | Duration | Activities |
|-------|---------|-----------|
| **Planning** | 4-6 weeks | Select new 3PL, sign contract, define processes, set up integrations |
| **Testing** | 2-4 weeks | Send test inventory, process test orders, validate accuracy and speed |
| **Parallel run** | 2-4 weeks | Both old and new providers active; route a percentage of orders to new 3PL |
| **Full cutover** | 1-2 weeks | Shift all orders to new 3PL; drain old inventory |
| **Stabilization** | 2-4 weeks | Monitor SLAs closely, resolve issues, optimize workflows |
| **Total** | **10-18 weeks** | |

### Transition Checklist

**Pre-transition (4-6 weeks before):**
- [ ] New 3PL contract signed with agreed SLAs and rates
- [ ] All sales channel integrations set up and tested
- [ ] SKU master data transferred (dimensions, weights, barcodes, images)
- [ ] Shipping preferences configured (carrier, service level, packaging)
- [ ] Returns workflow documented and configured
- [ ] Receiving procedures documented (labeling, inspection requirements)
- [ ] Escalation contacts established (your team and 3PL team)

**Testing phase (2-4 weeks before):**
- [ ] Ship 100-500 units of top SKUs to new 3PL
- [ ] Process 20-50 test orders (cover different scenarios: single item,
      multi-item, oversized, international)
- [ ] Verify order accuracy, packaging quality, shipping speed
- [ ] Test returns workflow with 5-10 simulated returns
- [ ] Validate inventory sync (counts match between WMS and sales channels)
- [ ] Confirm tracking number propagation to sales channels

**Parallel run (2-4 weeks):**
- [ ] Route 10-25% of orders to new 3PL
- [ ] Monitor SLAs daily (accuracy, ship time, tracking)
- [ ] Compare new 3PL performance against old provider
- [ ] Resolve any integration issues discovered during live orders
- [ ] Gradually increase percentage to 50%, then 75%, then 100%

**Full cutover:**
- [ ] Stop sending new inventory to old provider
- [ ] Transfer remaining inventory from old provider to new 3PL
- [ ] Update all sales channel fulfillment settings to new 3PL
- [ ] Verify zero open orders at old provider
- [ ] Settle final invoice with old provider
- [ ] Confirm all inventory received at new 3PL matches transfer manifest

**Post-transition (first 4 weeks):**
- [ ] Daily SLA monitoring (relax to weekly after 2 weeks if stable)
- [ ] Weekly call with 3PL account manager
- [ ] Address any receiving discrepancies from transferred inventory
- [ ] Update customer service team with new tracking and support contacts
- [ ] Document lessons learned for future transitions

### Risk Mitigation During Transition

| Risk | Mitigation |
|------|-----------|
| Stockout during transfer | Maintain 4-6 weeks of safety stock at old location during transition |
| Integration failure | Test all integrations with live data before cutover; have manual backup process |
| Inventory loss during transfer | Photograph and count all inventory before shipping; use sealed, tracked containers |
| Customer experience degradation | Avoid transitioning during peak season; pad delivery estimates during parallel run |
| Billing disputes with old provider | Get final inventory count signed by both parties; settle within 30 days of exit |

---

## 9. Performance Monitoring Metrics

Once your 3PL is operational, monitor these metrics continuously. Build a
shared dashboard that both you and the 3PL can access.

### Tier 1 Metrics (Monitor Daily)

| Metric | Formula | Target | Action Threshold |
|--------|---------|--------|-----------------|
| **Order accuracy** | (Orders shipped correctly / Total orders shipped) x 100 | 99.8%+ | Investigate at < 99.5% |
| **Same-day ship rate** | (Orders shipped same day / Orders received before cutoff) x 100 | 99.0%+ | Escalate at < 97.0% |
| **On-time delivery rate** | (Orders delivered within promised window / Total orders delivered) x 100 | 97.0%+ | Escalate at < 95.0% |
| **Inventory accuracy** | (System count / Physical count) x 100 | 99.9%+ | Cycle count at < 99.5% |

### Tier 2 Metrics (Monitor Weekly)

| Metric | Formula | Target | Action Threshold |
|--------|---------|--------|-----------------|
| **Receiving turnaround** | Average time from dock receipt to available inventory | < 24 hours | Escalate at > 48 hours |
| **Return processing time** | Average time from return receipt to disposition | < 24 hours | Escalate at > 48 hours |
| **Cost per order** | Total 3PL charges / Total orders shipped | Track trend | Investigate if increasing > 5% month-over-month |
| **Damage rate** | (Units reported damaged in transit / Total units shipped) x 100 | < 0.5% | Investigate at > 1.0% |
| **Customer complaint rate** (fulfillment-related) | Fulfillment complaints / Total orders x 100 | < 1.0% | Root cause at > 2.0% |

### Tier 3 Metrics (Monitor Monthly)

| Metric | Formula | Target | Action Threshold |
|--------|---------|--------|-----------------|
| **Shrinkage rate** | (Units lost or unaccounted / Total units stored) x 100 | < 0.1% | Audit at > 0.3% |
| **Storage utilization** | (Space used / Space allocated) x 100 | 60-85% | Negotiate more/less space outside range |
| **Carrier performance** | On-time rate by carrier and service level | Varies by carrier | Switch carriers at < 93% on-time |
| **Peak capacity handling** | Orders shipped in peak week / Average weekly orders | Track ratio | Ensure 3PL can handle 2-3x normal volume |
| **Invoice accuracy** | (Correct invoices / Total invoices) x 100 | 99.0%+ | Audit every invoice at < 98% |

### Performance Review Cadence

| Review Type | Frequency | Participants | Agenda |
|------------|-----------|-------------|--------|
| **Daily check** | Daily | Your ops team | Tier 1 metrics, exception handling |
| **Weekly review** | Weekly | Your ops + 3PL account manager | Tier 1+2 metrics, open issues, upcoming volume |
| **Monthly business review** | Monthly | Your ops lead + 3PL management | All metrics, cost trends, SLA compliance, improvement plans |
| **Quarterly strategy review** | Quarterly | Your leadership + 3PL leadership | Growth planning, rate negotiation, technology roadmap |

### When to Consider Changing 3PLs

Consider beginning a transition if:

- SLA metrics consistently below acceptable thresholds for 3+ months
- 3PL is unresponsive to escalations or resistant to process improvements
- Pricing has increased significantly with no corresponding service improvement
- 3PL cannot scale for your growth (peak season failures, capacity limits)
- Technology platform is falling behind (no API, no real-time inventory sync)
- Financial instability concerns (delayed communications, staff turnover,
  facility downgrades)
- Your business has outgrown the provider's target market segment

**Warning:** Switching 3PLs is disruptive and risky. Exhaust all improvement
options with your current provider before deciding to transition. The cost
of a bad transition often exceeds the cost of tolerating a slightly
underperforming provider for another quarter while they improve.

# Shipping Methods Comparison

Comprehensive reference for cross-border e-commerce shipping modes. Use this
to select the right shipping method based on cost, speed, volume, and route.

## Table of Contents

1. [Sea Freight](#1-sea-freight)
2. [Air Freight](#2-air-freight)
3. [Rail Freight](#3-rail-freight)
4. [Express Courier](#4-express-courier)
5. [FBA Partnered Carrier Program](#5-fba-partnered-carrier-program)
6. [Door-to-Door vs Port-to-Port](#6-door-to-door-vs-port-to-port)
7. [Consolidated Shipping Services](#7-consolidated-shipping-services)
8. [Route-Specific Recommendations](#8-route-specific-recommendations)
9. [Insurance Options](#9-insurance-options)
10. [Peak Season Shipping](#10-peak-season-shipping)

---

## 1. Sea Freight

Sea freight is the lowest-cost option for large shipments. It is the backbone
of cross-border e-commerce logistics for sellers moving container-level or
near-container-level volume.

### FCL (Full Container Load)

You book an entire container. The container is sealed at the factory and opened
at the destination warehouse.

| Container Type | Internal Dimensions (L x W x H) | Capacity (CBM) | Max Payload (kg) | Typical Use |
|---------------|-------------------------------|----------------|------------------|-------------|
| 20ft Standard | 5.9m x 2.35m x 2.39m | ~33 CBM | 21,700 kg | Small to medium shipments |
| 40ft Standard | 12.0m x 2.35m x 2.39m | ~67 CBM | 26,500 kg | Standard large shipments |
| 40ft High Cube | 12.0m x 2.35m x 2.69m | ~76 CBM | 26,200 kg | Light, bulky products |

**FCL Cost Ranges (indicative, fluctuates significantly):**

| Route | 20ft Container | 40ft Container | Transit Time |
|-------|---------------|---------------|-------------|
| China (Shanghai) to US West Coast | $1,500-$4,000 | $2,500-$6,000 | 14-18 days |
| China (Shanghai) to US East Coast | $2,500-$6,000 | $4,000-$9,000 | 25-35 days |
| China to Northern Europe | $1,500-$4,500 | $2,500-$7,000 | 28-35 days |
| China to UK | $2,000-$5,000 | $3,000-$8,000 | 30-38 days |
| China to Australia | $1,200-$3,000 | $2,000-$5,000 | 14-21 days |
| China to Japan | $500-$1,500 | $800-$2,500 | 4-7 days |
| China to Southeast Asia | $400-$1,500 | $700-$2,500 | 5-12 days |

**FCL additional costs (often overlooked):**
- Origin terminal handling: $100-$300
- Documentation fee: $50-$100
- Destination terminal handling: $200-$500
- Chassis usage (US): $50-$100/day
- Container drayage to warehouse: $200-$800
- Demurrage (late container return): $100-$300/day after free time
- Detention (late cargo pickup): $100-$200/day after free time

### LCL (Less than Container Load)

Your cargo shares container space with other shippers. Charged per cubic meter
(CBM) with a minimum of 1 CBM.

**LCL Cost Ranges:**

| Route | Cost per CBM | Minimum Charge | Transit Time (add to FCL) |
|-------|-------------|----------------|--------------------------|
| China to US West Coast | $40-$80 | 1 CBM | +7-14 days (consolidation) |
| China to US East Coast | $60-$100 | 1 CBM | +7-14 days |
| China to Northern Europe | $50-$90 | 1 CBM | +7-14 days |
| China to UK | $55-$95 | 1 CBM | +7-14 days |
| China to Australia | $45-$75 | 1 CBM | +5-10 days |
| China to Japan | $30-$50 | 1 CBM | +3-7 days |

**LCL disadvantages:**
- Longer transit time due to consolidation and deconsolidation
- Higher risk of damage (multiple cargo handlers)
- Less predictable schedule
- Per-CBM rate makes it uneconomical above ~10-12 CBM (switch to FCL)

### CBM Calculation

```
CBM = Length (m) x Width (m) x Height (m) x Number of cartons

Example:
Carton: 60cm x 40cm x 40cm = 0.6 x 0.4 x 0.4 = 0.096 CBM per carton
100 cartons = 9.6 CBM --> LCL is appropriate
200 cartons = 19.2 CBM --> FCL 20ft is more economical
```

### Incoterms for Sea Freight

| Incoterm | Seller Responsibility Ends At | Buyer Pays From | Best For |
|----------|------------------------------|-----------------|----------|
| **EXW** (Ex Works) | Factory gate | Everything from pickup onward | Experienced buyers with own forwarder |
| **FOB** (Free on Board) | Loaded onto vessel at origin port | Ocean freight + destination costs | Most common for CN sellers |
| **CIF** (Cost, Insurance, Freight) | Destination port (freight + insurance paid) | Unloading + destination delivery | Seller wants to control shipping cost |
| **DDP** (Delivered Duty Paid) | Customer's warehouse (all costs paid) | Nothing (all-inclusive price) | Door-to-door services, simplest for buyer |
| **DAP** (Delivered at Place) | Destination address (duties unpaid) | Import duties + taxes | When buyer has duty deferment |

**Recommendation for most sellers:** Use **FOB** when shipping to your own
warehouse or 3PL. Use **DDP** when using a door-to-door freight service. Avoid
EXW unless you have logistics expertise at origin.

---

## 2. Air Freight

Air freight is 4-6x more expensive per kg than sea freight but 5-8x faster.
Use it for high-value, lightweight, or time-sensitive shipments.

### Commercial Air Freight vs Charter

**Commercial air freight** uses belly cargo space on passenger flights or
scheduled cargo flights.

| Factor | Commercial Air | Charter |
|--------|---------------|---------|
| Cost per kg | $4-$10 | $2-$5 (for very large volumes) |
| Minimum | 45 kg (most carriers) | Full plane load |
| Transit time | 5-10 days (airport to airport) | 3-5 days |
| Schedule | Fixed routes/schedules | Flexible |
| Best for | Regular shipments < 5,000 kg | Emergency restocks > 10,000 kg |
| Booking lead time | 3-7 days | 1-3 weeks |

**Air freight cost components:**
- Freight rate: charged per kg (actual weight or volumetric, whichever is higher)
- Fuel surcharge: variable, often 20-40% of base rate
- Security surcharge: $0.05-$0.15/kg
- Terminal handling: $0.10-$0.25/kg
- Pickup/delivery: $100-$500 depending on distance
- Customs clearance: $100-$200

### Dimensional Weight Calculation

Airlines charge based on the greater of actual weight or dimensional weight.

```
Dimensional weight (kg) = Length (cm) x Width (cm) x Height (cm) / 6000

Example:
Carton: 60cm x 40cm x 40cm, actual weight 8 kg
Dimensional weight: 60 x 40 x 40 / 6000 = 16 kg
Chargeable weight: 16 kg (dimensional > actual)
--> This shipment costs DOUBLE what the actual weight suggests
```

**Implication:** Air freight is only cost-effective for dense, heavy products
relative to their size. Light, bulky products (pillows, lampshades, large
plastic items) have terrible volumetric ratios and should go by sea.

### When Air Freight Makes Sense

- Product value exceeds $30/kg (shipping cost < 15% of product value)
- Product launch: first batch to start selling while sea shipment is in transit
- Stockout prevention: emergency restock to avoid losing ranking
- Seasonal product: narrow selling window makes sea transit too slow
- Small, regular restocks: under 200 kg, where sea LCL consolidation delays
  negate the cost savings

### Air Freight Cost Ranges

| Route | Cost per kg (45+ kg) | Cost per kg (300+ kg) | Transit Days |
|-------|---------------------|----------------------|-------------|
| China to US (West Coast) | $5-$9 | $4-$7 | 5-8 |
| China to US (East Coast) | $6-$10 | $5-$8 | 6-10 |
| China to Europe | $5-$9 | $4-$7 | 5-8 |
| China to UK | $5-$9 | $4-$7 | 5-8 |
| China to Australia | $5-$8 | $4-$6 | 4-7 |
| China to Japan | $3-$6 | $2-$4 | 2-4 |
| China to Southeast Asia | $3-$5 | $2-$4 | 2-5 |

---

## 3. Rail Freight

Rail freight (primarily China-Europe) offers a middle ground between sea and
air in both cost and speed.

### China-Europe Rail Routes

| Route | Key Rail Lines | Transit Time | Cost (40ft container) |
|-------|---------------|-------------|----------------------|
| China to Germany | China Railway Express via Kazakhstan-Russia-Poland | 14-18 days | $4,000-$7,000 |
| China to Netherlands | Via Russia-Belarus-Poland | 16-20 days | $4,500-$7,500 |
| China to Spain | Via Kazakhstan-Russia-Poland-France | 18-22 days | $5,000-$8,000 |
| China to UK | Via Poland + short sea crossing | 18-24 days | $5,000-$8,500 |

### Rail vs Sea vs Air Comparison (China to Europe)

| Factor | Sea | Rail | Air |
|--------|-----|------|-----|
| Transit time | 28-38 days | 14-20 days | 5-8 days |
| Cost (per kg, approximate) | $0.50-$1.50 | $1.50-$3.00 | $4-$8 |
| Cost (40ft container) | $2,500-$7,000 | $4,000-$7,000 | N/A (per kg) |
| Reliability | Weather/port delays | Stable (fewer variables) | Flight cancellations |
| Capacity | Very high | Limited (book early) | Limited |
| Best for | Bulk, not urgent | Mid-urgency, medium volume | High-value, urgent |

### Rail Freight Limitations

- **Route concentration**: almost exclusively China-to-Europe; not viable
  for US, SEA, or Australia
- **Capacity constraints**: limited slots, especially during peak season;
  book 2-4 weeks in advance
- **Weight restrictions**: stricter than sea freight; heavy goods may face
  surcharges
- **Limited origin/destination cities**: not all Chinese cities have direct
  rail connections; may need trucking to rail terminal
- **Geopolitical risk**: routes through Russia/Central Asia subject to
  sanctions and political disruption

### When to Choose Rail

- Shipping to EU and transit time of 28-38 days (sea) is too slow
- Shipment value does not justify air freight cost
- Products are not extremely heavy (rail weight limits are tighter than sea)
- Reliable scheduling is important (rail is more consistent than sea)
- You can plan 3-4 weeks ahead for booking

---

## 4. Express Courier

Express couriers (DHL, FedEx, UPS, TNT/FedEx) provide door-to-door delivery
with full tracking, customs clearance included, and fast transit times.

### Express Courier Comparison

| Carrier | Strengths | Weaknesses | Best Routes |
|---------|----------|-----------|-------------|
| **DHL Express** | Strongest international network, reliable customs clearance, best for EU | Premium pricing, surcharges for remote areas | China-EU, China-SEA, intra-EU |
| **FedEx** | Strong US domestic, good air network, competitive rates for US-bound | Weaker in some Asian markets, complex surcharge structure | China-US, US domestic |
| **UPS** | Reliable US delivery, good for heavy parcels, competitive B2B rates | Slower international transit vs DHL, residential surcharges | China-US, intra-US B2B |
| **TNT (FedEx)** | Strong intra-EU network, good ground service | Limited outside EU, being merged into FedEx | Intra-EU |
| **SF Express** | Excellent China-SEA, competitive pricing, fast | Limited Western market coverage | China-SEA, China-Japan/Korea |

### Express Courier Cost Tiers

Pricing depends on weight, dimensions, origin, destination, and account volume.

| Weight Range | Cost per kg (China to US) | Cost per kg (China to EU) |
|-------------|--------------------------|--------------------------|
| 0.5-5 kg | $25-$50 | $25-$55 |
| 5-20 kg | $15-$30 | $15-$35 |
| 20-50 kg | $10-$20 | $10-$25 |
| 50-100 kg | $8-$15 | $8-$18 |
| 100+ kg | $6-$12 (negotiate) | $6-$15 (negotiate) |

**Volume discounts:** open an account directly with the carrier and negotiate
rates based on monthly shipping volume. Rates can drop 30-60% from published
retail rates with consistent volume (50+ shipments/month).

### When to Use Express

- Sending product samples to yourself or customers
- Urgent restocks of small quantities (under 100 kg)
- High-value, lightweight products (jewelry, electronics accessories)
- Markets with unreliable freight infrastructure (some African, South American
  destinations)
- Customer-direct shipping for high-value DTC orders
- Sending FBA shipment documents that must arrive before cargo

### When NOT to Use Express

- Anything over 200 kg (air freight is cheaper)
- Low-value, heavy products (cost per unit makes it uneconomical)
- Non-urgent shipments (sea freight saves 80-90% on shipping cost)
- Large product launches (express cannot scale for 5,000+ unit shipments)

---

## 5. FBA Partnered Carrier Program

Amazon offers discounted shipping rates through its Partnered Carrier program
for inbound FBA shipments.

### How It Works

1. Create shipping plan in Seller Central
2. Select "Amazon Partnered Carrier" option
3. Amazon provides discounted UPS (US) or other carrier labels
4. Ship using the provided labels; tracking is automatic

### FBA Partnered Carrier Rates (US)

Amazon's partnered carrier rates are typically 30-50% below standard UPS/FedEx
retail rates for domestic US shipments.

**Small parcel delivery (SPD):**
- For shipments that fit in individual boxes (max 50 lbs per box)
- Cost: typically $0.30-$0.80 per lb depending on zone
- Best for: small restocks, lightweight products

**Less than truckload (LTL):**
- For pallet shipments (6+ boxes or heavy shipments)
- Cost: typically 50-70% below standard LTL rates
- Best for: large FBA replenishments, heavy products

### Limitations

- Only for domestic shipping to FBA warehouses (not international inbound)
- Must use Amazon's shipping plan workflow
- Carrier selection is limited (usually UPS for SPD in US)
- Cannot combine with your own negotiated carrier rates
- Voided shipments may incur fees

### Best Practice: International to FBA

For international inbound to FBA, the typical flow is:

```
Factory --> International freight (sea/air) --> US port/airport
  --> Customs clearance --> Delivery to your 3PL or prep center
  --> FBA prep (labeling, inspection) --> Ship to FBA via Partnered Carrier
```

Do not ship directly from China to FBA unless your freight forwarder offers
a "direct-to-FBA" service that includes:
- FBA-compliant labeling at origin
- Customs clearance
- Delivery appointment scheduling with Amazon FC
- Handling of split shipments to multiple FCs

---

## 6. Door-to-Door vs Port-to-Port

### Port-to-Port

Freight forwarder handles only the international transit segment.

```
You arrange: Factory pickup --> Port of origin
Forwarder:   Port of origin --> Port of destination
You arrange: Port of destination --> Customs --> Warehouse
```

**Pros:**
- Lower freight cost (you only pay for the ocean/air leg)
- More control over each segment
- Can use specialized local agents at each end

**Cons:**
- You manage multiple parties (trucking, forwarder, customs broker, delivery)
- More coordination overhead
- Higher risk of handoff delays between parties
- You bear responsibility for delays at every transition

### Door-to-Door (DDP or DDU)

Freight forwarder or logistics company handles the entire chain.

```
Forwarder handles everything:
Factory pickup --> Origin port --> International transit -->
Destination port --> Customs clearance --> Delivery to warehouse
```

**Pros:**
- Single point of contact and accountability
- Simpler logistics management
- All-inclusive pricing (easier to budget)
- Forwarder handles customs paperwork

**Cons:**
- Higher total cost (forwarder marks up each segment)
- Less control and visibility into each leg
- Forwarder may use subcontracted parties you would not have chosen
- Difficult to compare pricing (bundled vs. itemized)

### Recommendation

| Seller Profile | Recommended Approach |
|---------------|---------------------|
| New seller, first few shipments | Door-to-door DDP (simplicity over cost) |
| Growing seller, 5-20 shipments/year | Door-to-door with itemized billing |
| Experienced seller, 20+ shipments/year | Port-to-port with own customs broker |
| Multi-origin seller (multiple factories) | Hybrid: door-to-port + own destination agent |

---

## 7. Consolidated Shipping Services

Consolidated shipping services (also called "China warehouse forwarding" or
"freight consolidation") combine cargo from multiple sellers into shared
containers.

### How It Works

1. Ship products from your factory to the consolidator's China warehouse
2. Consolidator receives, inspects, labels, and palletizes
3. Consolidator combines your cargo with other sellers' cargo into FCL
4. Container ships to destination; cargo is deconsolidated and delivered

### Popular Consolidation Services

| Service Type | Example Providers | Cost Savings | Transit Time Impact |
|-------------|-------------------|-------------|-------------------|
| **Amazon FBA forwarding** | Yiwu/Shenzhen-based forwarders | 30-50% vs direct air | +5-10 days vs direct |
| **Sea freight consolidation** | FreightOS, Flexport, regional forwarders | 20-40% vs LCL | Similar to LCL |
| **Express consolidation** | Yanwen, 4PX, CNE Express | 40-60% vs DHL/FedEx | +2-5 days vs express |

### Advantages

- Significant cost savings for small shipments (1-5 CBM)
- Many offer FBA labeling, inspection, and prep at origin
- Simplified logistics (one provider handles most of the chain)
- Good for sellers with multiple suppliers shipping to one market

### Disadvantages

- Longer transit times due to consolidation waiting periods
- Less control over timing (your cargo waits for the container to fill)
- Co-loading risk (your cargo is with other shippers' goods)
- Quality of service varies dramatically between providers
- Limited recourse if cargo is damaged or lost during consolidation

### Selection Criteria for Consolidators

- Verify warehouse address and visit if possible (or get referrals)
- Request photos of your cargo at their warehouse before shipping
- Confirm insurance coverage during consolidation and transit
- Check their container shipping frequency to your destination (weekly = good,
  monthly = too slow)
- Test with a small shipment before committing large volume

---

## 8. Route-Specific Recommendations

### China to US

| Shipment Size | Recommended Method | Estimated Cost | Transit Time |
|--------------|-------------------|---------------|-------------|
| < 50 kg | Express courier (DHL/FedEx) | $8-$20/kg | 5-8 days |
| 50-300 kg | Air freight | $4-$8/kg | 7-12 days |
| 300 kg - 5 CBM | Sea LCL or consolidated | $50-$80/CBM | 30-45 days |
| 5-30 CBM | Sea FCL (20ft) | $1,500-$4,000 flat | 18-30 days |
| 30+ CBM | Sea FCL (40ft or multiple) | $2,500-$6,000 flat | 18-30 days |

**US-specific notes:**
- West Coast ports (LA/Long Beach) are cheaper but congestion-prone
- East Coast routing (via Panama Canal) adds 7-10 days but avoids West Coast
  congestion
- US customs bond required for commercial imports over $2,500
- Section 301 tariffs add 7.5-25% duty on many Chinese goods
- Consider routing through bonded warehouses for duty deferral

### China to EU

| Shipment Size | Recommended Method | Estimated Cost | Transit Time |
|--------------|-------------------|---------------|-------------|
| < 50 kg | Express courier | $8-$20/kg | 5-8 days |
| 50-300 kg | Air freight | $4-$8/kg | 7-10 days |
| 300 kg - 5 CBM | Rail freight | $2-$4/kg | 14-20 days |
| 5-30 CBM | Sea FCL or Rail (20ft) | $2,000-$5,000 | 14-35 days |
| 30+ CBM | Sea FCL (40ft) | $2,500-$7,000 | 28-38 days |

**EU-specific notes:**
- Rail is a strong mid-cost option unavailable for other destinations
- Port of entry matters: Rotterdam, Hamburg, and Piraeus have different costs
- IOSS (Import One-Stop Shop) for parcels under EUR 150 simplifies VAT
- EU customs can be stricter on CE marking and REACH compliance
- Consider entering via one EU country and distributing to others (free movement)

### China to Southeast Asia

| Shipment Size | Recommended Method | Estimated Cost | Transit Time |
|--------------|-------------------|---------------|-------------|
| < 20 kg | Express courier (SF Express, J&T) | $5-$12/kg | 3-6 days |
| 20-200 kg | Air freight | $3-$5/kg | 3-5 days |
| 200 kg - 5 CBM | Sea LCL | $30-$50/CBM | 10-18 days |
| 5+ CBM | Sea FCL | $400-$1,500 | 5-12 days |

**SEA-specific notes:**
- Short sea routes make ocean freight relatively fast (5-12 days)
- Customs clearance varies wildly by country (Singapore = fast, Indonesia = slow)
- Consider platform-provided logistics (Shopee Logistics, Lazada Logistics)
- Cash-on-delivery (COD) is dominant; factor in rejection rates (15-30%)
- Cross-border e-commerce zones in some countries offer simplified clearance

---

## 9. Insurance Options

### Types of Cargo Insurance

| Insurance Type | Coverage | Typical Cost | When to Use |
|---------------|---------|-------------|-------------|
| **All-Risk** | Covers physical loss or damage from any external cause | 0.3-0.5% of cargo value | High-value shipments, fragile goods |
| **Named Perils** | Covers only specifically listed perils (fire, sinking, etc.) | 0.15-0.3% of cargo value | Standard shipments, cost-sensitive |
| **Carrier Liability** | Carrier's default coverage (very limited: ~$500/package sea) | Free (included) | Never rely on this alone for valuable cargo |
| **General Average** | Covers your share if ship's cargo is jettisoned to save vessel | Included in All-Risk | Relevant for sea freight only |

### When to Insure

**Always insure when:**
- Cargo value exceeds $10,000
- Product is fragile, perishable, or easily damaged
- Shipping during peak season (higher congestion = higher risk)
- Using a new or unproven carrier/forwarder
- Shipping to high-risk destinations (ports with theft issues)

**Consider self-insuring when:**
- Cargo value is under $5,000 and you can absorb the loss
- You ship 20+ containers per year (statistical risk is spread across shipments)
- Products are durable and commodity-grade (easy to replace)

### Filing a Claim

1. **Document damage immediately** at point of discovery (photos, written notes)
2. **Note damage on delivery receipt** before signing for cargo
3. **Notify insurer within 3 days** of discovering damage
4. **Preserve damaged goods** for inspection (do not dispose)
5. **Gather documents**: bill of lading, commercial invoice, packing list,
   survey report, photos
6. **File claim within policy timeframe** (usually 60-180 days)

---

## 10. Peak Season Shipping

Peak season for cross-border e-commerce runs from August through January,
with the highest pressure in October-November (pre-holiday inventory
positioning).

### Peak Season Timeline

| Month | What Happens | What You Should Do |
|-------|-------------|-------------------|
| **July** | Rates begin rising; carrier space tightening | Book all Q4 shipments; finalize production |
| **August** | Peak booking window; rates up 20-40% | Ship first batch of holiday inventory |
| **September** | Space premium; delays begin | All holiday inventory should be in transit |
| **October** | Peak rates; congestion at ports | Emergency air freight for shortfalls only |
| **November** | Amazon FBA inbound cutoff dates approaching | Final FBA receiving deadline (check Seller Central) |
| **December** | Post-Black Friday lull then Christmas push | Minimal shipping; plan January restock |
| **January** | Rates drop but CNY factory closures begin | Place post-CNY orders; pre-ship before factories close |

### Peak Season Survival Checklist

- [ ] Book ocean freight 6-8 weeks before ship date (vs. 2-3 weeks in normal season)
- [ ] Budget 20-50% higher shipping rates than off-peak
- [ ] Confirm FBA receiving cutoff dates (Amazon publishes these annually)
- [ ] Ship to FBA in smaller, more frequent batches (reduces risk of FC rejection)
- [ ] Have a backup forwarder or carrier if primary cannot provide space
- [ ] Pad delivery timelines by 7-14 days for potential port congestion
- [ ] Pre-position inventory at 3PL or prep center near FBA facilities
- [ ] Confirm all customs paperwork is perfect (delays are longer during peak)
- [ ] Buy cargo insurance (higher volume = higher absolute risk)
- [ ] Monitor carrier surcharges weekly (GRI, PSS, EBS announcements)

### Chinese New Year (CNY) Planning

CNY typically falls in late January or early February. Factories close for
15-30 days. Shipping volume spikes in the 2-3 weeks before CNY as sellers
rush to ship.

**CNY timeline:**
- **6-8 weeks before CNY**: place final production orders
- **4-6 weeks before CNY**: all goods should leave factory
- **2-4 weeks before CNY**: last chance for express/air shipments
- **CNY week + 1 week after**: virtually no production or shipping
- **2-3 weeks after CNY**: factories resume, but slowly (workers return gradually)
- **4-6 weeks after CNY**: production normalizes

**Rule of thumb:** whatever inventory you need for January-March, have it
produced and shipped by mid-December at the latest.

# Landed Cost Calculator Reference

Complete reference for calculating the true landed cost of cross-border e-commerce
products. Every cost component is itemized so that nothing is missed.

---

## Table of Contents

1. [The Complete Cost Formula](#the-complete-cost-formula)
2. [COGS Components](#cogs-components)
3. [Freight Costs](#freight-costs)
4. [Customs and Duties](#customs-and-duties)
5. [Platform Fees](#platform-fees)
6. [Advertising Cost Allocation](#advertising-cost-allocation)
7. [Returns Reserve](#returns-reserve)
8. [Payment Processing Fees](#payment-processing-fees)
9. [VAT/GST Impact on Pricing](#vatgst-impact-on-pricing)
10. [Worked Examples](#worked-examples)

---

## The Complete Cost Formula

```
Landed Cost per Unit =
    COGS per Unit
  + Freight per Unit
  + Insurance per Unit
  + Customs Duty per Unit
  + Customs Brokerage per Unit
  + Platform Referral Fee per Unit
  + Fulfillment Fee per Unit
  + Storage Fee Allocation per Unit
  + Advertising Allocation per Unit
  + Returns Reserve per Unit
  + Payment Processing Fee per Unit
  + VAT/GST (if seller-absorbed) per Unit
```

```
Minimum Viable Selling Price = Landed Cost per Unit / (1 - Target Net Margin%)
```

```
Net Profit per Unit = Selling Price - Landed Cost per Unit
Net Margin % = Net Profit per Unit / Selling Price x 100
```

All fee components that are percentages of selling price (referral fee, payment
processing, advertising allocation) create a circular dependency. Solve with:

```
Selling Price = Fixed Costs per Unit / (1 - Sum of All Percentage-Based Fees - Target Margin%)
```

Where:
- Fixed Costs per Unit = COGS + Freight + Insurance + Duty + Brokerage + Fulfillment + Storage Allocation
- Sum of All Percentage-Based Fees = Referral% + Payment% + TACOS% + Returns Reserve%

---

## COGS Components

### Factory / Purchase Price
- Confirm pricing basis: FOB (Free On Board) or EXW (Ex Works)
- FOB includes domestic transport to port; EXW does not
- Always confirm currency and whether price includes or excludes Chinese VAT (for
  China-sourced goods, export pricing typically excludes the 13% VAT via tax rebate)
- Get quotes at multiple MOQ tiers; unit cost can drop 10-30% at higher quantities

### Packaging
| Component | Typical Cost Range (USD) | Notes |
|-----------|------------------------:|-------|
| Poly bag | $0.02 - $0.10 | Required for most FBA items |
| Color box / retail packaging | $0.15 - $1.50 | Varies by size and print quality |
| Inner box / protective packaging | $0.05 - $0.30 | Foam inserts, bubble wrap |
| Outer carton (allocated per unit) | $0.03 - $0.15 | Master carton cost divided by units per carton |
| FNSKU / barcode labels | $0.01 - $0.05 | Per unit |
| Suffocation warning sticker | $0.01 - $0.03 | Required for poly-bagged items |
| Custom insert / thank you card | $0.03 - $0.15 | Optional; check platform rules on review solicitation |

### Labeling and Compliance
- CE marking (EU): testing $500-3,000 per product; allocated across expected sales volume
- FCC marking (US electronics): testing $1,000-5,000 per product
- FDA registration (health/beauty): $200-2,000 setup; allocate across units
- UPC/EAN barcode: $250 for 10 barcodes (GS1 US); one-time cost allocated across lifetime

### Quality Inspection
- Pre-shipment inspection: $250-400 per inspection (third party)
- Allocate per unit: inspection cost / units in shipment
- Typical allocation: $0.01-0.10 per unit depending on order size

---

## Freight Costs

### Cost by Shipping Method

| Method | Cost Range | Transit Time | Best For |
|--------|-----------|-------------|----------|
| **Sea Freight (FCL)** | $2-6 per kg; $1,500-4,500 per 20ft container | 25-45 days | Large, heavy shipments; bulk inventory |
| **Sea Freight (LCL)** | $5-10 per CBM (min 1 CBM) | 30-50 days | Smaller shipments not filling a container |
| **Air Freight (standard)** | $4-8 per kg | 7-15 days | Mid-weight, time-sensitive restocks |
| **Air Express (DHL/FedEx/UPS)** | $6-15 per kg | 3-7 days | Urgent restocks, lightweight items, samples |
| **Rail (China-Europe)** | $3-6 per kg | 18-25 days | EU-bound goods; balance of cost and speed |
| **Sea-Air Combo** | $4-7 per kg | 15-25 days | Moderate urgency, moderate cost |

### Per-Unit Freight Calculation
```
Freight per Unit = Total Freight Cost / Total Units in Shipment
```

For volumetric-weight-based shipping:
```
Volumetric Weight (kg) = Length(cm) x Width(cm) x Height(cm) / 5000 (air) or 6000 (sea)
Chargeable Weight = MAX(Actual Weight, Volumetric Weight)
```

### Additional Freight Costs
| Item | Typical Cost | Notes |
|------|------------:|-------|
| Pickup/drayage (origin) | $50-200 | Factory to port/warehouse |
| Port handling (origin) | $50-150 | Per container or per shipment |
| Cargo insurance | 0.3-0.5% of declared value | Recommended for all shipments |
| Port handling (destination) | $100-300 | Per container or per shipment |
| Last-mile delivery to FBA/warehouse | $50-500 | Depends on distance and carrier |
| Amazon Partnered Carrier discount | 30-50% off standard | When available, use it |

---

## Customs and Duties

### How to Calculate Import Duty
```
Customs Value (CIF) = FOB Price + Freight Cost + Insurance Cost
Import Duty = Customs Value x Duty Rate%
```

### Finding the Correct Duty Rate
1. Identify the HS (Harmonized System) code for the product (6-digit international,
   8-10 digit country-specific)
2. Look up the duty rate for the destination country using that HS code
3. Resources:
   - US: USITC HTS database (hts.usitc.gov)
   - EU: TARIC database (ec.europa.eu/taxation_customs/dds2/taric)
   - Southeast Asia: ASEAN Tariff Finder

### Common Duty Rate Ranges by Category (US)

| Category | Typical US Duty Rate | Notes |
|----------|--------------------:|-------|
| Electronics / accessories | 0-5% | Many items duty-free under ITA |
| Textiles / apparel | 10-32% | Varies widely by material and construction |
| Footwear | 8-48% | Highest rates in the tariff schedule |
| Furniture / home goods | 0-10% | Material-dependent |
| Toys | 0-6.5% | Most are duty-free or low rate |
| Kitchenware (plastic) | 3-5% | |
| Kitchenware (metal) | 0-8% | Stainless steel often 0-3% |
| Beauty / personal care | 0-5% | FDA compliance cost often exceeds duty |
| Pet products | 0-8% | Depends on material |

### Section 301 Tariffs (US-China)
- Additional 7.5-25% on top of standard duty for many China-origin goods
- List-specific; check USTR Section 301 lists for your HS code
- Significantly impacts cost calculations for China-sourced products
- Some exclusions exist; verify current status

### De Minimis Thresholds
| Country | Threshold | Effect |
|---------|----------:|--------|
| United States | $800 | No duty or tax below this value per shipment |
| European Union | EUR 150 | No duty below; VAT still applies from EUR 0 |
| United Kingdom | GBP 135 | No duty below; VAT still applies from GBP 0 |
| Canada | CAD 20 (duty), CAD 40 (tax) | Very low thresholds |
| Australia | AUD 1,000 | No duty below; GST applies from AUD 0 |
| Singapore | SGD 400 | No duty/GST below this value |
| Japan | JPY 10,000 | No duty/tax below |

Note: De minimis applies to individual shipments and is not useful for bulk FBA
shipments. It is relevant for direct-to-consumer orders fulfilled from origin country.

### Customs Brokerage
- US: $50-150 per entry (formal entry above $2,500 value)
- EU: EUR 50-200 per declaration
- Allocate per unit: brokerage cost / units in shipment

---

## Platform Fees

### Fee Structure Overview
Platform fees are the largest variable cost for most sellers. They typically include:
1. **Referral/commission fee:** Percentage of selling price (varies by category)
2. **Fulfillment fee:** Per-unit fee for pick, pack, and ship (if using platform fulfillment)
3. **Storage fee:** Monthly fee per cubic foot/meter of inventory stored
4. **Long-term/aged inventory surcharge:** Additional fee for slow-moving inventory

### Per-Unit Fee Calculation
```
Referral Fee = Selling Price x Referral Rate%
Fulfillment Fee = Fixed amount per unit (based on size/weight tier)
Storage Fee per Unit = (Monthly Rate per CBF x Unit Volume in CBF) / Inventory Turnover Rate
```

For storage allocation, estimate monthly inventory turnover:
```
Storage Cost per Unit = Monthly Storage Rate x Unit CBF x Average Days in Warehouse / 30
```

See `references/platform-fees.md` for complete fee schedules per platform.

---

## Advertising Cost Allocation

### TACOS (Total Advertising Cost of Sales)
```
TACOS = Total Ad Spend / Total Revenue (ad-driven + organic)
Per-Unit Ad Cost = Selling Price x TACOS%
```

### TACOS Benchmarks by Stage
| Product Stage | Target TACOS | Notes |
|--------------|-------------:|-------|
| Launch (weeks 1-4) | 20-30% | Heavy spend to generate reviews and ranking |
| Growth (months 2-4) | 12-20% | Scaling campaigns, optimizing keywords |
| Mature (month 5+) | 8-12% | Maintenance; organic sales should dominate |
| Decline / clearance | 5-8% | Reduce spend; let organic carry |

### ACOS vs TACOS
- ACOS (Advertising Cost of Sales) = Ad Spend / Ad-Attributed Revenue
- TACOS includes organic revenue in the denominator, so it is always lower than ACOS
- Use TACOS for pricing decisions because it reflects true per-unit ad cost
- Target ACOS for individual campaigns can be higher than TACOS if organic sales are strong

### Per-Unit Calculation Example
```
Selling Price:        $29.99
Target TACOS:         12%
Per-Unit Ad Cost:     $29.99 x 0.12 = $3.60
```

---

## Returns Reserve

### Category-Specific Return Rates
| Category | Average Return Rate | Reserve Recommendation |
|----------|-------------------:|----------------------:|
| Electronics | 5-10% | 8% |
| Home & Kitchen | 3-6% | 5% |
| Beauty | 2-4% | 4% |
| Apparel | 15-30% | 25% |
| Shoes | 20-35% | 30% |
| Toys | 3-7% | 6% |
| Pet Supplies | 2-5% | 4% |
| Sports & Outdoors | 5-10% | 8% |
| Baby Products | 3-8% | 7% |
| Office Products | 2-5% | 4% |

### Per-Unit Return Cost Calculation
```
Return Cost per Unit =
    Return Rate%
  x (Selling Price
     + Return Shipping Cost (if seller-paid)
     + Restocking/Processing Fee
     + Unsalvageable Rate x COGS)
```

For FBA returns:
- Amazon charges a return processing fee equal to the original fulfillment fee (most categories)
- Customer-damaged returns: often cannot be resold as new
- Typical unsalvageable rate: 20-40% of returned units

### Reserve Formula
```
Returns Reserve per Unit = Expected Return Cost / Units Sold
```

Simplified:
```
Returns Reserve per Unit = Return Rate% x (COGS + Fulfillment Fee) x 1.3
```

The 1.3 multiplier accounts for return shipping and unsalvageable losses.

---

## Payment Processing Fees

### By Platform
| Platform | Payment Processing Fee | Currency Conversion | Notes |
|----------|----------------------:|--------------------:|-------|
| Amazon | 0% (included in referral) | 1.5% (if different currency) | Currency conversion via ACCS |
| Shopee | 2% transaction fee | 1-3% | Varies by market |
| TikTok Shop | Included in commission | 1-2% | Varies by market |
| Lazada | 2% payment fee | 1-2% | Varies by market |
| Shopify (self-hosted) | 2.4-2.9% + $0.30 | Varies by provider | Plus gateway fees |
| PayPal | 3.49% + $0.49 (international) | 3-4% | Expensive; avoid if possible |

### Third-Party Payment Services
- Payoneer: 1-2% currency conversion; $0-3 withdrawal fee
- Pingpong: 1% currency conversion
- WorldFirst: 0.3-1% currency conversion
- LianLian: 0.7-1% currency conversion

Choosing a competitive payment service for currency conversion can save 1-2% on every
sale compared to platform-native conversion.

---

## VAT/GST Impact on Pricing

### VAT-Inclusive vs VAT-Exclusive Pricing
- **US:** No federal sales tax collected by marketplace; marketplace facilitator laws
  handle state sales tax. Sellers generally do not need to build sales tax into price.
- **EU:** Prices displayed to consumers are VAT-inclusive. The selling price includes
  VAT, which reduces the net revenue the seller receives.
- **UK:** Same as EU; 20% VAT included in displayed price.
- **Australia:** 10% GST included in displayed price.
- **Singapore:** 9% GST included in displayed price (as of 2024).

### EU VAT Calculation for Pricing
```
Net Revenue = VAT-Inclusive Selling Price / (1 + VAT Rate)
```

Example (Germany, 19% VAT):
```
Displayed Price: EUR 29.99
Net Revenue:     EUR 29.99 / 1.19 = EUR 25.20
VAT Collected:   EUR 4.79
```

The seller receives EUR 25.20, not EUR 29.99. All cost calculations must use net
revenue, not the displayed price.

### VAT Rates by Major EU Markets
| Country | Standard VAT Rate |
|---------|------------------:|
| Germany | 19% |
| France | 20% |
| Italy | 22% |
| Spain | 21% |
| Netherlands | 21% |
| Poland | 23% |
| Sweden | 25% |

### Import VAT
- When goods are imported into the EU, import VAT is charged on (Customs Value + Duty)
- This import VAT is recoverable if the seller is VAT-registered in the import country
- If not recoverable, it becomes an additional cost in the landed cost calculation

---

## Worked Examples

### Example 1: Small Electronics Item, China to Amazon US via FBA

**Product:** Bluetooth earbuds, China factory to Amazon US FBA warehouse

| Cost Component | Calculation | Amount (USD) |
|---------------|-------------|-------------:|
| **Factory price (FOB)** | Quoted price per unit | $4.50 |
| **Packaging** | Color box + poly bag + insert | $0.35 |
| **Quality inspection** | $300 / 3,000 units | $0.10 |
| **COGS Total** | | **$4.95** |
| **Sea freight** | $2,400 (LCL) / 3,000 units | $0.80 |
| **Insurance** | 0.4% x ($4.50 x 3,000) | $0.02 |
| **Last-mile to FBA** | $350 / 3,000 units | $0.12 |
| **Freight Total** | | **$0.94** |
| **US Customs duty** | HS 8518.30 (earphones) 0% | $0.00 |
| **Section 301 tariff** | 7.5% x ($4.50 + $0.80 + $0.02) | $0.40 |
| **Customs brokerage** | $125 / 3,000 units | $0.04 |
| **Duty Total** | | **$0.44** |
| **Fixed Costs per Unit** | COGS + Freight + Duty | **$6.33** |

Now calculate selling price. Assume:
- Amazon referral fee: 15% (electronics accessories)
- FBA fulfillment fee: $3.22 (small standard)
- Storage allocation: $0.15 (assumes 60-day turnover)
- TACOS target: 15% (growth stage)
- Returns reserve: 8%
- Payment processing: 0% (Amazon handles)

```
Fixed cost per unit:  $6.33 + $3.22 (fulfillment) + $0.15 (storage) = $9.70
Variable fee total:   15% (referral) + 15% (TACOS) + 8% (returns) = 38%
Target net margin:    15%

Minimum Selling Price = $9.70 / (1 - 0.38 - 0.15)
                      = $9.70 / 0.47
                      = $20.64
```

Round to $21.99 for market positioning.

**Margin verification at $21.99:**

| Line Item | Amount |
|-----------|-------:|
| Selling Price | $21.99 |
| minus Referral Fee (15%) | -$3.30 |
| minus FBA Fulfillment | -$3.22 |
| minus Storage | -$0.15 |
| minus COGS | -$4.95 |
| minus Freight | -$0.94 |
| minus Duty | -$0.44 |
| minus Ad Cost (15% TACOS) | -$3.30 |
| minus Returns Reserve (8%) | -$1.76 |
| **Net Profit** | **$3.93** |
| **Net Margin** | **17.9%** |

The product is viable at $21.99 with a 17.9% net margin.

---

### Example 2: Apparel Item, China to Shopee Singapore

**Product:** Women's casual dress, China factory to Shopee Singapore

| Cost Component | Calculation | Amount (USD) |
|---------------|-------------|-------------:|
| **Factory price (FOB)** | Quoted price per unit | $3.80 |
| **Packaging** | Poly bag + size label + hang tag | $0.15 |
| **Quality inspection** | $300 / 2,000 units | $0.15 |
| **COGS Total** | | **$4.10** |
| **Air freight** | $5.50/kg x 0.25 kg | $1.38 |
| **Insurance** | 0.3% of declared value | $0.01 |
| **Freight Total** | | **$1.39** |
| **Singapore import duty** | Most apparel: 0% (Singapore is free port) | $0.00 |
| **GST on import** | 9% x ($3.80 + $1.39) applies if above threshold | $0.00 |
| **Duty Total** | (Below SGD 400 de minimis per shipment not applicable for bulk) | **$0.47** |
| **Fixed Costs per Unit** | | **$5.96** |

Shopee Singapore fee assumptions:
- Commission rate: 2.16% (Shopee Mall)
- Transaction fee: 2.0%
- Shopee shipping subsidy: -$0.50 (estimated platform shipping support)
- TACOS target: 12%
- Returns reserve: 20% (apparel)
- Payment/currency conversion: 2%

Selling price in SGD, converted at 1 USD = 1.35 SGD.

```
Fixed cost per unit:  $5.96 (USD)
Variable fee total:   2.16% + 2% + 12% + 20% + 2% = 38.16%
Target net margin:    15%

Minimum Selling Price = $5.96 / (1 - 0.3816 - 0.15)
                      = $5.96 / 0.4684
                      = $12.72 USD
                      = SGD 17.17
```

Round to SGD 18.90 for market positioning.

**Margin verification at SGD 18.90 ($14.00 USD):**

| Line Item | Amount (USD) |
|-----------|-------------:|
| Selling Price | $14.00 |
| minus Commission (2.16%) | -$0.30 |
| minus Transaction Fee (2%) | -$0.28 |
| minus COGS | -$4.10 |
| minus Freight | -$1.39 |
| minus Duty/GST | -$0.47 |
| minus Ad Cost (12% TACOS) | -$1.68 |
| minus Returns Reserve (20%) | -$2.80 |
| minus Payment/FX (2%) | -$0.28 |
| plus Shipping Subsidy | +$0.50 |
| **Net Profit** | **$3.20** |
| **Net Margin** | **22.9%** |

Viable, but the 20% returns reserve for apparel is critical. If actual returns exceed
20%, margin erodes quickly.

---

### Example 3: Home Goods, China to Amazon Germany (with VAT)

**Product:** Stainless steel kitchen organizer, China factory to Amazon DE FBA

| Cost Component | Calculation | Amount (EUR) |
|---------------|-------------|-------------:|
| **Factory price (FOB)** | $6.00 USD = EUR 5.50 (at 1.09) | EUR 5.50 |
| **Packaging** | Color box + bubble wrap | EUR 0.55 |
| **Compliance (REACH/CE)** | EUR 1,500 / 5,000 units | EUR 0.30 |
| **COGS Total** | | **EUR 6.35** |
| **Sea freight** | EUR 3,200 / 5,000 units | EUR 0.64 |
| **Insurance** | 0.4% of declared value | EUR 0.02 |
| **Last-mile to FBA DE** | EUR 600 / 5,000 units | EUR 0.12 |
| **Freight Total** | | **EUR 0.78** |
| **EU customs duty** | HS 7323 (stainless steel kitchen) 3.5% x CIF | EUR 0.25 |
| **Import VAT** | 19% x (CIF + Duty) recoverable if VAT-registered | EUR 0.00* |
| **Customs brokerage** | EUR 150 / 5,000 units | EUR 0.03 |
| **Duty Total** | | **EUR 0.28** |
| **Fixed Costs per Unit** | | **EUR 7.41** |

*Import VAT is recoverable with German VAT registration; not a cost if registered.

Amazon DE fee assumptions:
- Referral fee: 15% (Home & Kitchen)
- FBA fulfillment fee: EUR 4.45 (standard size, 0.8 kg)
- Storage allocation: EUR 0.20 (assumes 45-day turnover)
- TACOS target: 12%
- Returns reserve: 5%
- VAT: 19% (price must be VAT-inclusive; net revenue is price/1.19)

For VAT-inclusive markets, the formula changes:
```
Net Revenue = Displayed Price / 1.19
Fixed Costs = EUR 7.41 + EUR 4.45 + EUR 0.20 = EUR 12.06
Variable Fees = 15% + 12% + 5% = 32% (applied to net revenue)
Target Margin = 15% (of net revenue)

Net Revenue needed = EUR 12.06 / (1 - 0.32 - 0.15) = EUR 12.06 / 0.53 = EUR 22.75
Displayed Price (VAT-inclusive) = EUR 22.75 x 1.19 = EUR 27.07
```

Round to EUR 27.99 for market positioning.

**Margin verification at EUR 27.99:**

| Line Item | Amount (EUR) |
|-----------|-------------:|
| Displayed Price (incl. VAT) | EUR 27.99 |
| VAT portion (19%) | -EUR 4.47 |
| Net Revenue | EUR 23.52 |
| minus Referral Fee (15% of net) | -EUR 3.53 |
| minus FBA Fulfillment | -EUR 4.45 |
| minus Storage | -EUR 0.20 |
| minus COGS | -EUR 6.35 |
| minus Freight | -EUR 0.78 |
| minus Duty | -EUR 0.28 |
| minus Ad Cost (12% TACOS of net) | -EUR 2.82 |
| minus Returns Reserve (5% of net) | -EUR 1.18 |
| **Net Profit** | **EUR 3.93** |
| **Net Margin (of net revenue)** | **16.7%** |

The product is viable at EUR 27.99 with a 16.7% net margin after all costs and VAT.

Key takeaway for EU pricing: always calculate from net revenue (ex-VAT), not displayed
price. The VAT portion belongs to the government, not the seller.

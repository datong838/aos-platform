# 30-Point Product Validation Scorecard

A rigorous, data-driven checklist for evaluating cross-border e-commerce
product opportunities. Every product MUST be scored against all 30 checkpoints
before a purchase order is placed.

**Scoring**: Each checkpoint is scored 0 (fail) or 1 (pass). No partial
credit. No subjective "feels like a 0.5."

**Threshold**: 21+ to proceed. See Go/No-Go decision matrix at the bottom.

## Table of Contents

- [How to Use This Scorecard](#how-to-use-this-scorecard)
- [Category 1: Demand Validation (5 points)](#category-1-demand-validation-5-points)
- [Category 2: Competition Analysis (5 points)](#category-2-competition-analysis-5-points)
- [Category 3: Margin Viability (5 points)](#category-3-margin-viability-5-points)
- [Category 4: Logistics Feasibility (5 points)](#category-4-logistics-feasibility-5-points)
- [Category 5: Differentiation Potential (5 points)](#category-5-differentiation-potential-5-points)
- [Category 6: Scalability (5 points)](#category-6-scalability-5-points)
- [Score Summary Template](#score-summary-template)
- [Go/No-Go Decision Matrix](#gono-go-decision-matrix)
- [Category Minimum Thresholds](#category-minimum-thresholds)

---

## How to Use This Scorecard

1. Complete market research first (`cbec-ops:market-research`). You need a
   defined target market and platform.
2. Gather data for ALL 30 checkpoints. Do not skip checkpoints. "I couldn't
   find data" scores as 0.
3. Use the specified data sources. Do not substitute gut feeling for data.
4. Score honestly. The scorecard protects your capital. Inflating scores only
   hurts you.
5. Document your evidence. For each checkpoint, note the specific data point
   and source used.
6. Data must be less than 30 days old. Stale data produces stale decisions.

---

## Category 1: Demand Validation (5 points)

Determines whether enough people want this product to sustain a business.

### 1.1 Search Volume

| Attribute | Detail |
|---|---|
| **What to check** | Monthly search volume for the primary keyword and top 3 related keywords on the target platform |
| **Score = 1** | Primary keyword has 3,000+ monthly searches on Amazon (or equivalent threshold on other platforms: Shopee 5,000+, Google 10,000+) |
| **Score = 0** | Primary keyword is below the threshold, or data is unavailable |
| **Data sources** | Helium 10 Magnet, Jungle Scout Keyword Scout, Merchant Words, Google Keyword Planner, Shopee Keyword Tool |
| **Red flags** | Search volume is inflated by a brand name (e.g., "Dyson fan" is not a product opportunity). Volume is concentrated in a single misspelling. Volume spiked recently but has no history (possible manipulation). |

### 1.2 BSR Analysis

| Attribute | Detail |
|---|---|
| **What to check** | Best Sellers Rank of the top 10 organic results for the primary keyword in the target subcategory |
| **Score = 1** | At least 3 of the top 10 have BSR under 15,000 in their main category (Amazon). For Shopee: at least 3 of top 10 have 100+ monthly sales. |
| **Score = 0** | Fewer than 3 products meet the threshold |
| **Data sources** | Jungle Scout Product Database, Helium 10 Xray, Keepa BSR charts, Shopee seller tools |
| **Red flags** | All top BSRs belong to a single brand. BSR is good but review count is under 10 (possible manipulation or very new listings). BSR has been declining steadily over 6 months. |

### 1.3 Trend Direction

| Attribute | Detail |
|---|---|
| **What to check** | 12-month search trend on Google Trends and platform-specific trend data. Is demand growing, stable, or declining? |
| **Score = 1** | Trend is stable (flat with <20% variation) or growing over the past 12 months |
| **Score = 0** | Trend is declining (>20% drop from 12-month peak to current) or shows a single spike with no sustained interest |
| **Data sources** | Google Trends (12-month and 5-year views), Keepa BSR history, Jungle Scout Trend data |
| **Red flags** | Sharp spike in the last 30 days (TikTok effect; likely too late to enter). Steady decline over 24 months (dying category). Flat at near-zero (no demand). |

### 1.4 Seasonal Stability

| Attribute | Detail |
|---|---|
| **What to check** | Monthly demand distribution across the year. How concentrated are sales in specific months? |
| **Score = 1** | No single quarter accounts for more than 40% of annual demand, OR the product has a predictable seasonal peak that the seller can plan inventory for |
| **Score = 0** | Demand is concentrated (>70% in one quarter) with dead periods, or seasonal pattern is unpredictable |
| **Data sources** | Google Trends (5-year view for seasonal pattern), Keepa BSR history (12-month overlay), category-level sales data |
| **Red flags** | Product is a holiday-only item (Halloween costumes, Christmas decorations) with near-zero off-season demand. Seasonal peak requires inventory to arrive 3+ months early (cash flow strain). |

### 1.5 Market Size

| Attribute | Detail |
|---|---|
| **What to check** | Estimated total monthly revenue for the top 20 sellers in the subcategory on the target platform |
| **Score = 1** | Top 20 sellers generate a combined $200,000+/month in the subcategory (Amazon US). Adjusted thresholds: Amazon EU $100K+, Shopee $50K+. |
| **Score = 0** | Combined monthly revenue is below threshold |
| **Data sources** | Jungle Scout Product Database (revenue estimates), Helium 10 Market Tracker, manual calculation (BSR-to-sales estimate x price x 20 sellers) |
| **Red flags** | Revenue is concentrated in 1-2 sellers (winner-take-all market). Revenue estimates vary wildly between tools (unreliable data). Average order value is declining month-over-month. |

---

## Category 2: Competition Analysis (5 points)

Determines whether you can realistically win market share.

### 2.1 Number of Competitors

| Attribute | Detail |
|---|---|
| **What to check** | Count of active sellers on page 1-3 of the primary keyword search results who have >50 reviews and >$5,000/month estimated revenue |
| **Score = 1** | Between 5 and 25 meaningful competitors. Fewer than 5 may indicate a dead market. More than 25 means oversaturation. |
| **Score = 0** | Fewer than 5 or more than 25 meaningful competitors |
| **Data sources** | Helium 10 Xray, Jungle Scout Chrome Extension, manual count from search results |
| **Red flags** | Dozens of identical listings with stock photos (race-to-bottom market). Many new listings in the last 90 days (gold rush saturation). Competitor count is growing 20%+ month-over-month. |

### 2.2 Review Moats

| Attribute | Detail |
|---|---|
| **What to check** | Average review count of page-1 organic sellers for the primary keyword |
| **Score = 1** | Average review count of top 10 organic sellers is under 1,000 reviews |
| **Score = 0** | Average review count exceeds 1,000 reviews |
| **Data sources** | Manual count from search results, Helium 10 Xray, Jungle Scout |
| **Red flags** | Top 3 sellers have 5,000+ reviews each (nearly impossible to outrank organically). Review velocity of top sellers is 100+/month (they are accelerating away). Wide review gap between #1 and #10 (winner-take-all dynamics). |

### 2.3 Brand Dominance

| Attribute | Detail |
|---|---|
| **What to check** | Whether recognized brands or Amazon's own brands dominate the first page of search results |
| **Score = 1** | No single brand holds more than 30% of page-1 organic positions, and no major national/global brand is present |
| **Score = 0** | One brand holds 30%+ of page 1, or a major brand (Nike, Apple, etc.) is competing in the subcategory |
| **Data sources** | Manual review of search results, Brand Analytics (if available), Helium 10 Market Tracker |
| **Red flags** | Amazon Basics or Amazon private label is in the category. A brand-name product is the #1 seller and the keyword is semi-branded. Category is trending toward brand consolidation. |

### 2.4 Listing Quality

| Attribute | Detail |
|---|---|
| **What to check** | Quality of competitor listings (images, A+ content, bullet points, video, backend keywords) for the top 10 results |
| **Score = 1** | At least 4 of the top 10 listings have poor quality (bad images, thin bullet points, no A+ content, no video). Opportunity to win with better listing quality. |
| **Score = 0** | Most top 10 listings are well-optimized with professional images, A+ content, and video |
| **Data sources** | Manual review of top 10 listings, Listing Quality Score tools |
| **Red flags** | All top listings have premium A+ content and brand stories (high bar to compete). Top sellers use video extensively (production cost to match). Listings are in multiple languages already (sophisticated sellers). |

### 2.5 Price Clustering

| Attribute | Detail |
|---|---|
| **What to check** | Price distribution of page-1 organic sellers. Is there price diversity or are all sellers clustered at the same price? |
| **Score = 1** | Price range of top 10 sellers spans at least 30% (e.g., $15 to $22), indicating room for price positioning |
| **Score = 0** | All top 10 sellers are within 15% of each other's price (tight cluster = price war) |
| **Data sources** | Manual price survey from search results, Keepa price history, Helium 10 Xray |
| **Red flags** | Prices have been declining month-over-month (active price war). Multiple sellers are priced at or near the FBA fee floor. Frequent coupon/deal usage suggests margin pressure across the category. |

---

## Category 3: Margin Viability (5 points)

Determines whether you can make money selling this product.

### 3.1 Target Retail Price

| Attribute | Detail |
|---|---|
| **What to check** | The price you can realistically sell at, based on competitor pricing, perceived value, and your differentiation |
| **Score = 1** | Target retail price is between $18 and $55 (sweet spot for impulse buying with workable margins for cross-border sellers) |
| **Score = 0** | Target price is below $18 (margin squeeze) or above $55 (low volume, high return risk) |
| **Data sources** | Competitor pricing from search results, Keepa price history, `cbec-ops:pricing-strategy` preliminary model |
| **Red flags** | You can only compete at a price below the current lowest seller. The "right" price is above what any current seller charges (demand unproven at that price). Price must include a coupon/deal to be competitive (hidden margin reduction). |

### 3.2 COGS Estimate

| Attribute | Detail |
|---|---|
| **What to check** | Estimated cost of goods from supplier quotes or 1688.com reference pricing, including any customization or branding costs |
| **Score = 1** | COGS is 25% or less of the target retail price (4x markup from factory to consumer) |
| **Score = 0** | COGS exceeds 25% of target retail price |
| **Data sources** | 1688.com price ranges (sort by "most orders"), Alibaba RFQ responses, direct supplier quotes, `cbec-ops:supplier-sourcing` preliminary estimates |
| **Red flags** | Only one supplier offers the target COGS (single-source risk). COGS requires MOQ of 5,000+ units to achieve (capital risk). Raw material prices for this product are volatile (margin unpredictability). |

### 3.3 Platform Fees

| Attribute | Detail |
|---|---|
| **What to check** | Total platform fees including referral fee, FBA/fulfillment fee, storage fee, and any category-specific fees |
| **Score = 1** | Total platform fees are 35% or less of the target retail price |
| **Score = 0** | Total platform fees exceed 35% of target retail price |
| **Data sources** | Amazon Revenue Calculator, Shopee Fee Calculator, platform fee schedules, `cbec-ops:pricing-strategy` fee model |
| **Red flags** | Product falls into a high-fee category (e.g., clothing on Amazon has higher referral fees). Product is oversized (FBA surcharges). Long-term storage fees are likely (slow-moving inventory risk). |

### 3.4 Shipping Cost

| Attribute | Detail |
|---|---|
| **What to check** | Total shipping cost from factory to customer, including international freight, customs/duties, last-mile delivery, and any prep/labeling fees |
| **Score = 1** | Total landed shipping cost (factory to FBA warehouse or customer door) is 15% or less of target retail price |
| **Score = 0** | Shipping cost exceeds 15% of target retail price |
| **Data sources** | Freight forwarder quotes, FBA inbound shipping estimates, 4PX/YunExpress rate cards, `cbec-ops:order-fulfillment` cost model |
| **Red flags** | Product is volumetric (large box, light weight = expensive air freight). Product requires special handling (cold chain, hazmat surcharge). Import duties are high for the product's HS code. |

### 3.5 Advertising Budget Room

| Attribute | Detail |
|---|---|
| **What to check** | After COGS, platform fees, and shipping, is there enough margin remaining to fund PPC advertising and still profit? |
| **Score = 1** | At least 15% of the target retail price remains available for advertising after deducting COGS, platform fees, and shipping, while still maintaining a minimum 15% net profit margin |
| **Score = 0** | Advertising budget room is less than 15% of retail price, or net margin after ads drops below 15% |
| **Data sources** | Margin model from checkpoints 3.1-3.4, Amazon Advertising benchmark CPCs for the category, `cbec-ops:pricing-strategy` full P&L model |
| **Red flags** | Category average CPC exceeds $2.00 (expensive to acquire customers). ACoS benchmarks in the category exceed 35%. Competitors are running heavy promotions (ad spend arms race). |

---

## Category 4: Logistics Feasibility (5 points)

Determines whether you can physically get this product to customers reliably.

### 4.1 Weight and Size

| Attribute | Detail |
|---|---|
| **What to check** | Product weight and dimensions (packaged, ready to ship). Determine FBA size tier or equivalent. |
| **Score = 1** | Product is standard-size (not oversized) and under 2 kg packaged weight. For non-FBA: packaged weight under 1 kg for air freight viability. |
| **Score = 0** | Product is oversized or exceeds weight thresholds |
| **Data sources** | Supplier product specs, Amazon FBA size tier calculator, competitor listing dimensions |
| **Red flags** | Product is close to a size-tier boundary (small changes in packaging could push it to a higher fee tier). Dimensional weight exceeds actual weight significantly. Product requires assembly that increases box size. |

### 4.2 Fragility

| Attribute | Detail |
|---|---|
| **What to check** | Risk of damage during international shipping and last-mile delivery. Consider the full journey: factory to port, ocean/air freight, customs handling, warehouse receiving, last-mile carrier. |
| **Score = 1** | Product is not fragile, or can be adequately protected with standard packaging at less than $1 additional packaging cost per unit |
| **Score = 0** | Product is inherently fragile (glass, ceramic, thin plastic) and requires special packaging that adds more than $1/unit or still has >5% expected damage rate |
| **Data sources** | Product material assessment, competitor review analysis for damage complaints, supplier packaging recommendations |
| **Red flags** | Competitor reviews mention "arrived broken" frequently. Product has thin or protruding parts. Product contains liquid that can leak. Previous seller attempts in the category show high damage rates. |

### 4.3 Customs Restrictions

| Attribute | Detail |
|---|---|
| **What to check** | Import restrictions, required certifications, HS code classification, and duty rates for the product in the target market |
| **Score = 1** | Product has no special import restrictions, does not require certifications the seller lacks, and duty rate is under 10% |
| **Score = 0** | Product faces import restrictions, requires certifications not yet obtained, or duty rate exceeds 10% |
| **Data sources** | Target country customs database, HS code lookup tools, customs broker consultation, `cbec-ops:platform-compliance` regulatory check |
| **Red flags** | Product contains wood (ISPM-15 requirements). Product is food-contact (FDA/EU food safety). Product contains batteries (IATA dangerous goods). Product is a children's item (CPSIA/EN71 testing). HS code is ambiguous (risk of reclassification at customs). |

### 4.4 Shelf Life

| Attribute | Detail |
|---|---|
| **What to check** | Does the product have a shelf life, expiration date, or degradation risk? Consider the full timeline: production to warehouse to customer use. |
| **Score = 1** | Product has no shelf life concerns, or shelf life exceeds 24 months and product can withstand warehouse temperature variations |
| **Score = 0** | Product has a shelf life under 24 months, or degrades under normal warehouse conditions (heat, humidity, cold) |
| **Data sources** | Supplier product specifications, material safety data sheets, competitor listing expiration warnings |
| **Red flags** | Product contains organic materials that can degrade. Product is temperature-sensitive (warehouses are not climate-controlled). Product uses adhesives or batteries that lose effectiveness over time. Customs delays could consume significant shelf life. |

### 4.5 Packaging Complexity

| Attribute | Detail |
|---|---|
| **What to check** | How complex is the packaging and prep required to make the product FBA-ready or shippable? Consider poly-bagging, labeling, bundling, and special handling. |
| **Score = 1** | Product requires standard packaging and prep only (poly bag + FNSKU label or equivalent). No special assembly, kitting, or handling required. |
| **Score = 0** | Product requires complex packaging, multi-component kitting, special inserts, or handling that adds more than $1.50/unit in prep costs |
| **Data sources** | Supplier packaging capabilities, FBA prep requirements, 3PL prep service pricing |
| **Red flags** | Product has multiple components that must be bundled (kitting errors). Product requires "frustration-free" packaging (Amazon requirement for some categories). Custom packaging is needed for brand differentiation but adds significant cost. Packaging materials themselves have import restrictions. |

---

## Category 5: Differentiation Potential (5 points)

Determines whether you can stand out from existing sellers.

### 5.1 Improvement Opportunity

| Attribute | Detail |
|---|---|
| **What to check** | Analyze top negative reviews (1-3 stars) of the top 5 competitors. Are there consistent complaints that you could solve? |
| **Score = 1** | A clear, recurring complaint appears in 20%+ of negative reviews across multiple competitors, AND the fix is technically feasible at less than $2 additional COGS |
| **Score = 0** | No clear common complaint, or the fix is too expensive or technically infeasible |
| **Data sources** | Amazon review analysis (filter by 1-3 stars), Helium 10 Review Insights, manual reading of 50+ negative reviews across top 5 competitors |
| **Red flags** | The complaint is about an inherent product limitation (e.g., "too small" for a product that must be compact). The fix requires a complete redesign. Multiple different complaints with no single dominant issue. |

### 5.2 Bundling Potential

| Attribute | Detail |
|---|---|
| **What to check** | Can complementary items be bundled to create a higher-value offer that competitors do not offer? |
| **Score = 1** | A natural complementary bundle exists that increases perceived value by 30%+ with less than $3 additional COGS, and no current top-10 seller offers this bundle |
| **Score = 0** | No natural bundle opportunity, or competitors already offer similar bundles |
| **Data sources** | "Frequently bought together" data on Amazon, competitor listing analysis, customer Q&A sections, common accessory searches |
| **Red flags** | Bundle components come from different suppliers (coordination complexity). Bundle makes the package oversized. Bundle includes consumable items (reorder logistics). Platform may classify the bundle differently (different fee structure). |

### 5.3 Design Differentiation

| Attribute | Detail |
|---|---|
| **What to check** | Can the product's appearance, color, material, or form factor be meaningfully differentiated from existing offerings? |
| **Score = 1** | A visual or material differentiation is feasible that costs less than $1.50 additional COGS and does not exist in the current top 20 listings |
| **Score = 0** | Product is a commodity where appearance does not influence purchase decision, or all obvious differentiations are already taken |
| **Data sources** | Visual analysis of top 20 listings, Pinterest/Instagram for design trends in the category, supplier customization capabilities |
| **Red flags** | Differentiation is purely cosmetic with no functional benefit (weak moat). Design change requires new tooling (high upfront cost). Design trend may be short-lived. |

### 5.4 Private Label Viability

| Attribute | Detail |
|---|---|
| **What to check** | Can you create a branded version of this product? Is the supplier willing to do custom branding (logo, packaging, inserts) at your MOQ? |
| **Score = 1** | Supplier offers private labeling at MOQ of 500 units or less, including custom packaging and logo placement, at less than $1 additional cost per unit |
| **Score = 0** | Private labeling requires MOQ >500 or adds more than $1/unit, or the product category does not benefit from branding |
| **Data sources** | Supplier communication (1688/Alibaba), competitor brand analysis (are branded products priced higher?), Amazon Brand Registry requirements |
| **Red flags** | Category is purely price-driven (branding adds no perceived value). Multiple sellers are already private labeling the same base product. Brand registration in the target market is complex or expensive. |

### 5.5 IP Clearance

| Attribute | Detail |
|---|---|
| **What to check** | Is the product free of patent, trademark, and design patent conflicts? Can you sell it without infringing on existing IP? |
| **Score = 1** | No active patents found for the product design or key features, no trademark conflicts with your proposed brand/listing, and no design patents covering the product's appearance |
| **Score = 0** | Active patents exist that could cover the product, trademark conflicts are possible, or the product closely resembles a design-patented item |
| **Data sources** | Google Patents, USPTO/EPO patent search, Amazon Brand Registry complaint history for the category, trademark databases (USPTO TESS, EUIPO) |
| **Red flags** | A competitor has a utility patent on a key feature. The product category has frequent IP complaints on Amazon. A design patent covers the general shape/appearance. The product mimics a recognizable branded design. |

---

## Category 6: Scalability (5 points)

Determines whether this product can grow into a sustainable business.

### 6.1 Supplier Availability

| Attribute | Detail |
|---|---|
| **What to check** | How many qualified suppliers can produce this product? Can you switch suppliers if your primary source fails? |
| **Score = 1** | At least 10 suppliers on 1688.com/Alibaba produce this product or a close equivalent, with at least 3 having "verified" or "Gold" status |
| **Score = 0** | Fewer than 10 suppliers available, or the product requires specialized manufacturing with limited sources |
| **Data sources** | 1688.com search results, Alibaba supplier directory, industry trade show exhibitor lists |
| **Red flags** | All suppliers are in the same city/region (geographic concentration risk). Product requires proprietary tooling held by one factory. Supplier reviews mention quality inconsistency. |

### 6.2 Reorder Consistency

| Attribute | Detail |
|---|---|
| **What to check** | Can you get consistent quality and pricing across multiple production runs? Are raw materials stable? |
| **Score = 1** | Product uses standard, widely available materials with stable pricing. Supplier has documented QC processes and can provide production samples matching the initial order. |
| **Score = 0** | Product uses volatile-price materials, requires hand-crafted elements with inconsistent output, or supplier cannot guarantee consistency |
| **Data sources** | Supplier quality certifications (ISO 9001), raw material commodity price charts, supplier communication about QC processes |
| **Red flags** | Product uses natural materials with inherent variation (wood grain, stone). Key components have volatile commodity pricing (copper, silicone). Supplier's production capacity is near maximum (quality drops under pressure). |

### 6.3 Seasonal Dependency

| Attribute | Detail |
|---|---|
| **What to check** | Is the product viable year-round, or is revenue concentrated in specific seasons? Assess whether off-season demand can sustain operations. |
| **Score = 1** | Product sells year-round with off-season months still generating at least 40% of peak-month revenue |
| **Score = 0** | Off-season months generate less than 40% of peak-month revenue, creating cash flow gaps |
| **Data sources** | Google Trends (5-year view), Keepa BSR 12-month chart, category seasonal data |
| **Red flags** | Product is a gift item (concentrated around holidays). Product is weather-dependent (outdoor/seasonal use). Off-season storage costs erode margins. Inventory planning requires accurate seasonal forecasting. |

### 6.4 Trend Durability

| Attribute | Detail |
|---|---|
| **What to check** | Is demand based on a lasting consumer need or a temporary trend? Will people still want this product in 2-3 years? |
| **Score = 1** | Product addresses a lasting functional need or belongs to a stable/growing consumer category with 3+ years of consistent demand data |
| **Score = 0** | Product is tied to a specific trend, meme, viral moment, or technology that is likely to be replaced within 2 years |
| **Data sources** | Google Trends (5-year view), industry reports on the category, technology roadmap analysis (for tech-adjacent products) |
| **Red flags** | Product is tied to a specific social media trend. Product depends on a technology that is being disrupted (e.g., phone cases for a specific model). Product is a "fad" category with historical boom-bust cycles. |

### 6.5 Multi-Platform Potential

| Attribute | Detail |
|---|---|
| **What to check** | Can this product be sold on multiple platforms (Amazon, Shopee, TikTok Shop, own website) or is it locked to one channel? |
| **Score = 1** | Product can be listed and sold on at least 2 additional platforms beyond the primary target, with no platform-specific restrictions |
| **Score = 0** | Product is restricted to a single platform due to category gating, compliance requirements, or platform-specific limitations |
| **Data sources** | Platform category policies, competitor presence across platforms, `cbec-ops:multi-platform-expansion` compatibility check |
| **Red flags** | Product requires platform-specific certifications that do not transfer. Product category is gated on most platforms. Product's target demographic is concentrated on one platform. |

---

## Score Summary Template

Use this template to record scores for each product candidate.

```
Product: _______________
Date Scored: ___________
Scored By: _____________
Target Market: _________
Target Platform: _______

Category 1 - Demand Validation:
  1.1 Search Volume:           [ ] 0  [ ] 1  Source: ___
  1.2 BSR Analysis:            [ ] 0  [ ] 1  Source: ___
  1.3 Trend Direction:         [ ] 0  [ ] 1  Source: ___
  1.4 Seasonal Stability:      [ ] 0  [ ] 1  Source: ___
  1.5 Market Size:             [ ] 0  [ ] 1  Source: ___
  Subtotal: ___/5

Category 2 - Competition Analysis:
  2.1 Number of Competitors:   [ ] 0  [ ] 1  Source: ___
  2.2 Review Moats:            [ ] 0  [ ] 1  Source: ___
  2.3 Brand Dominance:         [ ] 0  [ ] 1  Source: ___
  2.4 Listing Quality:         [ ] 0  [ ] 1  Source: ___
  2.5 Price Clustering:        [ ] 0  [ ] 1  Source: ___
  Subtotal: ___/5

Category 3 - Margin Viability:
  3.1 Target Retail Price:     [ ] 0  [ ] 1  Source: ___
  3.2 COGS Estimate:           [ ] 0  [ ] 1  Source: ___
  3.3 Platform Fees:           [ ] 0  [ ] 1  Source: ___
  3.4 Shipping Cost:           [ ] 0  [ ] 1  Source: ___
  3.5 Advertising Budget Room: [ ] 0  [ ] 1  Source: ___
  Subtotal: ___/5

Category 4 - Logistics Feasibility:
  4.1 Weight and Size:         [ ] 0  [ ] 1  Source: ___
  4.2 Fragility:               [ ] 0  [ ] 1  Source: ___
  4.3 Customs Restrictions:    [ ] 0  [ ] 1  Source: ___
  4.4 Shelf Life:              [ ] 0  [ ] 1  Source: ___
  4.5 Packaging Complexity:    [ ] 0  [ ] 1  Source: ___
  Subtotal: ___/5

Category 5 - Differentiation Potential:
  5.1 Improvement Opportunity: [ ] 0  [ ] 1  Source: ___
  5.2 Bundling Potential:      [ ] 0  [ ] 1  Source: ___
  5.3 Design Differentiation:  [ ] 0  [ ] 1  Source: ___
  5.4 Private Label Viability: [ ] 0  [ ] 1  Source: ___
  5.5 IP Clearance:            [ ] 0  [ ] 1  Source: ___
  Subtotal: ___/5

Category 6 - Scalability:
  6.1 Supplier Availability:   [ ] 0  [ ] 1  Source: ___
  6.2 Reorder Consistency:     [ ] 0  [ ] 1  Source: ___
  6.3 Seasonal Dependency:     [ ] 0  [ ] 1  Source: ___
  6.4 Trend Durability:        [ ] 0  [ ] 1  Source: ___
  6.5 Multi-Platform Potential:[ ] 0  [ ] 1  Source: ___
  Subtotal: ___/5

TOTAL SCORE: ___/30

Decision: [ ] Strong Go (21-30)
          [ ] Conditional Go (16-20)
          [ ] Weak - Reconsider (11-15)
          [ ] Hard No (0-10)

Notes / Weak Areas to Address:
___________________________________
___________________________________
```

---

## Go/No-Go Decision Matrix

| Score Range | Decision | Required Actions |
|---|---|---|
| **21-30** | **Strong Go** | Proceed to `cbec-ops:supplier-sourcing`. Document scorecard. Set launch timeline. |
| **16-20** | **Conditional Go** | Identify all categories scoring 2/5 or below. Create written mitigation plan for each. Get explicit seller acknowledgment of accepted risks. Proceed only after mitigations are documented. |
| **11-15** | **Weak - Reconsider** | Do NOT proceed unless at least 2 weak categories can be definitively fixed (not "probably" or "hopefully" fixed). Require re-scoring after fixes. In most cases, move to the next candidate. |
| **0-10** | **Hard No** | Kill this product immediately. Do not rationalize. Do not "test with a small batch." Do not revisit unless market conditions fundamentally change. Move to the next candidate in the pipeline. |

---

## Category Minimum Thresholds

Even if the total score meets the threshold, certain category scores should
trigger additional scrutiny:

| Category | Minimum Score | If Below Minimum |
|---|---|---|
| **Demand Validation** | 3/5 | Without proven demand, nothing else matters. Hard stop. |
| **Margin Viability** | 3/5 | Unprofitable products do not become profitable at scale. Hard stop. |
| **Logistics Feasibility** | 3/5 | Logistics problems compound with volume. Conditional stop; requires written mitigation. |
| **Competition Analysis** | 2/5 | Competitive markets can still work with strong differentiation. Review with Differentiation score. |
| **Differentiation Potential** | 2/5 | Low differentiation in a competitive market = commodity trap. Review with Competition score. |
| **Scalability** | 2/5 | Low scalability is acceptable for a test product but not for a core SKU. Flag for review at reorder. |

**Critical rule**: If both Competition Analysis AND Differentiation Potential
score below 3/5, this is a **Hard No** regardless of total score. You cannot
win in a competitive market without differentiation.

---
name: product-selection
description: >
  Use when the seller asks about finding products to sell, evaluating product
  ideas, validating demand for a specific product, comparing product
  opportunities, building a product shortlist, or deciding whether to proceed
  with a purchase order. Also activate when the seller mentions BSR analysis,
  niche research, product scoring, or "should I sell X?"
---

# Product Selection

Help sellers find and validate winning products through rigorous, data-driven
scoring. This skill enforces discipline: every product idea must survive
objective validation before capital is committed.

## The Product Selection Iron Law

> **A product that cannot be validated with data is a gamble, not a business
> decision. Every product MUST pass the 30-point validation scorecard with a
> score of 21+ before any purchase order is placed.**

There are no exceptions. Gut feelings, anecdotes, and "I just know" are not
validation. The scorecard exists to protect the seller from the most expensive
mistake in e-commerce: committing inventory dollars to a product that does not
sell.

## Rationalization Table

When a seller presents a product idea with conviction but without data, they
are almost always rationalizing. Recognize these patterns and redirect to
evidence.

| What the Seller Says | What Is Actually Happening | Correct Response |
|---|---|---|
| "I just know this will sell" | **Confirmation bias.** The seller has emotionally committed before validating. They will unconsciously filter out disconfirming data. | "Let's prove it. Show me the search volume data, BSR range, and competitor count. If the data agrees with your instinct, we proceed." |
| "Competition is low" | **Low competition often means low demand.** Empty niches are usually empty for a reason: no buyers, regulatory barriers, or the category is dying. | "Low competition is only valuable when paired with proven demand. What is the monthly search volume? What is the top seller's BSR?" |
| "I can beat them on price" | **Price war = margin death.** Competing on price alone is a race to zero. Sellers who undercut attract bargain hunters with no loyalty. Chinese factories will always undercut further. | "Price is the weakest moat. What is your landed cost? What margin remains at the competitor's price minus 15%? If it's under 25%, this is unsustainable." |
| "Reviews are bad so it's easy to win" | **Category-wide bad reviews signal a product defect baked into the category.** If all competitors have the same complaint, the problem may be unsolvable at the seller's price point. | "Read the top 20 one-star reviews across 5 competitors. Are they complaining about the same thing? If yes, can you solve it for under $2 additional COGS?" |
| "It's trending on TikTok" | **TikTok viral products have a 2-6 week lifecycle.** By the time you source, ship, and list, the trend is dead. Dozens of sellers flood in simultaneously. | "Check Google Trends for the 12-month view. Is this a spike or sustained growth? What is the BSR trajectory on Amazon for the same product?" |
| "My friend is selling this and making money" | **Survivorship bias.** You hear about the one friend who succeeded; you do not hear about the fifty who failed with the same product. | "What is their actual net margin after ad spend, returns, and storage fees? How many units per month? Can they share their Seller Central screenshot?" |
| "The margin is huge" | **High margin with zero demand is still zero revenue.** A 70% margin means nothing if you sell 3 units per month. | "What is the estimated monthly sales volume at the top 10 BSR in this subcategory? Multiply by your margin. Is the absolute profit worth your time?" |
| "I'll test with a small batch" | **Small batches have higher per-unit costs**, often 30-60% more than MOQ pricing. The "test" runs at an artificially bad margin, then the seller concludes the product doesn't work when the real problem was unit economics. | "What is the MOQ price vs. your small-batch price? Model the P&L at both. If the small batch cannot break even with PPC, the test is invalid." |
| "The supplier says it sells well" | **Suppliers profit from your order, not your sales.** They have zero incentive to tell you a product won't sell. Their "bestseller" claim means they ship a lot of it, not that end consumers are buying it. | "Supplier claims are marketing, not validation. Cross-reference with Amazon BSR data, Google search volume, and competitor review velocity." |
| "I found it on a product research tool's hot list" | **Everyone using that tool sees the same list.** If a product appears on a popular tool's recommended list, hundreds of sellers are already evaluating it. First-mover advantage is gone. | "How many days ago did this appear on the list? Check how many new listings appeared in the last 30 days for this keyword. Saturation may already be underway." |

## The Validation Workflow

Every product idea follows this four-stage funnel. Each stage is a gate:
failing at any stage means the product is killed or sent back for rework.

### Stage 1: Discover

Generate a broad list of product candidates from multiple sources.

**Inputs:**
- Target market (from `cbec-ops:market-research` output)
- Seller constraints (capital, category experience, risk tolerance)
- Trend signals (see `references/trend-sources.md`)

**Activities:**
1. Mine trend sources for rising demand signals
2. Scan competitor new arrivals (last 90 days) on target platform
3. Review supplier hot lists on 1688.com, Alibaba, AliExpress
4. Analyze search query data (Google Trends, platform search suggestions)
5. Check social commerce signals (TikTok, Instagram, Pinterest)

**Output:** A raw candidate list of 20-50 product ideas with source noted.

### Stage 2: Filter (Quick-Kill Criteria)

Apply instant disqualifiers to cut the list down fast. Any single quick-kill
criterion eliminates the product immediately.

**Quick-Kill Criteria (any one = instant elimination):**

| # | Criterion | Threshold | Why It Kills |
|---|---|---|---|
| 1 | **Legal/IP restriction** | Product is patented, trademarked, or restricted for import | Lawsuit risk, customs seizure, account suspension |
| 2 | **Gated category** | Seller cannot get approval to list | Cannot sell regardless of demand |
| 3 | **Hazmat/regulated** | Requires special certifications the seller lacks (FDA, FCC, CE) | Compliance cost and timeline make entry impractical |
| 4 | **Dominated by major brand** | Top 5 results are all recognized brands with 5000+ reviews | Organic ranking is nearly impossible without massive ad spend |
| 5 | **Average selling price < $12** | After fees, shipping, and ads, margin is negative or negligible | Unit economics do not work for cross-border sellers |
| 6 | **Average selling price > $75** | High price = low impulse buying, high return rate, large capital requirement | Risk per unit is too high for new sellers |
| 7 | **Oversized/heavy** | Shipping cost exceeds 30% of retail price | Logistics eat the margin; FBA fees are punishing |
| 8 | **Fragile/liquid/battery** | High damage rate, shipping restrictions, or customs complications | Returns, compliance headaches, and carrier surcharges |
| 9 | **Extreme seasonality** | >70% of annual sales in a single quarter | Cash flow disaster; dead stock for 9 months |
| 10 | **Review velocity stalled** | Top 10 listings show <5 new reviews/month each | Market is dead or declining; no new buyers entering |

**Output:** A filtered shortlist of 5-15 candidates that survive all quick-kill
checks.

### Stage 3: Score (30-Point Validation)

Run every surviving candidate through the full 30-point validation scorecard.
See `references/validation-checklist.md` for the complete scorecard with
data sources and scoring instructions.

**Process:**
1. For each candidate, systematically collect data for all 30 checkpoints
2. Score each checkpoint as 0 (fail) or 1 (pass)
3. Sum scores across all 6 categories
4. Apply the Go/No-Go threshold

**Go/No-Go Thresholds:**

| Score | Decision | Action |
|---|---|---|
| 21-30 | **Strong Go** | Proceed to supplier sourcing. Product has strong fundamentals. |
| 16-20 | **Conditional Go** | Identify which categories scored low. Create a mitigation plan for each weak area before proceeding. Document accepted risks. |
| 11-15 | **Weak - Reconsider** | Product has fundamental problems. Only proceed if 2+ weak categories can be definitively resolved. Usually better to move on. |
| 0-10 | **Hard No** | Kill this product. Do not rationalize. Do not "test with a small batch." Move to the next candidate. |

**Output:** Ranked shortlist of 1-5 scored candidates with detailed scorecards.

### Stage 4: Decide

Select the final product(s) to pursue. This is a portfolio decision, not just
a single-product decision.

**Decision Framework:**
1. **Top scorer wins** unless the seller has a specific strategic reason to
   override (document that reason)
2. **Never launch more than 2-3 new products simultaneously** for sellers with
   < 12 months experience
3. **Capital allocation**: no single product should consume more than 40% of
   available inventory budget
4. **Risk diversification**: if launching 2+ products, they should be in
   different subcategories
5. **Timeline check**: can all products be sourced, shipped, and listed within
   the seller's target launch window?

**Output:** Final selection with scorecard, sourcing brief (hand off to
`cbec-ops:supplier-sourcing`), and pricing model skeleton (hand off to
`cbec-ops:pricing-strategy`).

## Category Selection Strategy

Before individual product selection, sellers should narrow their category focus.
Spreading across unrelated categories wastes research time and prevents
building category expertise.

### Category Evaluation Criteria

| Factor | What to Assess | Ideal State |
|---|---|---|
| **Market size** | Total addressable market in target geography | Large enough to support 5+ sellers profitably |
| **Growth trajectory** | Is the category growing, stable, or declining? | Growing or stable; avoid declining categories |
| **Barrier to entry** | Certifications, capital, expertise required | Moderate barriers (keeps out casual sellers but not insurmountable) |
| **Review moat depth** | How many reviews do top sellers have? | < 2000 reviews for #1 seller in subcategory |
| **Return rate** | Category average return rate | < 8% for most categories; < 3% ideal |
| **Seasonality** | Revenue distribution across months | Even distribution or predictable peaks |
| **Seller expertise** | Does the seller have relevant knowledge? | Any domain knowledge is a meaningful advantage |
| **Supplier density** | Number of manufacturers on 1688/Alibaba | 50+ suppliers = competitive pricing and backup options |

### Category Sweet Spot

The ideal category for a new cross-border seller has:
- Annual market size of $50M-$500M on the target platform
- Growth rate of 10-30% year-over-year
- No single brand holding >25% market share
- Average review count of 100-1500 for page-one sellers
- Average selling price of $18-$55
- Return rate under 5%
- Multiple qualified suppliers on 1688.com

## Red Flags and Common Mistakes

### Product Red Flags

- **Single-source dependency**: only one factory in the world makes this
  component. If they raise prices or shut down, you are dead.
- **Compliance complexity**: the product requires UL, FDA, CE, FCC, or other
  certifications you have not budgeted for. Certification can cost $3,000-
  $15,000+ and take 2-6 months.
- **Intellectual property minefield**: the product resembles a patented design,
  even if the seller thinks it is "different enough." Amazon Brand Registry
  complaints trigger immediately.
- **Weight-to-value ratio**: the product is heavy or bulky relative to its
  price. Shipping costs will eat margins, especially for cross-border sellers
  paying international freight.
- **High return categories**: clothing (30%+ return rate), electronics (15%+),
  fragile items. Returns destroy margin twice: you pay shipping both ways and
  the returned unit is often unsellable.
- **Consumables with shelf life**: expiration dates mean dead stock. Customs
  delays can eat months of shelf life. Health/food items have additional
  regulatory requirements in most markets.

### Process Red Flags

- **Skipping the scorecard**: "I don't need to score it, the numbers are
  obviously good." This is the most common precursor to a failed product
  launch.
- **Scoring with outdated data**: BSR and search volume data older than 30 days
  is unreliable. Always use fresh data.
- **Anchoring on a single metric**: a product with amazing search volume but
  terrible margins is not a good product. All six scorecard categories matter.
- **Ignoring negative signals**: sellers who have already decided often
  unconsciously dismiss red flags. The scorecard forces objective evaluation.
- **Rushing to source before validating**: contacting suppliers before
  completing the validation workflow wastes time and creates sunk-cost
  pressure to continue with a bad product.
- **Copy-paste products**: launching an identical product to the top seller
  with no differentiation. You will lose on reviews, ranking, and price.

## Cross-References

| Relationship | Skill | Purpose |
|---|---|---|
| **PREREQUISITE** | `cbec-ops:market-research` | Market selection must be completed before product selection begins. You need to know WHERE you are selling before choosing WHAT to sell. |
| **REQUIRED SUB-SKILL** | `cbec-ops:supplier-sourcing` | After a product passes validation, supplier sourcing begins. The scorecard output feeds directly into the supplier brief. |
| **REQUIRED SUB-SKILL** | `cbec-ops:pricing-strategy` | Margin viability scoring requires preliminary pricing. Full pricing strategy is completed after supplier quotes are received. |
| **RELATED** | `cbec-ops:platform-compliance` | Quick-kill criteria include gated categories and compliance requirements. Consult platform-compliance for detailed regulatory guidance. |
| **RELATED** | `cbec-ops:data-analytics` | Ongoing product performance tracking after launch feeds back into product selection decisions for the next product cycle. |
| **RELATED** | `cbec-ops:seasonal-planning` | Seasonality assessment in the scorecard should be cross-referenced with seasonal planning for launch timing. |

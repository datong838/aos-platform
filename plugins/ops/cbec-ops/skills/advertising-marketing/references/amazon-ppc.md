# Amazon PPC Campaign Guide

A comprehensive reference for setting up, managing, and optimizing Amazon
Pay-Per-Click advertising campaigns for cross-border e-commerce sellers.

---

## Table of Contents

1. [Campaign Types](#campaign-types)
2. [Campaign Structure](#campaign-structure)
3. [Match Types](#match-types)
4. [Keyword Research for PPC](#keyword-research-for-ppc)
5. [Bid Strategies](#bid-strategies)
6. [Budget Allocation by Campaign Type](#budget-allocation-by-campaign-type)
7. [Negative Keyword Strategy](#negative-keyword-strategy)
8. [Keyword Harvesting Workflow](#keyword-harvesting-workflow)
9. [ACOS Optimization Techniques](#acos-optimization-techniques)
10. [Dayparting and Bid Scheduling](#dayparting-and-bid-scheduling)
11. [Sponsored Brands Video Best Practices](#sponsored-brands-video-best-practices)
12. [Amazon DSP Overview](#amazon-dsp-overview)
13. [Common Amazon PPC Mistakes](#common-amazon-ppc-mistakes)

---

## Campaign Types

### Sponsored Products (SP)

The foundation of Amazon PPC. Sponsored Products ads appear in search results
and on product detail pages, looking nearly identical to organic listings.

**When to use:** Always. This should be the first campaign type launched and
typically receives the largest budget share.

**Key characteristics:**
- Keyword-targeted and product-targeted (ASIN targeting)
- Appears in search results (top of search, rest of search) and product pages
- Automatic and manual targeting options
- No brand registry required
- Highest conversion rate among all ad types (shoppers have high purchase intent)

**Best for:** Direct sales, keyword ranking, product discovery.

### Sponsored Brands (SB)

Banner-style ads that appear at the top of search results, featuring your brand
logo, a custom headline, and up to three products.

**When to use:** After establishing profitable Sponsored Products campaigns and
when you have Brand Registry. Use for brand awareness and to capture top-of-
funnel traffic.

**Key characteristics:**
- Requires Brand Registry enrollment
- Custom headline (50 characters), brand logo, and product selection
- Links to Brand Store or custom landing page
- Keyword-targeted and product-targeted
- Higher CPC than Sponsored Products (premium placement)
- Lower direct conversion rate but strong brand halo effect

**Best for:** Brand visibility, driving traffic to Brand Store, category
dominance positioning.

### Sponsored Display (SD)

Display ads that appear on product detail pages, review pages, and off-Amazon
on third-party websites and apps within Amazon's ad network.

**When to use:** After SP and SB are running profitably. Use for retargeting,
competitor conquest, and audience expansion.

**Key characteristics:**
- Product targeting (specific ASINs or categories) and audience targeting
- Retargeting shoppers who viewed your product or similar products
- Appears on and off Amazon (extended reach)
- Lower CPC than SP/SB for some placements
- Longer attribution window (14 days vs 7 days for SP)

**Best for:** Retargeting, competitor product page conquest, audience building.

### Sponsored Brands Video (SBV)

Auto-playing video ads that appear in search results, delivering high visibility
and engagement.

**When to use:** When you have video creative assets (15-30 seconds) and want to
stand out in search results. Highly effective for demonstrating product features
or use cases.

**Key characteristics:**
- Requires Brand Registry
- Video auto-plays in search results (muted, with captions recommended)
- Links directly to product detail page
- Often lower CPC than standard Sponsored Brands
- Significantly higher CTR than text/image ads
- Single-product focus (not multi-product like SB)

**Best for:** Product demonstration, differentiation in crowded categories,
higher CTR at competitive CPC.

---

## Campaign Structure

Organize campaigns in a clear hierarchy for manageable optimization.

```
Portfolio (optional grouping)
 |
 +-- Campaign (budget + targeting type + strategy)
      |
      +-- Ad Group (theme/keyword cluster + bid)
           |
           +-- Keywords / Targets (what triggers the ad)
           +-- Ads (which products are advertised)
```

### Recommended Structure for a Single Product

```
Portfolio: [Product Name / SKU]
 |
 +-- SP - Auto - [Product Name]
 |    (Single ad group, automatic targeting, keyword discovery)
 |
 +-- SP - Manual Exact - [Product Name]
 |    (Ad groups by keyword theme, exact match, proven converters)
 |
 +-- SP - Manual Broad/Phrase - [Product Name]
 |    (Ad groups by keyword theme, expansion targeting)
 |
 +-- SP - Product Targeting - [Product Name]
 |    (Target competitor ASINs and complementary products)
 |
 +-- SB - Brand Headline - [Product Name]
 |    (Top of search branding, links to Brand Store)
 |
 +-- SBV - Video - [Product Name]
 |    (Video ads on proven high-converting keywords)
 |
 +-- SD - Retargeting - [Product Name]
      (Views remarketing and competitor targeting)
```

### Campaign Naming Convention

Use a consistent naming pattern for easy filtering and reporting:

```
[Type]-[Targeting]-[Match]-[Product]-[Notes]

Examples:
SP-Manual-Exact-GardenHose-Core
SP-Auto-Discovery-GardenHose
SP-ASIN-Competitors-GardenHose
SB-Headline-GardenHose-BrandStore
SBV-Video-GardenHose-DemoClip
SD-Retarget-GardenHose-Views
```

---

## Match Types

### Broad Match

Ads can show for searches that include the keyword terms in any order, plus
related terms, synonyms, and close variations.

**Example:** Keyword "garden hose" can match:
- "garden hose 50 feet"
- "hose for garden watering"
- "outdoor water hose"
- "gardening hose flexible"

**When to use:**
- Early-stage keyword discovery
- Expanding reach for high-volume keywords
- Finding long-tail variations you haven't thought of

**Bid guidance:** Set bids 20-30% lower than exact match bids (lower expected
conversion rate due to broader matching).

### Phrase Match

Ads show for searches that contain the keyword phrase in order, with possible
additions before or after.

**Example:** Keyword "garden hose" can match:
- "50 foot garden hose"
- "garden hose with nozzle"
- "best garden hose for small yard"

**Cannot match:** "garden flexible hose" (breaks phrase order).

**When to use:**
- Controlled expansion beyond exact match
- Capturing long-tail variations while maintaining relevance
- When you want word-order specificity

**Bid guidance:** Set bids 10-15% lower than exact match bids.

### Exact Match

Ads show only for searches that closely match the keyword, including close
variations (plurals, minor misspellings).

**Example:** Keyword "garden hose" can match:
- "garden hose"
- "garden hoses"

**Cannot match:** "garden hose 50 feet" (additional terms excluded).

**When to use:**
- Proven high-converting keywords
- Maximum bid control and ACOS management
- Core keywords where you want precise budget allocation

**Bid guidance:** Highest bids (this is where you know intent matches best).

### Match Type Strategy Summary

| Stage | Primary Match Types | Purpose |
|---|---|---|
| Launch (weeks 1-4) | Auto + Broad | Maximum discovery, data collection |
| Growth (months 2-3) | Broad + Phrase + Exact | Graduated control, promoting winners |
| Optimization (month 4+) | Exact (primary) + Phrase (secondary) | Efficiency-focused, tight ACOS control |
| Ongoing | All three + Auto (at low budget) | Exact for profit, Broad for continued discovery |

---

## Keyword Research for PPC

### Method 1: Auto Campaign Mining

The most reliable source of converting keywords because the data comes from
actual shopper behavior on your listing.

**Process:**
1. Launch an auto campaign with a moderate daily budget ($15-30)
2. Run for 7-14 days to accumulate data
3. Download the Search Term Report
4. Filter for terms with 2+ orders and ACOS below break-even
5. Move those terms to manual exact campaigns
6. Add poor-performing terms (high spend, zero orders) as negatives

### Method 2: Competitor ASIN Reverse Lookup

Identify keywords that competitors rank for and advertise on.

**Process:**
1. Identify top 5-10 competitor ASINs in your subcategory
2. Use reverse ASIN tools (Helium 10 Cerebro, Jungle Scout Keyword Scout) to
   extract their indexed and ranking keywords
3. Filter for keywords with 1000+ monthly search volume
4. Cross-reference with your own indexing (check if your listing appears for
   those terms)
5. Add high-relevance, high-volume terms to broad/phrase campaigns for testing

### Method 3: Amazon Search Suggestions

Free method using Amazon's own autocomplete.

**Process:**
1. Type your root keyword into the Amazon search bar
2. Note all autocomplete suggestions (these reflect real search volume)
3. Add letters after your keyword ("garden hose a", "garden hose b", etc.)
4. Compile the full list of suggestions
5. Use Brand Analytics (if available) to check search frequency rank

### Method 4: Brand Analytics

Available to Brand Registry sellers. Provides actual Amazon search data.

**Process:**
1. Access Brand Analytics in Seller Central
2. Review Top Search Terms report for your category
3. Identify keywords with high search frequency rank and low click concentration
   (opportunity for new entrants)
4. Cross-reference with competitor ASIN analysis
5. Prioritize keywords where top 3 clicked ASINs have fewer reviews than yours

### Method 5: Product Targeting Keywords

Target specific competitor ASINs or categories rather than keywords.

**Candidate selection criteria:**
- Competitor products with lower ratings than yours (3.5-4.0 stars vs your 4.3+)
- Competitor products priced higher than yours with similar features
- Complementary products where your product is a natural cross-sell
- New competitor listings with few reviews (vulnerable to displacement)

---

## Bid Strategies

### Dynamic Bids - Down Only (Recommended Starting Point)

Amazon reduces your bid in real time when a click is less likely to convert.
Your bid is the maximum; actual CPC will often be lower.

**When to use:**
- Default strategy for all new campaigns
- Conservative approach that protects against wasted spend
- Best for sellers who are still learning their keyword economics

**Behavior:** Amazon may reduce your bid by up to 100% (to $0) for low-
conversion-probability placements but will never exceed your set bid.

### Dynamic Bids - Up and Down

Amazon increases your bid by up to 100% for top-of-search placements (where
conversion probability is highest) and decreases for lower-probability
placements.

**When to use:**
- After you have 2-4 weeks of conversion data showing which keywords convert
- When your target ACOS allows room for higher CPCs on top placements
- For proven high-converting keywords where top-of-search position is critical

**Caution:** This can double your effective CPC on top-of-search placements.
Only use when you are confident in your conversion rate and margin.

### Fixed Bids

Amazon uses your exact bid for all placements without any adjustment.

**When to use:**
- When you want full manual control over spend
- For campaigns where you are testing placement performance
- For product targeting campaigns where you want consistent visibility

**Limitation:** You may overpay for low-conversion placements or underbid for
high-conversion placements. Requires more active management.

### Placement Bid Adjustments

In addition to the bid strategy, you can set percentage multipliers for specific
placements:

| Placement | Adjustment Range | When to Increase |
|---|---|---|
| Top of search (first page) | 0-900% | When top-of-search converts at 2x+ your average; highest visibility |
| Product pages | 0-900% | When product-page placements show strong conversion (retargeting effect) |
| Rest of search | Base bid (no adjustment) | Default placement; adjust others relative to this baseline |

**How to set placement adjustments:**
1. Run campaigns for 14+ days with "down only" bidding
2. Pull placement report from Campaign Manager
3. Compare conversion rate and ACOS by placement
4. If top-of-search ACOS is 50%+ better than average, increase top-of-search
   multiplier by 25-50%
5. Reassess every 2 weeks

---

## Budget Allocation by Campaign Type

### Launch Phase Budget Split (First 60 Days)

| Campaign Type | Budget Share | Daily Budget Example ($50/day total) |
|---|---|---|
| SP Auto (discovery) | 25% | $12.50 |
| SP Manual Exact | 30% | $15.00 |
| SP Manual Broad/Phrase | 20% | $10.00 |
| SP Product Targeting | 10% | $5.00 |
| SB Headline | 10% | $5.00 |
| SBV Video | 5% | $2.50 |

### Steady-State Budget Split

| Campaign Type | Budget Share | Daily Budget Example ($50/day total) |
|---|---|---|
| SP Manual Exact | 40% | $20.00 |
| SP Manual Broad/Phrase | 15% | $7.50 |
| SP Auto (low-budget discovery) | 10% | $5.00 |
| SP Product Targeting | 10% | $5.00 |
| SB Headline | 10% | $5.00 |
| SBV Video | 10% | $5.00 |
| SD Retargeting | 5% | $2.50 |

### Budget Rules

1. **Never let a profitable campaign run out of budget.** If a campaign
   consistently hits its daily budget before end-of-day and ACOS is below
   target, increase the budget.
2. **Pause campaigns that spend $50+ with zero conversions.** After sufficient
   data (50+ clicks), a zero-converting campaign needs structural changes, not
   more budget.
3. **Reallocate weekly.** Move budget from underperformers to outperformers
   every week during the optimization cycle.

---

## Negative Keyword Strategy

Negative keywords prevent your ads from showing for irrelevant or unprofitable
searches. This is one of the highest-ROI optimization activities.

### Types of Negatives

| Type | Scope | When to Use |
|---|---|---|
| Negative Exact | Blocks only that specific term | When a specific search term has high spend and zero/low conversions |
| Negative Phrase | Blocks any search containing that phrase | When an entire category of searches is irrelevant |

### Sources of Negative Keywords

1. **Search Term Report (primary source)**
   - Terms with 10+ clicks and zero orders: add as negative exact
   - Terms with high spend and ACOS 3x+ above target: add as negative exact
   - Irrelevant root terms appearing repeatedly: add as negative phrase

2. **Pre-launch negative list (add before starting campaigns)**
   - Competitor brand names (unless doing conquest campaigns intentionally)
   - Unrelated product types that share keywords
   - Wrong size/color/material variations you do not sell
   - "Free," "cheap," "used," "wholesale" (unless relevant to your strategy)
   - "How to," "what is," "DIY" (informational intent, not purchase intent)

3. **Category-specific negatives**
   - If selling a 50-foot garden hose, negate "100 foot," "25 foot" etc.
   - If selling a blue variant only, negate other colors
   - If selling for residential use, negate "commercial," "industrial"

### Negative Keyword Workflow

```
Weekly:
1. Download Search Term Report (last 7 days, with 48-hour lag)
2. Filter: Spend > $3 AND Orders = 0
3. Review each term for relevance
4. Irrelevant terms -> Negative Phrase (campaign or ad group level)
5. Relevant but non-converting -> Negative Exact (watch for 2 more weeks
   before permanent negative)

Monthly:
1. Review all negative keywords for accuracy
2. Remove negatives that may have been added prematurely
3. Cross-reference with new product variations (a negative for "red" should
   be removed if you now sell a red variant)
```

---

## Keyword Harvesting Workflow

The auto-to-manual promotion cycle is the core engine of Amazon PPC optimization.

### The Harvesting Funnel

```
Auto Campaign (broad net, keyword discovery)
    |
    | Search Term Report analysis (weekly)
    |
    v
Broad/Phrase Campaign (controlled expansion, validation)
    |
    | Performance validation (2-4 weeks)
    |
    v
Exact Campaign (precise targeting, profit maximization)
    |
    | Ongoing optimization (bid adjustment, budget allocation)
    |
    v
Profitable Keywords Portfolio (long-term asset)
```

### Step-by-Step Process

**Step 1: Auto Campaign Seeding**
- Launch auto campaign with $15-25/day budget
- Set default bid at 75% of suggested bid (start conservative)
- Let run for 7-14 days without changes (resist the urge to optimize early)

**Step 2: Harvest from Auto**
- Download Search Term Report
- Identify terms with: 2+ orders AND ACOS below break-even ACOS
- Add these terms to a Manual Broad or Phrase campaign
- Add these terms as Negative Exact in the Auto campaign (prevent double-serving)

**Step 3: Validate in Broad/Phrase**
- Run promoted terms in broad/phrase for 2-4 weeks
- Monitor for: consistent conversion (not a one-time fluke), sustainable ACOS,
  sufficient volume
- Terms that validate (5+ orders, ACOS within 20% of target): promote to Exact

**Step 4: Optimize in Exact**
- Add validated terms to Manual Exact campaign
- Set bid based on target ACOS: `Bid = Target ACOS x Avg Sale Price x Conv Rate`
- Add as Negative Exact in the Broad/Phrase source campaign
- This is now a long-term keyword asset; optimize bid weekly

**Step 5: Continuous Loop**
- Keep the Auto campaign running at low budget ($5-10/day) for ongoing discovery
- Repeat the harvest cycle weekly
- Over time, Manual Exact campaigns accumulate your proven keyword portfolio

---

## ACOS Optimization Techniques

### Technique 1: Bid-to-Target ACOS Alignment

Calculate the ideal bid for each keyword based on its actual performance data.

```
Ideal Bid = Target ACOS x Average Selling Price x Conversion Rate

Example:
Target ACOS:  25%
Avg Selling Price: $29.99
Conversion Rate:   12%

Ideal Bid = 0.25 x $29.99 x 0.12 = $0.90
```

Apply this formula after 20+ clicks per keyword to have statistically meaningful
conversion data.

### Technique 2: Search Term Isolation

Move all converting search terms to exact match campaigns and negate them in
broad/auto campaigns. This ensures:
- Exact match gets the traffic at your controlled bid
- Broad/auto campaigns do not compete on already-known terms
- Budget in discovery campaigns goes to genuinely new terms

### Technique 3: Dayparting (Time-Based Bid Adjustment)

Analyze hourly performance data and adjust bids/budgets for time periods with
better conversion rates. See the dayparting section below.

### Technique 4: Placement Optimization

Bid higher on placements with better ACOS and lower on placements with worse
ACOS. Top-of-search typically converts best but costs more per click.

### Technique 5: Ad Group Segmentation by Performance

Split ad groups by keyword performance tier:

| Tier | Criteria | Bid Strategy |
|---|---|---|
| Champions | ACOS < 50% of target, 10+ orders/week | Max bid, max budget, protect position |
| Performers | ACOS within target, 3+ orders/week | Standard bid, standard budget |
| Potentials | ACOS slightly above target, converting | Reduce bid 10%, give more time |
| Drains | ACOS 2x+ target or zero conversions after 50 clicks | Pause or drastically reduce bid |

### Technique 6: Single Keyword Campaigns (SKAGs)

For your top 3-5 highest-volume, highest-converting keywords, create dedicated
single-keyword exact-match campaigns. This gives you:
- Precise budget control per keyword
- Clear performance attribution
- Independent bid management without ad-group-level averaging

---

## Dayparting and Bid Scheduling

### Why Dayparting Matters

Conversion rates and CPCs vary significantly by hour of day and day of week.
Running ads at full budget during low-conversion hours wastes spend that could
be reallocated to high-conversion periods.

### How to Analyze Hourly Performance

1. Download the hourly performance report from Campaign Manager (or use a
   third-party tool like Perpetua, Pacvue, or Quartile)
2. Aggregate 30+ days of data for statistical reliability
3. Calculate conversion rate and ACOS by hour of day
4. Identify: peak hours (best ACOS), shoulder hours (average ACOS), dead hours
   (worst ACOS)

### Typical Patterns (US Market, Eastern Time)

| Time Block | Typical Behavior | Recommended Action |
|---|---|---|
| 6am-9am | Rising traffic, moderate conversion | Standard bids |
| 9am-12pm | Peak shopping hours, highest conversion | Increase bids 10-20% |
| 12pm-2pm | Lunch browsing, moderate conversion | Standard bids |
| 2pm-6pm | Afternoon shopping, strong conversion | Increase bids 10% |
| 6pm-10pm | Evening shopping, high traffic, moderate conversion | Standard bids, watch ACOS |
| 10pm-12am | Late browsing, lower conversion | Reduce bids 10-20% |
| 12am-6am | Lowest traffic and conversion | Reduce bids 20-30% or pause |

**Important:** These are general patterns. Your specific product category may
differ significantly. Always use your own data over general benchmarks.

### Implementation

Amazon does not offer native bid scheduling. Options:
- **Manual method:** Adjust daily budgets at key times (labor-intensive)
- **Third-party tools:** Perpetua, Pacvue, Quartile, Scale Insights, and others
  offer automated dayparting with rule-based bid adjustments
- **Budget pacing:** Set daily budgets so they exhaust during peak hours rather
  than running evenly across 24 hours

---

## Sponsored Brands Video Best Practices

### Video Specifications

| Attribute | Requirement |
|---|---|
| Duration | 15-30 seconds (recommended: 20-25 seconds) |
| Aspect ratio | 16:9 |
| Resolution | 1920x1080 minimum |
| File size | Under 500MB |
| Format | MP4, MOV |
| Audio | Optional but recommended |

### Creative Guidelines

1. **Hook in the first 3 seconds.** Video auto-plays silently in search results.
   The first frame and first 3 seconds must visually communicate what the product
   is and why the shopper should care.

2. **Show the product immediately.** Do not start with a logo animation or brand
   intro. Shoppers scroll fast; the product must be visible in frame 1.

3. **Demonstrate, do not describe.** Show the product in use. A garden hose
   being unwound, connected, and spraying water is more compelling than text
   listing features.

4. **Include text overlays.** Video plays muted by default. Key selling points
   must be readable as text on screen, not only spoken.

5. **End with a clear call to action and product shot.** The last 3-5 seconds
   should show the product clearly with a CTA ("Shop Now," "Learn More").

6. **Loop-friendly design.** The video loops automatically. Ensure the ending
   transitions smoothly back to the beginning.

### Performance Benchmarks

| Metric | Good | Great | Exceptional |
|---|---|---|---|
| CTR | 0.35%+ | 0.50%+ | 0.75%+ |
| Video completion rate | 50%+ | 65%+ | 80%+ |
| ACOS | Below target | 20%+ below target | 40%+ below target |
| CPC | Below SP average | 20%+ below SP average | 40%+ below SP average |

SBV often achieves lower CPCs than standard Sponsored Brands because fewer
advertisers compete in the video format. This is an efficiency opportunity.

---

## Amazon DSP Overview

Amazon Demand-Side Platform (DSP) is programmatic display and video advertising
that reaches audiences both on and off Amazon.

### When to Consider DSP

DSP is NOT for beginners. Consider DSP only when:
- Monthly ad spend exceeds $10,000 across all campaign types
- SP/SB/SD campaigns are profitable and fully optimized
- You need to reach audiences beyond Amazon's search and product pages
- You want to build upper-funnel awareness with precise Amazon audience data
- You have brand-building goals beyond direct response

### DSP vs Sponsored Display

| Feature | Sponsored Display | DSP |
|---|---|---|
| Minimum spend | No minimum | $10,000-$35,000/month (managed) or self-serve |
| Audience depth | Basic retargeting and product targeting | Full Amazon audience graph (in-market, lifestyle, lookalike) |
| Placement | Amazon properties + limited off-Amazon | Amazon + thousands of third-party sites and apps |
| Creative control | Template-based, limited | Full custom display and video creatives |
| Reporting | Basic | Advanced audience insights and attribution |
| Management | Self-serve in Seller Central | Managed service (Amazon or agency) or self-serve console |

### DSP Use Cases for Cross-Border Sellers

1. **Top-of-funnel awareness:** Reach shoppers in your category who have not yet
   discovered your product
2. **Competitive conquest:** Target audiences who have viewed or purchased from
   competitor products
3. **Cross-sell:** Target your own customers with complementary products
4. **Seasonal pre-launch:** Build awareness before a major sales event
5. **Brand defense:** Retarget shoppers who viewed your listing but did not convert

### Cost Consideration

DSP pricing is typically CPM-based (cost per thousand impressions) rather than
CPC. Expect $3-8 CPM for standard display and $15-30 CPM for video placements.
Attribution is view-through (14-day) which inflates apparent ROAS. Always compare
DSP performance against a holdout group when possible.

---

## Common Amazon PPC Mistakes

### Mistake 1: Launching Only Auto Campaigns and Never Graduating Keywords

Auto campaigns are a discovery tool, not a long-term strategy. Without promoting
winning keywords to manual exact campaigns, you pay higher CPCs for broad
matching and lose control over which searches trigger your ads.

**Fix:** Implement the keyword harvesting workflow from day one. Review search
term reports weekly.

### Mistake 2: Setting One Bid for All Keywords

Different keywords have different conversion rates, competition levels, and
values. A single bid means you overpay for low-value terms and underbid on
high-value terms.

**Fix:** Calculate target bids per keyword using the formula:
`Bid = Target ACOS x Avg Selling Price x Keyword Conversion Rate`

### Mistake 3: Ignoring Negative Keywords

Without negatives, your ads show for irrelevant searches. A garden hose ad
showing for "garden hose repair kit" wastes clicks on shoppers who already own
a hose and want parts, not a new one.

**Fix:** Build a pre-launch negative list and review the search term report
weekly. Be aggressive with negatives in the first 30 days.

### Mistake 4: Panicking and Pausing Campaigns After 3 Days

Amazon PPC data has a 48-72 hour attribution lag. A campaign that looks
unprofitable on Monday may be profitable once Tuesday and Wednesday sales
attribute back. Pausing campaigns too early kills momentum.

**Fix:** Never make optimization decisions on fewer than 7 days of data. For
new campaigns, allow 14 days before structural changes.

### Mistake 5: Duplicating Keywords Across Campaigns Without Negation

If "garden hose" runs in your Auto, Broad, and Exact campaigns simultaneously,
you are bidding against yourself. Amazon shows only one ad per advertiser per
search, but the auction dynamics waste budget.

**Fix:** When promoting a keyword from Auto to Manual, add it as a negative
exact in the Auto campaign. Same when promoting from Broad to Exact.

### Mistake 6: Ignoring Placement Performance Data

Top-of-search placements typically convert at 2-3x the rate of rest-of-search
or product-page placements. Not adjusting bids by placement leaves money on
the table.

**Fix:** Review placement reports biweekly. Use placement bid multipliers to
bid aggressively on high-converting placements.

### Mistake 7: Running Ads on Listings Without the Buy Box

If you do not own the Buy Box, your Sponsored Products ad sends traffic to the
Buy Box holder's offer, not yours. You pay for the click; they get the sale.

**Fix:** Verify Buy Box ownership before launching ads. Pause ads if Buy Box
share drops below 90%. Fix the Buy Box issue (pricing, seller metrics, Prime
eligibility) before restarting ads.

### Mistake 8: Not Tracking Organic Rank Alongside Ad Spend

The purpose of PPC is not just direct sales. PPC drives sales velocity, which
improves organic ranking. If you are spending on PPC and organic rank is not
improving, something is wrong (listing quality, conversion rate, relevance).

**Fix:** Track organic position for your top 10 keywords weekly. If organic rank
stagnates after 4-6 weeks of PPC, investigate listing issues before increasing
ad spend.

### Mistake 9: Budget Caps That Are Too Restrictive

A daily budget of $5 on a campaign targeting 50 keywords means each keyword
gets roughly $0.10/day, which is insufficient to generate meaningful data. The
campaign will never collect enough clicks to optimize.

**Fix:** Either increase budget or reduce the number of keywords per campaign.
Each keyword needs enough budget for 10-15 clicks/day to generate actionable
conversion data within a reasonable timeframe.

### Mistake 10: Not Separating Brand and Non-Brand Keywords

Brand keywords (your own brand name) typically have 5-10x higher conversion
rates than generic keywords. Mixing them in the same campaign inflates apparent
performance and hides poor generic keyword ACOS.

**Fix:** Create separate campaigns for brand terms and generic terms. Evaluate
each independently. Brand campaigns protect your brand search traffic from
competitors; generic campaigns drive new customer acquisition.

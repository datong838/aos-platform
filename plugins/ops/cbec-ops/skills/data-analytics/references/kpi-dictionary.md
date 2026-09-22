# KPI Dictionary for Cross-Border E-Commerce

Complete reference of key performance indicators used across e-commerce
platforms. Each metric includes its definition, formula, benchmark range, data
source, and actionable insight.

## Table of Contents

- [Traffic Metrics](#traffic-metrics)
  - [Sessions](#sessions)
  - [Page Views](#page-views)
  - [Click-Through Rate (CTR)](#click-through-rate-ctr)
  - [Bounce Rate](#bounce-rate)
- [Conversion Metrics](#conversion-metrics)
  - [Conversion Rate (CVR)](#conversion-rate-cvr)
  - [Add-to-Cart Rate](#add-to-cart-rate)
  - [Unit Session Percentage](#unit-session-percentage)
- [Sales Metrics](#sales-metrics)
  - [Revenue](#revenue)
  - [Units Sold](#units-sold)
  - [Average Order Value (AOV)](#average-order-value-aov)
  - [Average Selling Price (ASP)](#average-selling-price-asp)
- [Advertising Metrics](#advertising-metrics)
  - [ACOS (Advertising Cost of Sales)](#acos-advertising-cost-of-sales)
  - [ROAS (Return on Ad Spend)](#roas-return-on-ad-spend)
  - [TACOS (Total Advertising Cost of Sales)](#tacos-total-advertising-cost-of-sales)
  - [CPC (Cost Per Click)](#cpc-cost-per-click)
  - [CTR - Ads (Click-Through Rate for Ads)](#ctr---ads-click-through-rate-for-ads)
  - [Impressions](#impressions)
  - [Ad Spend](#ad-spend)
- [Inventory Metrics](#inventory-metrics)
  - [IPI Score (Inventory Performance Index)](#ipi-score-inventory-performance-index)
  - [Days of Supply](#days-of-supply)
  - [Sell-Through Rate](#sell-through-rate)
  - [Aged Inventory Percentage](#aged-inventory-percentage)
- [Customer Metrics](#customer-metrics)
  - [Review Rating](#review-rating)
  - [Review Velocity](#review-velocity)
  - [Return Rate](#return-rate)
  - [Refund Rate](#refund-rate)
- [Financial Metrics](#financial-metrics)
  - [Gross Margin](#gross-margin)
  - [Net Margin](#net-margin)
  - [Contribution Margin](#contribution-margin)
  - [Customer Lifetime Value (CLTV)](#customer-lifetime-value-cltv)
- [SEO Metrics](#seo-metrics)
  - [Organic Rank](#organic-rank)
  - [Keyword Position](#keyword-position)
  - [Share of Voice](#share-of-voice)

---

## Traffic Metrics

### Sessions

**Definition**: The number of unique visits to a product listing or storefront
within a given time period. A session is typically defined as a continuous
period of activity by one visitor, ending after 30 minutes of inactivity or at
midnight.

**Formula**: Count of unique visitor sessions (platform-defined)

**Benchmark Range**:
- New listing (first 30 days): 10-50 sessions/day
- Established listing (niche category): 50-200 sessions/day
- Top seller (competitive category): 500-5,000+ sessions/day

**Data Source**:
- Amazon: Business Reports > Detail Page Sales and Traffic > Sessions
- Shopify: Analytics > Overview > Online store sessions
- Walmart: Analytics > Item Performance > Page Views (approximation)

**Actionable Insight**: Sessions alone do not indicate quality. A session
increase paired with CVR decrease signals low-quality traffic (often from
broad-match PPC keywords or irrelevant external traffic). Always analyze
sessions alongside conversion rate. If sessions are low but CVR is strong,
the opportunity is to increase traffic through advertising or SEO rather than
changing the listing.

---

### Page Views

**Definition**: The total number of times a product detail page is viewed,
including repeat views by the same visitor within a session. One session can
generate multiple page views.

**Formula**: Total count of page loads for the listing

**Benchmark Range**:
- Page Views / Sessions ratio: 1.0-1.4 is normal
- Ratio > 1.5: visitors are returning to the listing (comparison shopping) or
  browsing variations

**Data Source**:
- Amazon: Business Reports > Detail Page Sales and Traffic > Page Views
- Shopify: Analytics > Reports > Sessions by landing page

**Actionable Insight**: A high page-views-to-sessions ratio can indicate
shoppers are comparing your listing against competitors and returning, which
suggests the listing is a contender but not closing. Check price
competitiveness, review count, and main image quality. For variation listings,
a high ratio is normal as shoppers browse options.

---

### Click-Through Rate (CTR)

**Definition**: The percentage of impressions (search result appearances) that
result in a click to the product detail page. Measures how compelling the
listing appears in search results.

**Formula**: `CTR = (Clicks / Impressions) x 100`

**Benchmark Range**:
- Organic search results: 1-5% (position-dependent; top 3 positions get the
  majority of clicks)
- Sponsored Products: 0.3-0.8% (varies by category and competition)
- Good organic CTR: >2% for a top-10 keyword position

**Data Source**:
- Amazon: Search Query Performance report (Brand Analytics); Advertising
  Console for ad CTR
- Shopify: Google Search Console integration for organic CTR
- TikTok Shop: Data Compass > Product Analysis > Click rate

**Actionable Insight**: CTR is primarily driven by four elements visible in
search results: main image, title, price, and review stars/count. If CTR is
below category average, test a new main image first (highest impact), then
review title keyword placement and pricing. A coupon badge or deal badge can
lift CTR by 10-30%.

---

### Bounce Rate

**Definition**: The percentage of sessions where the visitor leaves the product
page without taking any action (no add-to-cart, no click to another page, no
purchase). Indicates relevance mismatch between what the shopper expected and
what the listing delivers.

**Formula**: `Bounce Rate = (Single-page sessions / Total sessions) x 100`

**Benchmark Range**:
- E-commerce product pages: 20-45%
- Category pages / storefronts: 30-55%
- >60%: significant relevance or quality problem

**Data Source**:
- Amazon: Not directly available; infer from low CVR + high sessions
- Shopify: Google Analytics integration > Behavior > Bounce Rate
- Standalone sites: Google Analytics or equivalent

**Actionable Insight**: High bounce rate combined with adequate sessions
suggests a disconnect between the search query (or ad) and the listing
content. Check that the main image matches what the title promises, the price
is within category norms, and the listing is not misleading. For Amazon, since
bounce rate is not directly reported, use the combination of high sessions +
low CVR + low ATC rate as a proxy.

---

## Conversion Metrics

### Conversion Rate (CVR)

**Definition**: The percentage of sessions that result in at least one unit
purchased. The single most important efficiency metric for any product listing.

**Formula**: `CVR = (Orders / Sessions) x 100`

**Benchmark Range**:
- Amazon average: 10-15%
- Well-optimized listing: 15-25%
- Commodity / low-price item: 20-35%
- High-price / considered purchase: 5-12%
- DTC / Shopify: 1.5-3.5%
- TikTok Shop: 1-5% (content-driven discovery traffic converts lower)

**Data Source**:
- Amazon: Business Reports > Detail Page Sales and Traffic > Unit Session
  Percentage (Amazon's term for CVR)
- Shopify: Analytics > Overview > Online store conversion rate
- TikTok Shop: Data Compass > Product Analysis > Conversion rate

**Actionable Insight**: CVR is the highest-leverage metric for existing
listings. A 1% CVR improvement on a listing with 1,000 weekly sessions adds
10 orders per week with zero additional traffic cost. Optimize in this order:
(1) main image, (2) price/deal, (3) bullet points, (4) A+ content / brand
story, (5) review count and rating. If CVR is strong but revenue is flat, the
constraint is traffic, not conversion.

---

### Add-to-Cart Rate

**Definition**: The percentage of sessions where the shopper adds the product
to their cart, regardless of whether they complete the purchase. Indicates
purchase intent.

**Formula**: `ATC Rate = (Add-to-Cart events / Sessions) x 100`

**Benchmark Range**:
- Amazon: 10-20% (higher than CVR because not all carts convert)
- Shopify: 5-12%
- Good ATC-to-purchase ratio: 30-50% (i.e., 30-50% of carts convert)

**Data Source**:
- Amazon: Search Query Performance report > Cart Adds column
- Shopify: Analytics > Reports > Online store cart analysis
- TikTok Shop: Data Compass > Product Analysis > Add to cart rate

**Actionable Insight**: If ATC rate is healthy but CVR is low, shoppers are
interested but abandoning at checkout. Common causes: high shipping cost
revealed at checkout, competitor price drop between cart and purchase, or
coupon/deal on a competitor listing. If ATC rate itself is low, the listing
content is not compelling enough -- focus on images, bullets, and price
positioning.

---

### Unit Session Percentage

**Definition**: Amazon-specific term for the ratio of units ordered to
sessions. Differs from standard CVR because it counts units, not orders. If
a customer buys 3 units in one session, unit session percentage is 300% for
that session's contribution.

**Formula**: `Unit Session % = (Units Ordered / Sessions) x 100`

**Benchmark Range**:
- Single-unit products: similar to CVR (10-25%)
- Consumables / multi-packs: can exceed 100% if shoppers buy multiple units
- Subscribe & Save products: higher due to multi-unit subscriptions

**Data Source**:
- Amazon: Business Reports > Detail Page Sales and Traffic > Unit Session
  Percentage

**Actionable Insight**: Compare Unit Session % to CVR (Orders / Sessions). If
Unit Session % significantly exceeds CVR, customers are buying multiple units
per order -- a positive signal for consumables. Consider offering multi-pack
variations or Subscribe & Save to further encourage multi-unit purchases.

---

## Sales Metrics

### Revenue

**Definition**: Total sales value (gross) generated by a product or account
within a time period, before deducting fees, returns, ad spend, or COGS. Also
called Gross Merchandise Value (GMV) on some platforms.

**Formula**: `Revenue = Units Sold x Selling Price` (or sum of all order values)

**Benchmark Range**: Highly category- and scale-dependent. Track trend
direction and growth rate rather than absolute benchmarks.
- Healthy growth: 10-30% month-over-month for new products
- Mature products: 0-10% year-over-year growth
- Seasonal categories: compare same period year-over-year

**Data Source**:
- Amazon: Business Reports > Ordered Product Sales
- Shopify: Analytics > Overview > Total sales
- TikTok Shop: Dashboard > GMV

**Actionable Insight**: Revenue growth without margin analysis is misleading.
Always pair revenue tracking with TACOS and net margin. If revenue grows but
TACOS rises proportionally, the growth is ad-subsidized and may not be
profitable. Focus on organic revenue share (total revenue minus ad-attributed
revenue) as the true health indicator.

---

### Units Sold

**Definition**: The total number of individual units ordered within a time
period. A purer demand signal than revenue because it is unaffected by price
changes.

**Formula**: Sum of all units ordered

**Benchmark Range**: Track velocity (units/day) and its trend.
- New product launch target: category BSR equivalent velocity
- Reorder trigger: maintain velocity to avoid rank decay

**Data Source**:
- Amazon: Business Reports > Units Ordered
- Shopify: Analytics > Reports > Sales by product > Net quantity
- TikTok Shop: Dashboard > Orders

**Actionable Insight**: A sudden drop in units with stable sessions and CVR
often indicates a Buy Box loss or suppressed listing. A gradual decline
suggests organic rank erosion or increased competition. Track units separately
from revenue to isolate demand changes from pricing changes.

---

### Average Order Value (AOV)

**Definition**: The average total value of each order placed. Important for
DTC / Shopify stores where customers may purchase multiple products per order.
Less relevant for single-ASIN marketplace analysis.

**Formula**: `AOV = Total Revenue / Number of Orders`

**Benchmark Range**:
- Shopify / DTC stores: $45-$80 (varies widely by niche)
- Amazon: closely approximates ASP for single-product orders
- Cross-border stores: often higher due to bundling for shipping efficiency

**Data Source**:
- Shopify: Analytics > Overview > Average order value
- Amazon: calculated from Business Reports (revenue / orders)

**Actionable Insight**: Increasing AOV is often more efficient than acquiring
new customers. Strategies: product bundling, quantity discounts (buy 2 save
10%), cross-sell recommendations, free shipping thresholds set just above
current AOV. For cross-border sellers, higher AOV also amortizes per-order
shipping costs.

---

### Average Selling Price (ASP)

**Definition**: The average price at which a single unit is sold, after
discounts and promotions but before fees and returns.

**Formula**: `ASP = Total Revenue / Total Units Sold`

**Benchmark Range**: Category-dependent. Track ASP trend to detect price
erosion from competition or over-reliance on promotions.

**Data Source**:
- Amazon: Business Reports (Ordered Product Sales / Units Ordered)
- Shopify: calculated from sales reports

**Actionable Insight**: Declining ASP with stable units indicates margin
compression -- likely from coupons, deals, or competitive price matching.
If ASP decline outpaces COGS reduction, profitability is eroding. Consider
value-based pricing strategies (bundling, premium positioning) to protect ASP.

---

## Advertising Metrics

### ACOS (Advertising Cost of Sales)

**Definition**: The percentage of ad-attributed revenue spent on advertising.
Measures the efficiency of individual advertising campaigns. Lower is better,
but too low may indicate under-investment.

**Formula**: `ACOS = (Ad Spend / Ad Revenue) x 100`

**Benchmark Range**:
- Aggressive launch phase: 40-80% (acceptable to build rank)
- Growth phase: 25-40%
- Profitable steady-state: 15-25%
- Highly optimized / high-margin: <15%
- Break-even ACOS = pre-ad profit margin (e.g., 30% margin = 30% break-even ACOS)

**Data Source**:
- Amazon: Advertising Console > Campaign Manager > ACOS column
- Walmart: Walmart Connect > Campaign Performance
- TikTok Shop: Ads Manager > Campaign Analytics

**Actionable Insight**: Calculate your break-even ACOS before evaluating
campaigns: `Break-even ACOS = (Selling Price - COGS - Fees) / Selling Price`.
Any campaign with ACOS below break-even is profitable on a direct basis.
Campaigns above break-even may still be valuable if they drive organic rank
improvement (flywheel effect). Track ACOS at the keyword level, not just
campaign level, to find and remove wasteful spend.

---

### ROAS (Return on Ad Spend)

**Definition**: The revenue generated per dollar spent on advertising. The
inverse of ACOS, preferred by some platforms and advertisers.

**Formula**: `ROAS = Ad Revenue / Ad Spend` (expressed as a ratio, e.g., 4.0x)

**Benchmark Range**:
- Equivalent to ACOS benchmarks: 25% ACOS = 4.0x ROAS
- Good ROAS: >3.0x (equivalent to <33% ACOS)
- Excellent ROAS: >5.0x (equivalent to <20% ACOS)

**Data Source**:
- Amazon: Advertising Console (calculated from revenue and spend)
- TikTok Shop Ads: Ads Manager > ROAS column
- Google Ads / Meta Ads: native ROAS reporting

**Actionable Insight**: ROAS and ACOS convey the same information in different
formats. Use whichever your team and platform prefer for consistency. The key
insight is the same: track at the keyword and ad group level, not just campaign
level, and compare against your break-even threshold.

---

### TACOS (Total Advertising Cost of Sales)

**Definition**: Total ad spend as a percentage of total revenue (organic +
paid). The single best metric for understanding blended advertising efficiency
and the health of the organic/paid revenue mix.

**Formula**: `TACOS = (Total Ad Spend / Total Revenue) x 100`

**Benchmark Range**:
- Launch phase: 15-30% (heavy ad investment to build organic rank)
- Growth phase: 10-15%
- Mature / optimized: 5-10%
- >20% sustained: over-reliance on paid traffic; organic rank likely weak

**Data Source**:
- Calculated: total ad spend (Advertising Console) / total revenue (Business
  Reports). Not a native metric on most platforms; must be calculated manually
  or via a third-party tool.

**Actionable Insight**: TACOS is the most important advertising metric at the
business level. A declining TACOS with stable or growing revenue means organic
sales are growing faster than ad spend -- the flywheel is working. Rising TACOS
with flat revenue means increasing ad dependency. If TACOS exceeds your
contribution margin, the product cannot be profitable at current advertising
levels. Review weekly and set target TACOS by product lifecycle stage.

---

### CPC (Cost Per Click)

**Definition**: The average amount paid for each click on an advertisement.
Determined by auction dynamics, bid strategy, relevance score, and competition.

**Formula**: `CPC = Total Ad Spend / Total Clicks`

**Benchmark Range**:
- Amazon Sponsored Products: $0.50-$1.50 (varies widely by category)
- High-competition categories (supplements, electronics): $1.50-$4.00+
- Low-competition niches: $0.20-$0.60
- TikTok Shop Ads: $0.10-$0.50 (generally lower than Amazon)
- Google Shopping: $0.30-$1.50

**Data Source**:
- Amazon: Advertising Console > Campaign Manager > CPC column
- TikTok Shop: Ads Manager > CPC
- Google Ads: Campaign > Avg. CPC

**Actionable Insight**: CPC is an input cost, not an efficiency metric. A high
CPC is acceptable if the conversion rate justifies it (low ACOS despite high
CPC). Focus on reducing CPC only when ACOS is above target. Strategies to
lower CPC: improve ad relevance (tighter keyword targeting), increase listing
CVR (better relevance score), use exact match over broad match, daypart ads
to lower-competition hours.

---

### CTR - Ads (Click-Through Rate for Ads)

**Definition**: The percentage of ad impressions that result in a click.
Measures how compelling the ad creative and listing thumbnail are relative to
competing ads in the same auction.

**Formula**: `Ad CTR = (Clicks / Impressions) x 100`

**Benchmark Range**:
- Amazon Sponsored Products: 0.3-0.8%
- Amazon Sponsored Brands: 0.4-1.0%
- Amazon Sponsored Display: 0.1-0.4%
- TikTok Shop Ads: 1-3% (video ads tend to have higher CTR)
- Google Shopping: 1-3%

**Data Source**:
- Amazon: Advertising Console > Campaign Manager > CTR column
- TikTok Shop: Ads Manager > CTR
- Google Ads: Campaign > CTR

**Actionable Insight**: Low ad CTR wastes impressions and signals poor
relevance, which can increase CPC over time (platforms reward high-CTR ads
with lower costs). Improve ad CTR by: (1) optimizing main image (the most
visible element in search ads), (2) ensuring the advertised keyword matches
the product title, (3) adding a coupon badge, (4) for Sponsored Brands, testing
different headline copy and custom images.

---

### Impressions

**Definition**: The total number of times an ad is displayed to shoppers,
regardless of whether it is clicked. Indicates reach and share of voice within
the advertising channel.

**Formula**: Count of ad displays (platform-defined)

**Benchmark Range**: Highly variable by category, keyword volume, and bid
strategy. Track trends rather than absolute numbers.
- Low impressions despite adequate bids: keyword targeting too narrow or listing
  relevance too low
- High impressions with low CTR: targeting too broad or creative underperforming

**Data Source**:
- Amazon: Advertising Console > Campaign Manager > Impressions column
- TikTok Shop: Ads Manager > Impressions
- Google Ads: Campaign > Impressions

**Actionable Insight**: Impressions are a leading indicator of reach. A sudden
impression drop often indicates: budget exhausted early in the day, bid no
longer competitive, or keyword relevance score decreased (often after a listing
content change). If impressions are strong but clicks are weak, the problem is
creative/relevance. If impressions themselves are low, increase bids or broaden
keyword targeting.

---

### Ad Spend

**Definition**: The total amount of money spent on advertising within a given
time period across all campaigns and ad types.

**Formula**: Sum of all advertising costs

**Benchmark Range**: Should be evaluated as a percentage of revenue (TACOS),
not as an absolute number.
- Typical allocation: 10-20% of revenue during growth phase
- Mature allocation: 5-10% of revenue

**Data Source**:
- Amazon: Advertising Console > Overview > Total Spend
- TikTok Shop: Ads Manager > Total Cost
- Multi-platform: aggregate from each platform's ad console

**Actionable Insight**: Track ad spend against a budget that is derived from
target TACOS and revenue forecast. Set daily budget caps to prevent runaway
spend. Review spend distribution: if >80% goes to one campaign or keyword,
the portfolio is dangerously concentrated. Diversify across keywords, match
types, and ad formats to reduce risk.

---

## Inventory Metrics

### IPI Score (Inventory Performance Index)

**Definition**: Amazon's composite score (0-1000) measuring how efficiently
a seller manages FBA inventory. Based on excess inventory, sell-through rate,
stranded inventory, and in-stock rate. Determines storage limits.

**Formula**: Amazon proprietary (weighted composite of four factors)

**Benchmark Range**:
- Minimum threshold: 400 (below this, Amazon may impose storage limits)
- Good: 500-700
- Excellent: >700
- Check quarterly for threshold changes by Amazon

**Data Source**:
- Amazon: Inventory > Inventory Planning > Inventory Performance Dashboard

**Actionable Insight**: IPI directly impacts how much inventory you can store
in FBA. A low IPI restricts storage capacity, which can lead to stockouts
during peak demand. Improve IPI by: (1) removing aged inventory (>90 days
without sales), (2) fixing stranded inventory immediately, (3) maintaining
healthy sell-through rate, (4) avoiding overshipment relative to demand
velocity.

---

### Days of Supply

**Definition**: The estimated number of days current inventory will last at
the current sales velocity. The primary metric for reorder timing.

**Formula**: `Days of Supply = Current Inventory Units / Average Daily Units Sold`

**Benchmark Range**:
- FBA ideal range: 30-60 days (balances stockout risk vs storage cost)
- Minimum safe level: 14-21 days (accounts for reorder + shipping lead time)
- Overstock signal: >90 days (incurring unnecessary storage fees)
- Cross-border shipping: add 15-30 days to minimum for ocean freight lead time

**Data Source**:
- Amazon: Inventory > Inventory Planning > Days of Supply column
- Manual calculation: current FBA units / 7-day average daily sales

**Actionable Insight**: Set reorder points based on lead time plus a safety
buffer: `Reorder Point = (Lead Time in Days x Daily Sales Velocity) + Safety Stock`.
For cross-border sellers with 30-45 day ocean freight, reorder when Days of
Supply drops to 45-60 days. Track separately for each SKU -- aggregate Days
of Supply across all products is meaningless.

---

### Sell-Through Rate

**Definition**: The percentage of inventory that is sold within a specific time
period (typically 90 days). Measures how quickly inventory moves.

**Formula**: `Sell-Through Rate = (Units Sold in Period / Units Available at Start of Period) x 100`

**Benchmark Range**:
- 90-day sell-through: >50% is healthy
- <20% over 90 days: slow-moving inventory; consider markdowns or removal
- Amazon IPI factor: Amazon expects high sell-through for a good IPI score

**Data Source**:
- Amazon: Inventory > Inventory Planning > Sell-Through Rate
- Manual: calculate from inventory snapshots and sales data

**Actionable Insight**: Low sell-through rate incurs long-term storage fees on
Amazon (monthly charges for inventory stored >181 days, with surcharges at
271+ and 365+ days). Improve sell-through by: (1) running promotions on
slow-moving inventory, (2) reducing replenishment quantities, (3) creating
removal orders for dead stock before long-term storage fee assessment dates
(typically 15th of each month).

---

### Aged Inventory Percentage

**Definition**: The proportion of FBA inventory that has been in the warehouse
beyond a defined threshold (typically 90, 180, or 365 days). A direct driver
of long-term storage fees and IPI score reduction.

**Formula**: `Aged Inventory % = (Units > X Days Old / Total FBA Units) x 100`

**Benchmark Range**:
- >90 days: monitor and consider promotion
- >180 days: active disposal or heavy discounting recommended
- >365 days: incurring maximum storage surcharges; remove immediately
- Target: <10% of total inventory should be >90 days old

**Data Source**:
- Amazon: Inventory > Inventory Planning > Inventory Age (age breakdown)
- FBA Inventory Health Report

**Actionable Insight**: Aged inventory is a cash trap: it ties up capital,
incurs storage fees, and depresses IPI score. Review monthly. For units
approaching 180 days, run a Lightning Deal or markdown to 30-50% discount.
For units approaching 365 days, create a removal order (destruction or return
to seller) -- the removal fee is almost always less than the long-term storage
surcharge.

---

## Customer Metrics

### Review Rating

**Definition**: The average star rating (1-5) across all customer reviews for
a product. A critical conversion factor: listings below 4.0 stars see
significant CVR decline.

**Formula**: `Review Rating = Sum of All Star Ratings / Number of Reviews`

**Benchmark Range**:
- Strong: 4.3-5.0 stars
- Acceptable: 4.0-4.2 stars
- Warning zone: 3.5-3.9 stars (CVR impact begins)
- Critical: <3.5 stars (consider product redesign or withdrawal)

**Data Source**:
- Amazon: Product detail page; Brand Analytics > Review Insights
- Shopify: Product reviews app
- All platforms: directly visible on listing

**Actionable Insight**: Rating impacts both CVR and ad efficiency (platforms
may reduce ad delivery for low-rated products). If rating drops below 4.0,
prioritize reading negative reviews to identify root causes. Common fixes:
improve packaging, update listing to set accurate expectations, address quality
issues with supplier. Do not attempt to manipulate reviews -- violations result
in listing suspension.

---

### Review Velocity

**Definition**: The rate at which new reviews are added to a listing over time.
Important for new product launches and competitive positioning.

**Formula**: `Review Velocity = New Reviews in Period / Number of Days in Period`

**Benchmark Range**:
- New product first 90 days: target 1-3 reviews/week
- Established product: 2-10 reviews/week depending on sales volume
- Natural review rate: approximately 1-2% of orders leave a review

**Data Source**:
- Amazon: Track manually or via third-party tools (Helium 10, Jungle Scout)
- Count reviews weekly and track trend

**Actionable Insight**: Review velocity is both a ranking signal and a
conversion factor. To accelerate reviews ethically: (1) enroll in Amazon Vine
for new products, (2) use Request a Review button for all orders, (3) include
a product insert that encourages feedback (without incentivizing), (4) follow
up with buyer-seller messaging where permitted. Monitor competitor review
velocity to understand your relative position.

---

### Return Rate

**Definition**: The percentage of units sold that are returned by customers.
A critical quality and listing-accuracy indicator.

**Formula**: `Return Rate = (Units Returned / Units Sold) x 100`

**Benchmark Range**:
- Category average: 5-15% (highly category-dependent)
- Apparel / shoes: 15-30% (size/fit issues)
- Electronics: 5-10%
- Consumables: 2-5%
- Concerning: >2x category average
- Amazon Account Health risk: excessive returns can trigger listing investigation

**Data Source**:
- Amazon: Reports > Fulfillment > FBA Customer Returns
- Amazon: Performance > Voice of the Customer
- Shopify: calculated from return/refund data

**Actionable Insight**: High return rate erodes profit, harms account health,
and signals listing or product problems. Analyze return reasons: (1) "item not
as described" = listing accuracy problem (update images, bullets), (2) "wrong
item sent" = FBA commingling issue (switch to FNSKU labeling), (3) "defective"
= quality control issue (work with supplier), (4) "no longer needed" = impulse
buy with buyer's remorse (less controllable, but clear pre-purchase info helps).

---

### Refund Rate

**Definition**: The percentage of orders that result in a full or partial
refund, including returns and non-return refunds (e.g., damaged in transit,
customer appeasement). Broader than return rate.

**Formula**: `Refund Rate = (Refunded Orders / Total Orders) x 100`

**Benchmark Range**:
- Normal: 2-8%
- Concerning: >10%
- Should track both full refund rate and partial refund rate separately

**Data Source**:
- Amazon: Reports > Payments > All Statements (refund line items)
- Shopify: Orders > Refunded orders

**Actionable Insight**: Refund rate exceeding return rate indicates non-return
refunds (concessions, replacements). Track the gap between refund rate and
return rate. If the gap is large, investigate FBA damage rates (reimbursement
opportunity), fraudulent "item not received" claims (may need Transparency
program), and customer service concession policies.

---

## Financial Metrics

### Gross Margin

**Definition**: Revenue minus cost of goods sold (COGS), expressed as a
percentage of revenue. Measures the basic profitability of the product before
operating expenses.

**Formula**: `Gross Margin = ((Revenue - COGS) / Revenue) x 100`

**Benchmark Range**:
- Private label products: 60-75%
- Wholesale / arbitrage: 25-40%
- Minimum viable for marketplace selling: 30% (to cover fees and advertising)
- Cross-border: factor in landed cost (product + shipping + duties + insurance)

**Data Source**:
- Calculated from internal COGS data and platform revenue reports
- Must account for all landed costs for accurate cross-border margin

**Actionable Insight**: Gross margin sets the ceiling for all other expenses
(advertising, platform fees, operations). If gross margin is below 50% for
private label, investigate COGS reduction (supplier negotiation, order volume
increases, material substitution) before scaling advertising. For cross-border
sellers, FX rate fluctuations can swing gross margin by 3-10% -- hedge or
build a buffer.

---

### Net Margin

**Definition**: The true bottom-line profit as a percentage of revenue after
all costs: COGS, platform fees, advertising, shipping, returns, storage,
overhead, and taxes.

**Formula**: `Net Margin = ((Revenue - All Costs) / Revenue) x 100`

**Benchmark Range**:
- Healthy Amazon private label: 15-25%
- Acceptable: 10-15%
- Marginal: 5-10% (vulnerable to cost increases or competition)
- <5%: unsustainable; requires immediate cost reduction or price increase

**Data Source**:
- Requires comprehensive P&L combining platform data, COGS, and operational costs
- Tools: Sellerboard, Inventory Lab, or custom spreadsheet

**Actionable Insight**: Net margin is the North Star of the KPI hierarchy for a
reason. Revenue growth at declining margins is a trap. Calculate net margin per
SKU monthly. Kill or fix any SKU with negative net margin unless it serves a
documented strategic purpose (loss leader driving cross-sell, new launch in
investment phase with a defined timeline to profitability).

---

### Contribution Margin

**Definition**: Revenue minus variable costs (COGS, platform fees, advertising,
fulfillment, shipping) per unit or per SKU. Excludes fixed overhead. Used to
evaluate individual product profitability and make pricing/discontinuation
decisions.

**Formula**: `Contribution Margin = Selling Price - Variable Cost per Unit`

Or as a percentage: `CM% = ((Selling Price - Variable Cost) / Selling Price) x 100`

**Benchmark Range**:
- Target: >$5 per unit AND >25% for most products
- Low contribution margin acceptable only for high-volume, low-touch products
- Below $3 per unit: difficult to sustain with any advertising spend

**Data Source**:
- Calculated: selling price minus (COGS + FBA fees + referral fee + ad cost per
  unit + return cost allocation)

**Actionable Insight**: Contribution margin per unit is the best metric for
portfolio decisions. Rank all SKUs by contribution margin. The bottom 20% are
candidates for price increase, cost reduction, or discontinuation. Use
contribution margin (not gross margin) to set break-even ACOS targets:
`Break-even ACOS = Contribution Margin % (before ad cost)`.

---

### Customer Lifetime Value (CLTV)

**Definition**: The total revenue or profit a business can expect from a single
customer account over the duration of the relationship. Critical for DTC and
subscription businesses; harder to track on marketplace platforms.

**Formula**: `CLTV = Average Order Value x Purchase Frequency x Customer Lifespan`

Or profit-based: `CLTV = (AOV x Purchase Frequency x Customer Lifespan) x Profit Margin`

**Benchmark Range**:
- DTC / Shopify: target CLTV > 3x Customer Acquisition Cost (CAC)
- Amazon Subscribe & Save: 3-12 months average subscription duration
- Marketplace sellers: limited customer data makes CLTV approximation necessary
  (use repeat purchase rate as a proxy)

**Data Source**:
- Shopify: Analytics > Reports > Returning customer rate; Cohort analysis
- Amazon: Brand Analytics > Repeat Purchase Behavior (limited)
- DTC stores: CRM / email platform data

**Actionable Insight**: On marketplaces, you cannot directly market to past
customers, so CLTV is driven by product quality, review rating, and brand
recognition (shoppers who remember your brand search for it directly). For DTC,
CLTV justifies higher acquisition costs: if CLTV is $150, spending $40 to
acquire a customer is profitable. Increase CLTV through email sequences,
loyalty programs, complementary product recommendations, and subscription
options.

---

## SEO Metrics

### Organic Rank

**Definition**: The position of a product listing in non-paid (organic) search
results for a specific keyword. The primary measure of SEO success on
marketplace platforms.

**Formula**: Position number in search results (1 = first result)

**Benchmark Range**:
- Page 1 (positions 1-48 on Amazon): captures >70% of clicks
- Top 10: captures the majority of first-page clicks
- Position 1-3: highest CTR and conversion
- Page 2+: minimal visibility and traffic

**Data Source**:
- Amazon: third-party tools (Helium 10, Jungle Scout, DataDive) or manual search
- Brand Analytics: Search Query Performance shows impression share (proxy for rank)
- Walmart: Walmart API or third-party rank trackers

**Actionable Insight**: Track organic rank for the top 5 revenue-driving
keywords per ASIN weekly. Rank drops of >5 positions warrant investigation
(see Sales Drop Diagnostic Framework in SKILL.md). Rank is primarily driven
by sales velocity, relevance, and conversion rate. PPC investment on a keyword
can indirectly boost organic rank by increasing sales velocity for that keyword.

---

### Keyword Position

**Definition**: The specific ranking position of a listing for an individual
search keyword, tracked over time. While organic rank is a snapshot, keyword
position tracking monitors the trend.

**Formula**: Position number for a specific keyword at a specific point in time

**Benchmark Range**: Same as organic rank. Focus on trend direction:
- Improving: gaining 1-3 positions per week is healthy growth
- Stable: holding position within +/- 3 spots
- Declining: losing >5 positions in a week requires action

**Data Source**:
- Third-party keyword trackers (Helium 10, Jungle Scout, DataDive, KeywordSpy)
- Amazon Brand Analytics: Search Query Performance > impression rank

**Actionable Insight**: Track 10-20 keywords per ASIN: the top 5 by revenue
contribution and 5-15 secondary or emerging keywords. Plot weekly position on
a chart. Correlate position changes with actions taken (listing edits, PPC
changes, promotions) to understand what moves the needle. If a keyword position
is stuck despite high ad spend, the listing may have a relevance problem for
that keyword (check that the keyword appears in title and backend search terms).

---

### Share of Voice

**Definition**: The percentage of total impressions, clicks, or purchases
within a category or keyword set that are captured by your brand. A competitive
positioning metric available through Amazon Brand Analytics.

**Formula**: `Share of Voice = (Your Brand's Impressions or Clicks / Total Category Impressions or Clicks) x 100`

**Benchmark Range**:
- Category leader: >15% click share
- Strong contender: 5-15% click share
- Niche player: 1-5% click share
- Emerging brand: <1% click share
- Track trend: growth of 0.5-1% per month is strong progress

**Data Source**:
- Amazon: Brand Analytics > Search Query Performance (click share, purchase share)
- Amazon: Brand Analytics > Market Basket Analysis (related purchase data)
- Third-party tools: Similarweb, SEMrush (for DTC sites)

**Actionable Insight**: Share of Voice is the best single metric for
competitive positioning. If your click share is growing while a competitor's is
declining, you are winning the category even if both are growing in absolute
terms. Use Search Query Performance to identify keywords where you have high
impression share but low click share (CTR problem) or high click share but low
purchase share (conversion problem). Focus optimization efforts on the highest-
volume keywords where you underperform on click-to-purchase conversion.

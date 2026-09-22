# Trend Discovery and Demand Validation Sources

A comprehensive guide to tools and platforms for discovering product
opportunities and validating demand signals. Each source is documented with
step-by-step usage, data interpretation, limitations, and cost.

**Rule**: Never rely on a single source. Cross-validate every signal with at
least 2 independent sources before advancing a product through the validation
workflow.

## Table of Contents

- [1. Google Trends](#1-google-trends)
- [2. Amazon Best Sellers and BSR Analysis](#2-amazon-best-sellers-and-bsr-analysis)
- [3. 1688.com Hot Lists](#3-1688com-hot-lists)
- [4. TikTok Creative Center](#4-tiktok-creative-center)
- [5. Jungle Scout and Helium 10](#5-jungle-scout-and-helium-10)
- [6. Keepa](#6-keepa)
- [7. Shopee Trending and Keyword Tools](#7-shopee-trending-and-keyword-tools)
- [8. Social Media Signals](#8-social-media-signals)
- [9. AliExpress Trending](#9-aliexpress-trending)
- [10. Industry Trade Shows and Supplier Catalogs](#10-industry-trade-shows-and-supplier-catalogs)
- [Source Comparison Matrix](#source-comparison-matrix)
- [Workflow: Combining Sources](#workflow-combining-sources)

---

## 1. Google Trends

**What it provides**: Relative search interest over time for any keyword,
broken down by geography, time period, and related queries. Not absolute volume
but directional trend data.

**Cost**: Free.

**URL**: https://trends.google.com

### Step-by-Step Usage

1. **Enter the product keyword** in the search bar. Use the generic product
   term, not a brand name (e.g., "portable blender" not "BlendJet").
2. **Set the time range**:
   - Use **12 months** for current trend direction (is it growing or
     declining right now?)
   - Use **5 years** for seasonal pattern analysis (does it spike every
     December? every summer?)
   - Use **30 days** for detecting short-term viral spikes (TikTok effect)
3. **Set the geography** to your target market. Select the specific country,
   not "Worldwide" (demand patterns differ dramatically by market).
4. **Check "Related queries"** at the bottom of the page:
   - **Top queries**: shows what people also search for (identifies the
     product ecosystem and potential bundles)
   - **Rising queries**: shows queries with the fastest growth rate
     (identifies emerging sub-niches before they saturate)
5. **Compare up to 4 keywords** to evaluate relative demand between product
   candidates. Use this to prioritize your shortlist.
6. **Check "Related topics"** to understand the broader category context and
   discover adjacent product opportunities.

### How to Interpret Signals

| Signal | Interpretation |
|---|---|
| Steady line at 50-100 over 12 months | Stable, established demand. Good. |
| Gradual upward slope over 12 months | Growing demand. Ideal entry timing. |
| Sharp spike in last 30 days | Likely viral/trend-driven. Dangerous for new sellers (too late to source). |
| Repeating peaks at same months yearly | Seasonal product. Factor into inventory and cash flow planning. |
| Declining slope over 12 months | Shrinking market. Avoid unless you have a strong contrarian thesis. |
| Flat line near 0 | Extremely low search interest. Either the keyword is wrong or demand does not exist. |

### Limitations

- Google Trends shows **relative** interest, not absolute search volume. A
  score of 100 means the peak of that keyword's own history, not 100 searches.
- It reflects Google search behavior, not platform-specific behavior. People
  searching on Google may not buy on Amazon/Shopee.
- Very niche products may show "not enough data" even if they have viable
  demand on specific platforms.
- Does not show purchase intent. Someone searching "portable blender review"
  has different intent than "buy portable blender."
- Regional data can be sparse for smaller countries.

---

## 2. Amazon Best Sellers and BSR Analysis

**What it provides**: Real-time ranking of products by sales velocity within
each category and subcategory. BSR (Best Sellers Rank) is the single most
reliable proxy for actual sales volume on Amazon.

**Cost**: Free to browse. Tools for BSR-to-sales estimation cost $30-$100/month.

**URL**: https://www.amazon.com/bestsellers (adjust domain for target market:
.co.uk, .de, .co.jp, etc.)

### Step-by-Step Usage

1. **Navigate to the Best Sellers page** for your target Amazon marketplace.
2. **Drill into the relevant category** and subcategory. Best Sellers are
   hierarchical: "Home & Kitchen" > "Kitchen & Dining" > "Blenders" >
   "Personal Size Blenders."
3. **Record the BSR** of the top 10 products in your target subcategory. This
   is found on each product's listing page under "Product Information" or
   "Additional Information."
4. **Estimate monthly sales** from BSR using these approximate benchmarks for
   Amazon US (main category BSR):
   - BSR 1-500: 1,000+ units/month
   - BSR 500-2,000: 300-1,000 units/month
   - BSR 2,000-5,000: 100-300 units/month
   - BSR 5,000-15,000: 30-100 units/month
   - BSR 15,000-50,000: 10-30 units/month
   - BSR 50,000+: <10 units/month
   Note: These are rough estimates. Actual conversion varies by category.
   Use Jungle Scout or Helium 10 for more precise estimates.
5. **Check "Movers and Shakers"** (also on the Best Sellers page): products
   whose BSR improved the most in the last 24 hours. This reveals sudden
   demand surges.
6. **Check "New Releases"** and "Most Wished For" for demand signals on
   emerging products not yet reflected in BSR.
7. **Review the "Hot New Releases"** to see recently launched products that
   are gaining traction quickly (potential validation of new niche demand).

### How to Interpret Signals

| Signal | Interpretation |
|---|---|
| Multiple top-10 products with BSR < 5,000 | High-demand subcategory. Validates market size. |
| Top seller BSR < 1,000 but #10 is BSR > 50,000 | Winner-take-all market. Risky for new entrants. |
| BSR of top products improving over 90 days | Growing category. Good timing. |
| BSR of top products worsening over 90 days | Declining category. Caution. |
| Many products with similar BSR in top 20 | Distributed demand. Healthier competitive dynamics. |
| New product (< 6 months) with BSR < 5,000 | Market is accepting new entrants. Positive signal. |

### Limitations

- BSR is a point-in-time snapshot. It fluctuates throughout the day based on
  recent sales velocity. Always check BSR over time using Keepa.
- BSR is relative within a category, not across categories. BSR 1,000 in
  "Patio, Lawn & Garden" is very different from BSR 1,000 in "Cell Phones &
  Accessories."
- BSR-to-sales conversion varies by category, marketplace, and season. The
  estimates above are directional, not precise.
- Amazon does not publish BSR methodology. Rank is influenced by recency of
  sales (recent sales weigh more).
- Some products have artificially low BSR due to promotional giveaways or
  deal days. Cross-reference with review velocity.

---

## 3. 1688.com Hot Lists

**What it provides**: Trending products from the largest B2B wholesale platform
in China. Shows what Chinese factories are producing in volume and what
domestic buyers (including cross-border sellers) are purchasing.

**Cost**: Free to browse. Registration (free) required for some features.

**URL**: https://www.1688.com

### Step-by-Step Usage

1. **Navigate to the "Hot Selling" (hot-selling/trending) sections** on the
   1688.com homepage. Look for sections labeled with trending icons or fire
   emojis indicating popular categories.
2. **Use the category navigation** to drill into your target product category.
   1688 categories roughly map to Amazon categories but with more granular
   manufacturing-oriented segmentation.
3. **Sort by "Most Orders"** (descending) within a category to see which
   products have the highest order volume from B2B buyers. High order count
   from other sellers is a strong signal that the product is selling well in
   end markets.
4. **Check the "Cross-Border Supply" section** specifically designed for export
   products. These products already have export packaging, compliance
   documentation, and cross-border logistics support.
5. **Analyze product listings** for each trending item:
   - Order count (total orders and recent 30-day orders)
   - Number of buyers (more buyers = broader demand, not one bulk order)
   - Price tiers (MOQ pricing structure reveals per-unit economics)
   - Supplier verification level (gold crown, verified, years in business)
6. **Use the built-in search** with product keywords in Chinese for more
   precise results. Use Google Translate or tools to convert your English
   keywords to Chinese equivalents.
7. **Check "Similar Products"** on any trending listing to discover variations
   and adjacent opportunities.

### How to Interpret Signals

| Signal | Interpretation |
|---|---|
| Product has 10,000+ total orders from 500+ buyers | Proven cross-border demand. Widely sourced by multiple sellers. |
| Recent 30-day orders are growing vs. total average | Rising demand trend. Good timing. |
| Many suppliers (50+) offering the same product | Commoditized product. Price competition is fierce. Differentiation is critical. |
| Few suppliers (< 5) offering the product | Either niche with real demand, or too new/untested. Cross-reference with Google Trends. |
| Product is in the "Cross-Border Supply" section | Already validated for export. Compliance and logistics are partially solved. |
| Prices dropping across suppliers over 3-6 months | Oversupply. Margin pressure is coming even if demand looks stable. |

### Limitations

- 1688.com is primarily in Chinese. Browser translation works but loses
  nuance. Critical specifications should be verified with the supplier
  directly.
- Order counts can be inflated. Some suppliers count sample orders and bulk
  orders equally.
- Trending on 1688 means Chinese sellers are buying it for resale. You are
  seeing the supply-side signal, not the consumer demand signal. A product
  may be trending on 1688 because sellers are stocking up for a trend that is
  already peaking on Amazon.
- Pricing shown is for domestic Chinese pricing. Export pricing, MOQ, and
  packaging for cross-border will differ.
- Supplier quality varies enormously. Trending status does not indicate
  quality.

---

## 4. TikTok Creative Center

**What it provides**: Trending hashtags, popular product-related videos,
ad performance data, and emerging product categories on TikTok. Useful for
spotting viral product trends early but requires careful interpretation.

**Cost**: Free.

**URL**: https://ads.tiktok.com/business/creativecenter

### Step-by-Step Usage

1. **Navigate to the Trending section** in TikTok Creative Center. Filter by
   your target country/region.
2. **Search for product-related hashtags** using your category keywords. For
   example, search "kitchen gadget" or "home organization" to find trending
   product content.
3. **Analyze trending hashtags** for your category:
   - View count trajectory (growing vs. peaked)
   - Number of videos using the hashtag (content creator interest)
   - When the trend started (if < 2 weeks ago, you are likely too late for
     physical products)
4. **Review "Top Ads"** section filtered by your product category:
   - Which products are advertisers spending money on? (Indicates proven
     demand.)
   - What creative formats are performing? (Informs your future listing
     video strategy.)
   - Which products appear repeatedly across different advertisers?
5. **Check "Trending Products"** under the commerce/shop section if available
   for your market. This shows actual TikTok Shop sales data.
6. **Analyze video engagement patterns**:
   - Videos with high save-to-like ratio indicate purchase intent (people
     save to buy later)
   - Videos with high share-to-like ratio indicate viral potential
   - Comments asking "where to buy?" or "link?" indicate unmet demand

### How to Interpret Signals

| Signal | Interpretation |
|---|---|
| Hashtag view count growing steadily over 30+ days | Sustained trend. Worth investigating further. |
| Hashtag spiked in last 7 days from near-zero | Viral moment. Likely too late for physical product sourcing. May still work for TikTok Shop dropshipping. |
| Multiple advertisers running ads for the same product type | Proven demand. Advertisers spend money on products that convert. |
| High save-to-like ratio on product videos | Purchase intent is high. People are bookmarking to buy. |
| Product appears in both TikTok trends and Google Trends growth | Cross-platform validation. Stronger signal than TikTok alone. |
| Trend is 3+ months old and still growing | Mature enough to be real demand, not just a fad. Investigate immediately. |

### Limitations

- **TikTok virality has a 2-6 week lifecycle for most products.** By the time
  you source from China and ship, the trend is likely dead. Only products
  with sustained multi-month trends are viable for physical product sourcing.
- TikTok Creative Center data is biased toward ad-friendly content, not
  organic search demand.
- Engagement metrics (likes, views) do not equal purchase intent. A product
  can be "interesting to watch" but not "worth buying."
- TikTok demographics skew young. Products targeting older demographics may
  not show up in TikTok trends at all.
- Data availability varies by market. Some countries have limited Creative
  Center data.
- TikTok Shop availability differs by region. Trending products may not be
  sellable on TikTok Shop in your target market.

---

## 5. Jungle Scout and Helium 10

**What they provide**: The two leading Amazon seller tools. They provide
keyword research, product research, competitor tracking, BSR-to-sales
estimates, review analysis, and market intelligence. These are the primary
data sources for Amazon-focused product validation.

**Cost**:
- Jungle Scout: $29-$84/month (Suite plan recommended for product research)
- Helium 10: $29-$79/month (Platinum plan recommended)

### Step-by-Step Usage (Jungle Scout)

1. **Product Database**: Filter Amazon's entire catalog by category, price
   range, BSR range, review count, revenue estimate, seller type, and more.
   Start with broad filters and narrow down.
   - Set price: $18-$55
   - Set estimated monthly revenue: $5,000+
   - Set review count: <500
   - Set BSR range: 1,000-30,000
   - These filters surface products with proven demand but manageable
     competition
2. **Keyword Scout**: Enter your product keyword to see monthly search volume,
   exact and broad match volume, trending direction, CPC (cost per click for
   PPC), and ease-of-ranking score.
3. **Product Tracker**: Add products to track their BSR, price, and revenue
   over time. Track the top 10 competitors for 30 days before committing to
   a product.
4. **Opportunity Finder**: Discover niches with high demand and low competition
   by analyzing keyword-level data across categories.
5. **Review Analysis**: Pull all reviews for a competitor product and use the
   AI analysis feature to identify common complaints and feature requests.

### Step-by-Step Usage (Helium 10)

1. **Black Box (Product Research)**: Similar to Jungle Scout Product Database.
   Filter by category, price, revenue, review count, BSR, and more. Key
   advantage: can filter by "number of images" and "listing quality" to find
   poorly-listed competitors.
2. **Magnet (Keyword Research)**: Enter a seed keyword. Get search volume,
   Magnet IQ Score (demand-to-competition ratio), competing products, word
   frequency, and related keywords.
3. **Cerebro (Reverse ASIN Lookup)**: Enter a competitor's ASIN to see every
   keyword they rank for, their position, and search volume. Reveals the
   full keyword universe for a product category.
4. **Xray (Chrome Extension)**: While browsing Amazon search results, click
   Xray to overlay revenue estimates, BSR, review count, and other data on
   every product on the page. Instant competitive landscape view.
5. **Market Tracker**: Define a market (set of keywords) and track total
   market size, top sellers, new entrants, and market share changes over
   time.
6. **Review Insights**: Analyze competitor reviews at scale with AI-powered
   sentiment analysis to identify improvement opportunities.

### How to Interpret Data

| Metric | Good Signal | Bad Signal |
|---|---|---|
| Monthly search volume (primary keyword) | 3,000+ with growth trend | Under 1,000 or declining |
| Estimated monthly revenue (top 10 avg) | $10,000+ per seller | Under $3,000 per seller |
| Average review count (page 1) | 50-500 | Over 2,000 (moat too deep) |
| Number of sellers on page 1 with < 50 reviews | 3+ sellers | 0 (established players only) |
| Magnet IQ Score / Opportunity Score | Above 5 | Below 2 |
| Listing Quality Score (Black Box) | Low (opportunity to outperform) | High across all top sellers |

### Limitations

- Revenue estimates are estimates, not actual data. They can be off by
  30-50% in either direction. Use them for relative comparison, not absolute
  planning.
- Both tools sample data and extrapolate. Actual numbers may differ.
- Historical data accuracy degrades beyond 12 months.
- Neither tool tracks off-Amazon demand. A product may have significant
  Shopee/TikTok Shop volume that these tools miss.
- Tools are optimized for Amazon US. Data quality for other marketplaces
  (EU, Japan, Australia) is lower.
- Subscription cost adds up. Choose one tool initially and add the second
  only when your product research volume justifies it.

---

## 6. Keepa

**What it provides**: Complete price history, BSR history, deal history,
and buy box tracking for every product on Amazon. The most reliable source
for understanding how a product's performance has changed over time.

**Cost**: Free for basic charts. Keepa Data Access subscription: ~$20/month
for full historical data and API access.

**URL**: https://keepa.com (also available as a Chrome/Firefox extension)

### Step-by-Step Usage

1. **Install the Keepa browser extension**. It embeds price and BSR history
   charts directly into Amazon product pages.
2. **Read the price history chart** on any product page:
   - Amazon price (orange line): when Amazon itself sells the product
   - Marketplace new price (blue line): third-party seller price
   - Used price (black line): used seller price
   - Identify price stability, drops, and promotional patterns
3. **Read the BSR history chart** (toggle "Sales Rank" in the chart):
   - Consistent low BSR = consistent sales
   - Wildly fluctuating BSR = inconsistent demand
   - Gradually improving BSR = growing demand
   - BSR that was good but is now worsening = declining demand
4. **Use Keepa Product Finder** (paid feature) to search for products by BSR
   range, price range, category, and more. Similar to Jungle Scout's Product
   Database but with Keepa's superior historical data.
5. **Set Keepa price drop alerts** for competitor products to monitor
   promotional activity and pricing trends in your target category.
6. **Export data** for detailed analysis. Keepa allows CSV export of price
   and BSR history for spreadsheet modeling.
7. **Check the "Data" tab** on Keepa's product page for:
   - Number of sellers over time (competitive density changes)
   - Buy box ownership history (who controls the listing)
   - Review count growth over time (review velocity)
   - "Frequently bought together" and "Customers also bought"

### How to Spot Opportunity Windows

| Pattern | Opportunity |
|---|---|
| BSR improving but price has not increased | Demand growing; current sellers not capitalizing on pricing power. Room for premium positioning. |
| Price dropped but BSR did not improve | Price reduction did not stimulate demand. Market is price-insensitive. Compete on value, not price. |
| Seasonal BSR pattern with predictable peaks | Plan inventory and ad spend around the peaks. Launch 2-3 months before the seasonal rise. |
| New product entered and rapidly achieved low BSR | Market is accepting new entrants. Demand exceeds current supply. |
| Multiple sellers' prices converging downward | Price war in progress. Wait for it to stabilize or differentiate significantly. |
| BSR spiked after a deal/coupon and then returned to baseline | Organic demand is lower than the deal-inflated BSR suggests. Use baseline BSR for your estimates, not the spike. |

### Limitations

- Keepa only tracks Amazon. No data for Shopee, TikTok Shop, or other
  platforms.
- The free version shows limited history (90 days). The paid version is
  essentially required for serious product research.
- BSR data is sampled periodically, not real-time. Short-lived BSR spikes
  may be missed.
- Keepa does not estimate revenue or units sold. You need to combine Keepa
  BSR data with Jungle Scout or Helium 10 sales estimates.
- Historical data for newer marketplaces (Amazon Australia, Amazon Singapore)
  may be sparse.

---

## 7. Shopee Trending and Keyword Tools

**What it provides**: Trending products, keyword search volumes, and
competitive intelligence for Shopee, the dominant marketplace in Southeast Asia
and Taiwan.

**Cost**: Shopee Seller Center is free. Third-party tools ($20-$60/month).

**URLs**:
- Shopee Seller Center: https://seller.shopee.com (country-specific)
- Shopee Market Insights (built-in): accessible within Seller Center

### Step-by-Step Usage

1. **Shopee Market Insights** (within Seller Center):
   - Navigate to "Market Insights" or "Business Insights" in your Seller
     Center dashboard
   - View trending keywords in your registered categories
   - Check keyword search volume, click-through rate, and conversion rate
   - Monitor top-performing products in each subcategory
2. **Shopee Trending page**:
   - Browse the platform's homepage trending sections
   - Check "Flash Sale" and "Daily Discover" for products with high
     engagement
   - Note products that appear repeatedly in recommendations (algorithm
     signals sustained demand)
3. **Shopee keyword search suggestions**:
   - Type your product keyword into Shopee search and note the auto-
     complete suggestions (these reflect actual user searches)
   - Compare suggestions across different Shopee country sites to assess
     cross-border demand
4. **Third-party Shopee analytics tools** (e.g., Kalodata, ShopeeScout):
   - Estimate competitor sales volumes
   - Track product performance over time
   - Identify trending categories and products
   - Analyze pricing and promotional patterns
5. **Competitor analysis**:
   - Find top sellers in your target subcategory
   - Check their sales count (shown on Shopee listings)
   - Analyze their product range and pricing strategy
   - Review their customer feedback for quality signals

### How to Interpret Signals

| Signal | Interpretation |
|---|---|
| Keyword search volume 5,000+/month on Shopee | Sufficient demand for a Shopee-focused launch |
| Product has 500+ sold/month from multiple sellers | Validated demand with multiple successful sellers |
| Flash sale appearances are frequent | Platform is promoting this category (good for visibility) |
| Price range is very tight ($1-2 spread) | Highly competitive on price. Margins will be thin. |
| Top sellers have 10K+ followers | Established sellers with loyal audiences. Harder to compete. |
| Same product trending in 3+ Shopee country sites | Cross-border demand validated. Can sell to multiple markets. |

### Limitations

- Shopee's internal analytics tools are basic compared to Amazon's ecosystem.
  Third-party tools are less mature.
- Sales counts shown on Shopee listings include promotional and discounted
  units, inflating perceived organic demand.
- Shopee's algorithm heavily promotes low-price items. Margins are generally
  thinner than Amazon.
- Data quality and tool availability vary by country. Shopee Singapore,
  Thailand, and Vietnam have different data accessibility.
- Shopee's competitive dynamics are different from Amazon: platform promotions,
  vouchers, and live streaming are much more influential.
- Shopee policies and fee structures change frequently. Verify current fee
  schedules before margin calculations.

---

## 8. Social Media Signals

**What it provides**: Early indicators of consumer interest, emerging
aesthetic trends, and niche community demand. Social media signals are leading
indicators that precede search volume and platform sales data.

**Cost**: Free for organic research. Paid analytics tools optional ($10-$50/month).

### Pinterest Trends

**URL**: https://trends.pinterest.com

1. **Search for product-related keywords** on Pinterest Trends. Pinterest
   users are planners: they pin products they intend to buy weeks or months
   later.
2. **Analyze the trend graph**: Pinterest Trends shows 12-month search
   interest similar to Google Trends but for a demographic that skews toward
   purchase intent.
3. **Check "Related Trends"** for adjacent product ideas.
4. **Key insight**: Pinterest trends often lead Amazon trends by 4-8 weeks.
   A rising Pinterest trend for a product category that has not yet shown
   up on Amazon BSR charts is an early-mover opportunity.

### Instagram and Influencer Signals

1. **Search product-related hashtags** on Instagram. Check post count and
   recent post velocity.
2. **Identify micro-influencers** (10K-100K followers) posting about your
   product category. If multiple micro-influencers are organically featuring
   a product type (not paid posts), this indicates genuine consumer interest.
3. **Check Instagram Shopping tags**: products being tagged in shopping posts
   have direct purchase intent.
4. **Monitor Reels** for product demonstration videos with high engagement
   (especially save and share counts).

### Reddit Niche Communities

1. **Search for your product category** on Reddit. Find relevant subreddits
   (e.g., r/BuyItForLife, r/shutupandtakemymoney, r/coolkitchengadgets).
2. **Analyze product recommendation threads**: what products do real users
   recommend? What complaints do they have about existing products?
3. **Check "What should I buy?" threads**: direct consumer demand signals
   with detailed use-case context.
4. **Monitor new product posts**: upvote counts and comment sentiment reveal
   genuine consumer interest (Reddit is harder to manipulate than other
   platforms).

### How to Interpret Signals

| Signal | Interpretation |
|---|---|
| Pinterest trend rising for 4+ weeks | Early demand signal. Investigate immediately for first-mover potential. |
| Multiple Instagram micro-influencers featuring product organically | Genuine interest. Not a paid campaign. Sustained demand likely. |
| Reddit threads asking "where to buy X" with no good answer | Unmet demand. Supply gap. Opportunity. |
| High Pinterest pin count but no Amazon equivalent | Product may be aspirational, not purchasable online. Verify with BSR data. |
| Reddit complaints about all existing options in a category | Differentiation opportunity. Build the product they wish existed. |

### Limitations

- Social media signals are qualitative and directional. They do not provide
  sales volume estimates.
- Social media demographics are biased. Pinterest skews female and older
  millennial. Instagram skews younger. Reddit skews male and tech-oriented.
- Engagement does not equal purchase intent. A viral product image may get
  likes from people who would never buy it.
- Influencer posts may be paid without clear disclosure. Organic vs. sponsored
  content is difficult to distinguish.
- Social media trends move much faster than physical product supply chains.
  Timing is critical.

---

## 9. AliExpress Trending

**What it provides**: Demand signals from the world's largest cross-border
retail platform targeting end consumers. AliExpress trending products indicate
what global consumers are actively buying from China-based sellers. Useful as
a demand indicator even if you are not selling on AliExpress.

**Cost**: Free.

**URL**: https://www.aliexpress.com (check "Trending" and "Best Sellers" sections)

### Step-by-Step Usage

1. **Browse the "Super Deals" and "Best Sellers" pages** on AliExpress. These
   surfaces show products with the highest recent sales velocity.
2. **Check "Weekly Deals" and category-specific trending** sections for
   products gaining momentum.
3. **Search your product keyword** and sort by "Orders" (descending) to see
   which products have the highest order counts.
4. **Analyze the dropshipper signal**:
   - Products with extremely high order counts on AliExpress (10,000+) are
     likely being dropshipped to Amazon, Shopee, eBay, and independent
     stores
   - This validates consumer demand but also signals competition is
     coming or already present
   - High AliExpress orders + low Amazon presence = potential opportunity
     for an Amazon private label version with better quality and branding
5. **Check product reviews on AliExpress** for quality signals. AliExpress
   reviews from actual consumers reveal product strengths and weaknesses that
   you can improve upon.
6. **Monitor new product launches** with rapidly growing order counts (0 to
   500+ orders in under 30 days indicates strong initial demand).

### How to Interpret Signals

| Signal | Interpretation |
|---|---|
| Product has 10K+ orders on AliExpress | Proven global demand. Dropshippers are actively selling it. |
| High AliExpress orders but low Amazon BSR | Market gap. Amazon consumers want it but supply has not caught up. Opportunity for branded version. |
| AliExpress price is $3-8 for a product selling at $25+ on Amazon | Large margin opportunity for private labeling with quality improvements. |
| Product has 4.0+ rating with specific quality complaints | Room for a differentiated version that fixes those complaints. |
| Rapidly growing orders on a product < 90 days old | Emerging trend. Cross-validate with Google Trends and TikTok. |
| Product is trending on AliExpress AND Shopee AND TikTok | Strong multi-platform demand signal. Higher confidence in sustained trend. |

### Limitations

- AliExpress order counts are cumulative (all-time), not monthly. A product
  with 50,000 orders may have peaked 2 years ago and now sells 10/month.
- AliExpress products are typically the cheapest version with the lowest
  quality. Consumer expectations on Amazon/Shopee are higher.
- Dropshipper-driven demand can collapse quickly when dropshippers move to
  the next trending product.
- AliExpress pricing does not reflect what consumers will pay on Amazon. The
  margin between AliExpress retail and Amazon retail is the opportunity, but
  verify willingness to pay.
- Some high-order products have inflated counts from promotional giveaways
  or fake orders.

---

## 10. Industry Trade Shows and Supplier Catalogs

**What it provides**: Direct access to new product innovations, manufacturing
capabilities, and industry trends from the source. Trade shows are where new
products debut before they reach consumer platforms.

**Cost**: Varies. Many trade shows are free for buyers. Travel costs are the
main expense.

### Major Trade Shows for Cross-Border E-Commerce

| Trade Show | Location | Focus | When | Best For |
|---|---|---|---|---|
| Canton Fair (China Import and Export Fair) | Guangzhou, China | All categories | April and October | Broadest product discovery; 25,000+ exhibitors |
| Global Sources Trade Shows | Hong Kong | Electronics, fashion, home | April and October | Curated supplier selection; quality focus |
| Yiwu International Trade Fair | Yiwu, China | Small commodities | October | Low-MOQ products; gift/novelty items |
| CES (Consumer Electronics Show) | Las Vegas, USA | Electronics, tech | January | Emerging consumer tech trends |
| Amazon Accelerate | Seattle, USA | Amazon-specific | September | Amazon seller tools, strategies, trends |
| ASD Market Week | Las Vegas, USA | General merchandise | March and August | Budget-friendly product discovery |

### Step-by-Step Usage

1. **Pre-show research**:
   - Review the exhibitor list before attending. Identify suppliers in your
     target categories.
   - Prepare a list of products you are evaluating with specific questions
     about MOQ, pricing, customization, and certifications.
   - Set up meetings with target suppliers in advance for priority attention.
2. **At the show**:
   - Focus on new product sections and innovation showcases.
   - Photograph products, collect catalogs, and take supplier contact cards.
   - Ask about cross-border e-commerce experience (shipping, compliance,
     labeling).
   - Request samples and pricing for products that pass your initial filter.
   - Note which products have the most buyer traffic at booths (crowd signal).
3. **Post-show validation**:
   - Run every interesting product through the Quick-Kill Criteria before
     investing further time.
   - Cross-reference trade show discoveries with Google Trends and Amazon
     BSR data.
   - Request formal quotations with MOQ, pricing tiers, lead times, and
     sample costs.
4. **Supplier catalogs** (virtual alternative):
   - Request digital catalogs from suppliers on 1688.com and Alibaba.
   - Many suppliers publish new product catalogs quarterly.
   - Compare catalog new-arrivals across multiple suppliers to identify
     manufacturing trends (if 5+ suppliers are all launching similar new
     products, there is likely demand driving it).

### How to Interpret Signals

| Signal | Interpretation |
|---|---|
| New product category appearing across multiple supplier booths | Industry is gearing up for demand. Leading indicator. |
| Supplier highlights "Amazon Best Seller" in their booth | Product is already validated but competition will be high. |
| Product is new at trade show but not yet on Amazon | First-mover opportunity. Validate demand before committing. |
| Supplier offers turnkey private label (branding, packaging, compliance) | Lower barrier to entry for cross-border sellers. Reduces launch timeline. |
| Heavy buyer traffic at a specific product booth | Crowd wisdom. Many sellers see opportunity. Also means competition is forming. |

### Limitations

- Trade shows require travel, time, and planning. Not practical for
  continuous monitoring.
- Exhibitors showcase their best products; quality of regular production may
  differ.
- Trade shows are lagging indicators for some categories (products debut at
  shows after already proving demand).
- Virtual alternatives (online supplier catalogs, Alibaba live events) have
  lower discovery quality than in-person events.
- Language barriers at Chinese trade shows can limit information gathering.
  Consider hiring a translator or bringing a bilingual partner.

---

## Source Comparison Matrix

| Source | Data Type | Cost | Best For | Update Frequency | Reliability |
|---|---|---|---|---|---|
| Google Trends | Search interest trends | Free | Trend direction, seasonality, geographic demand | Real-time | High for direction, low for absolute volume |
| Amazon BSR | Sales velocity ranking | Free (tools $30-100/mo) | Demand validation, competitor analysis | Real-time (hourly fluctuation) | High |
| 1688.com | Supplier/manufacturing trends | Free | Supply-side signals, COGS estimation | Daily | Medium (inflated order counts) |
| TikTok Creative Center | Viral product trends | Free | Early trend detection, content strategy | Daily | Low (short lifecycle) |
| Jungle Scout / Helium 10 | Comprehensive Amazon data | $29-84/mo | Full product research workflow | Daily | Medium-High (estimates vary) |
| Keepa | Price and BSR history | Free-$20/mo | Historical analysis, trend validation | Hourly sampling | High |
| Shopee Tools | SE Asia marketplace data | Free-$60/mo | Shopee-specific research | Daily | Medium |
| Social Media | Consumer interest signals | Free-$50/mo | Early trend detection, niche discovery | Real-time | Low-Medium (qualitative) |
| AliExpress | Dropshipper demand signals | Free | Cross-border demand validation, margin analysis | Daily | Medium (cumulative counts) |
| Trade Shows | New product discovery | Varies (travel) | Innovation scouting, supplier relationships | Biannual | Medium-High (curated) |

---

## Workflow: Combining Sources

Use this workflow to cross-validate signals and build conviction in a product
opportunity.

### Step 1: Initial Discovery (cast a wide net)

Use 2-3 discovery sources to generate ideas:
- Google Trends (rising queries in target categories)
- 1688.com hot lists (what suppliers are pushing)
- Social media signals (Pinterest trends, TikTok Creative Center)
- AliExpress trending (what consumers are buying globally)

### Step 2: Demand Validation (narrow down)

For each interesting product, validate demand on the target platform:
- Amazon: Jungle Scout or Helium 10 for search volume and BSR
- Shopee: Shopee Market Insights or third-party tools
- Cross-platform: Google Trends for sustained interest confirmation

### Step 3: Historical Verification (avoid traps)

Before committing, check the timeline:
- Keepa: BSR history over 12 months (is this growing, stable, or dying?)
- Google Trends 5-year view: is this a seasonal spike or sustained demand?
- AliExpress order velocity: is growth recent or has it plateaued?

### Step 4: Competitive Assessment (can you win?)

Evaluate whether you can realistically capture market share:
- Helium 10 Xray or Jungle Scout: review counts, listing quality, price
  range of page-1 sellers
- Keepa: price history of competitors (are they in a price war?)
- 1688.com: supplier density and pricing (can you get competitive COGS?)

### Step 5: Score and Decide

Feed all collected data into the 30-point validation scorecard
(`references/validation-checklist.md`). Let the scorecard make the decision,
not your gut.

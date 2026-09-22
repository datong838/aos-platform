# Social Media Advertising Guide for E-Commerce

A comprehensive reference for running social media ad campaigns across major
platforms to drive traffic and sales for cross-border e-commerce products.

---

## Table of Contents

1. [Meta Ads (Facebook + Instagram)](#meta-ads-facebook--instagram)
2. [TikTok Ads](#tiktok-ads)
3. [Google Shopping](#google-shopping)
4. [Pinterest Ads](#pinterest-ads)
5. [Budget Allocation Across Social Channels](#budget-allocation-across-social-channels)
6. [Attribution and Tracking Setup](#attribution-and-tracking-setup)
7. [Creative Best Practices](#creative-best-practices)
8. [Retargeting Strategies](#retargeting-strategies)
9. [Scaling Social Ads](#scaling-social-ads)

---

## Meta Ads (Facebook + Instagram)

Meta remains the largest social advertising platform for e-commerce, offering
deep audience targeting, robust product catalog integration, and extensive
reach across Facebook, Instagram, Messenger, and the Audience Network.

### Campaign Objectives for E-Commerce

| Objective | When to Use | Expected Outcome |
|---|---|---|
| **Sales (Conversions)** | Primary objective for direct-response campaigns driving purchases | Optimized for purchase events; highest ROAS |
| **Traffic** | Driving visitors to a listing or storefront when pixel data is limited | Volume of link clicks; lower quality than conversion-optimized |
| **Engagement** | Building social proof on posts before using them as ads | Likes, comments, shares; not directly tied to revenue |
| **Awareness** | Upper-funnel brand building with broad reach | Impressions and reach; use only with established brand budgets |

**Default recommendation:** Always start with the Sales objective optimizing for
Purchase events. Only use Traffic if you have fewer than 50 conversions per week
(Meta needs data volume to optimize for conversions).

### Audience Targeting

**Core Audiences (Interest and Demographic Targeting):**
- Layer interests related to your product category
- Narrow by demographics (age, gender, location, language)
- Exclude existing customers when acquiring new ones
- Start with audience sizes of 1-5 million for US market
- Test 2-3 distinct interest clusters per campaign

**Custom Audiences (Your Own Data):**

| Source | Use Case | Retention Window |
|---|---|---|
| Website visitors (pixel) | Retargeting shoppers who viewed products | 7, 14, 30, 60, 180 days |
| Customer list (email/phone) | Targeting existing customers for repeat purchase or cross-sell | Upload list; match rate varies |
| Video viewers | Retargeting people who watched your video ads | 3s, 10s, 25%, 50%, 75%, 95% thresholds |
| Instagram/Facebook engagers | Retargeting people who interacted with your profile or ads | 30, 60, 90, 365 days |

**Lookalike Audiences:**
- Build from your best Custom Audience (purchasers > add-to-cart > website visitors)
- Start with 1% Lookalike (most similar to source audience)
- Test 1%, 2-3%, and 5% Lookalikes to find volume/quality balance
- Minimum source audience size: 100 people (1,000+ recommended)
- Refresh source audiences monthly with new customer data

### Creative Formats

| Format | Best For | Specifications |
|---|---|---|
| Single Image | Simple product showcase, testimonials | 1080x1080 (square) or 1080x1350 (4:5 portrait) |
| Carousel | Multiple products, feature highlights, step-by-step | 2-10 cards, 1080x1080 each |
| Single Video | Product demonstration, UGC-style content | 15-60 seconds, 1080x1350 or 9:16 vertical |
| Collection | Product catalog browsing experience | Cover image/video + product grid from catalog |
| Dynamic Product Ads | Retargeting with personalized product recommendations | Auto-generated from product catalog feed |

### Product Catalog Ads (Dynamic Ads)

Product catalog ads automatically show the right products to shoppers based on
their browsing behavior. Essential for retargeting at scale.

**Setup requirements:**
1. Create a Product Catalog in Commerce Manager
2. Upload product feed (CSV, XML, or API) with: ID, title, description, price,
   image URL, landing page URL, availability, brand, category
3. Install Meta Pixel on your website/storefront
4. Configure standard events: ViewContent, AddToCart, Purchase
5. Create Dynamic Ad campaigns using the catalog as the product source

**Feed optimization:**
- Titles: include primary keyword, brand, key feature (max 150 characters)
- Images: white background product shots for feed; lifestyle for ad overlays
- Prices: ensure accuracy; mismatched prices erode trust and violate policy
- Availability: sync inventory status to prevent advertising out-of-stock items
- Update feed at least daily

### Meta Pixel Setup

The Meta Pixel is critical for conversion tracking, audience building, and
campaign optimization. Without it, Meta cannot optimize for purchases.

**Standard events to implement:**

| Event | Trigger | Purpose |
|---|---|---|
| PageView | Every page load | Base tracking, audience building |
| ViewContent | Product page view | Product interest tracking, retargeting |
| AddToCart | Add to cart click | Purchase intent signal, retargeting |
| InitiateCheckout | Checkout start | High-intent retargeting |
| Purchase | Order confirmation | Conversion tracking, ROAS calculation |

**Implementation options:**
- Direct pixel code installation (for owned storefronts)
- Shopify/WooCommerce native integration
- Google Tag Manager container
- Conversions API (server-side) for improved accuracy post-iOS 14

**Important:** Amazon does not allow Meta Pixel installation on Amazon listings.
For Amazon sellers, use the Amazon Attribution program to track social media
traffic to Amazon listings, or drive traffic to a landing page (brand website
or Shopify) with the pixel installed before redirecting to Amazon.

---

## TikTok Ads

TikTok has rapidly become a major e-commerce advertising platform, particularly
effective for products with visual appeal, demonstration value, or trend
potential.

### Ad Formats

**Spark Ads (Recommended Starting Point)**

Boost existing organic TikTok posts (your own or creator content with
permission) as ads. These maintain the native feel and retain all engagement
(likes, comments, shares) on the original post.

- Best for: UGC-style content, creator collaborations, authentic feel
- Performance: typically higher engagement and lower CPM than standard in-feed ads
- Setup: authorize the organic post via Spark Ads code; run as ad with targeting

**In-Feed Ads**

Standard video ads that appear in the For You feed between organic content.

- Best for: polished brand content, direct-response campaigns
- Duration: 5-60 seconds (15-30 seconds optimal)
- Aspect ratio: 9:16 vertical (full screen)
- Sound on by default (unlike Meta); audio matters

**TopView**

Premium placement: first ad users see when opening TikTok. Full-screen video
up to 60 seconds.

- Best for: major product launches, seasonal campaigns, maximum awareness
- Cost: CPM-based, significantly higher than in-feed ($50-100+ CPM)
- Reach: massive but expensive; reserve for products with broad appeal

### TikTok Creative Best Practices

1. **Native first.** Content that looks like an ad performs poorly on TikTok.
   Content that looks like a regular TikTok post performs well. Shoot on a phone,
   not in a studio.

2. **Hook in 1-2 seconds.** TikTok scroll speed is faster than any other
   platform. Your first frame must stop the thumb. Start with a surprising
   visual, a question, or a bold claim.

3. **Show the product in use.** Demonstration content outperforms static product
   shots by 2-5x on TikTok. Show the product solving a problem, creating a
   transformation, or delivering a satisfying result.

4. **Use trending sounds.** TikTok's algorithm favors content using trending
   audio. Check the Creative Center for trending sounds and adapt them to your
   product content.

5. **Multiple creatives.** TikTok creative fatigue sets in faster than Meta. Plan
   for 3-5 creative variations per campaign and refresh every 7-14 days.

6. **UGC over polish.** User-generated content style (authentic, unscripted,
   real-person reactions) consistently outperforms professionally produced
   content on TikTok.

### TikTok Pixel

Similar to Meta Pixel, the TikTok Pixel tracks conversions and enables
optimization.

**Standard events:** PageView, ViewContent, AddToCart, PlaceAnOrder, CompletePayment.

**Implementation:** JavaScript pixel code or server-side Events API. Same
limitation applies for Amazon sellers: use landing pages with pixel or TikTok
Shop for direct integration.

### TikTok Shop Integration

TikTok Shop allows in-app purchasing directly from TikTok content. For cross-
border sellers with TikTok Shop access:
- Products listed directly within TikTok
- Shoppable videos and LIVE shopping
- Affiliate marketplace (creators earn commission promoting your products)
- Native checkout reduces friction vs. off-platform redirects
- Attribution is cleaner than sending traffic to external platforms

---

## Google Shopping

Google Shopping ads display product images, prices, and merchant names at the
top of Google search results. High intent traffic because shoppers are actively
searching.

### Product Feed Optimization

The product feed in Google Merchant Center determines which searches trigger
your Shopping ads and how your products appear.

**Critical feed attributes:**

| Attribute | Optimization Notes |
|---|---|
| **title** | Include primary keyword, brand, key attributes (color, size, material). Front-load the most important keyword. Max 150 characters; first 70 visible in results. |
| **description** | Keyword-rich, detailed product description. Include use cases and key features. Max 5,000 characters. |
| **product_type** | Your own category taxonomy. Be specific: "Home > Kitchen > Utensils > Silicone Spatulas" not just "Kitchen." |
| **google_product_category** | Google's taxonomy. Use the most specific category available. |
| **image_link** | High-quality white-background product image. Must be the actual product, no watermarks, no promotional text. |
| **price** | Must match the landing page price exactly. Currency must match the target country. |
| **availability** | Must accurately reflect stock status. Mismatches lead to disapprovals. |
| **gtin / mpn / brand** | Required for most products. GTINs (UPC/EAN) significantly improve matching. |
| **shipping** | Accurate shipping costs and delivery estimates. Free shipping improves CTR. |

### Smart Shopping / Performance Max Campaigns

Google has migrated Smart Shopping to Performance Max (PMax). PMax campaigns
use machine learning to optimize across all Google properties (Search, Shopping,
Display, YouTube, Discover, Gmail, Maps).

**Setup:**
1. Connect Google Merchant Center to Google Ads
2. Create a Performance Max campaign with Sales objective
3. Upload asset groups: images (landscape, square, portrait), logos, headlines
   (up to 5), long headlines (up to 5), descriptions (up to 5), videos (optional
   but recommended)
4. Set target ROAS or maximize conversion value bidding
5. Provide audience signals (your customer lists, website visitors, in-market
   audiences) as starting points for Google's algorithm

**Performance Max best practices:**
- Start with a target ROAS 20% below your actual target to give the algorithm
  room to learn (tighten after 2-4 weeks of data)
- Provide strong audience signals; the algorithm uses them as starting points
- Monitor search term insights report (limited but available) for relevance
- Separate branded and non-branded traffic into different campaigns when possible
- Allow 2-4 weeks of learning period before making major changes

### Standard Shopping Campaigns

For sellers who want more control than Performance Max provides.

**Structure:**
- Campaign level: budget, bidding strategy, location targeting
- Ad group level: product groups and bids
- Product group level: segment by brand, category, product type, custom label

**Bidding strategies:**
- Manual CPC: full control, best for experienced advertisers
- Maximize clicks: volume-focused, good for data collection
- Target ROAS: automated bidding toward a revenue target (needs 15+ conversions
  in 30 days)

---

## Pinterest Ads

Pinterest is a visual discovery platform where users actively plan purchases.
Purchase intent on Pinterest is higher than most social platforms, making it
effective for home decor, fashion, beauty, food, and lifestyle products.

### Shopping Pins

Shopping Pins connect your product catalog directly to buyable pins. When a user
sees a pin from your catalog, they can tap to view price, availability, and a
direct link to purchase.

**Setup:**
1. Create a Pinterest Business account
2. Claim your website (verify ownership)
3. Upload product catalog (feed similar to Google Merchant Center format)
4. Enable auto-generated Shopping Pins from catalog
5. Create collections and boards organized by product category

### Ad Formats

| Format | Best For | Specifications |
|---|---|---|
| Standard Pin | Product showcase, inspirational imagery | 1000x1500 (2:3 ratio) recommended |
| Video Pin | Product demonstration, how-to content | 2-60 seconds, vertical or square |
| Carousel Pin | Multiple product views, feature highlights | 2-5 cards, 1000x1500 each |
| Shopping Ad | Direct purchase from catalog | Auto-generated from product feed |
| Collection Ad | Curated product groupings | One hero image/video + 3 product images below |

### Audience Targeting

- **Keyword targeting:** Target searches (Pinterest is a visual search engine)
- **Interest targeting:** Based on user pin/board activity
- **Actalike audiences:** Pinterest's version of lookalikes (based on your
  customer list or website visitors)
- **Retargeting:** Website visitors, engagers, customer list matches
- **Demographics:** Age, gender, location, language, device

### Pinterest-Specific Tips

1. **Vertical images perform best.** The 2:3 ratio (1000x1500) takes up more
   screen space in the feed. Square and horizontal images get less engagement.
2. **Text overlay on images.** Add a concise benefit statement or call to action
   on the image itself. Pinterest users scan quickly.
3. **Seasonal planning is critical.** Pinterest users plan 2-3 months ahead.
   Start holiday campaigns in September, summer campaigns in March.
4. **Rich Pins.** Enable Rich Pins to automatically sync product info (price,
   availability) from your website to your pins.
5. **Long content lifespan.** Unlike Meta and TikTok where ad fatigue sets in
   within 1-2 weeks, Pinterest content has a longer shelf life (weeks to months).

---

## Budget Allocation Across Social Channels

### Starting Budget Allocation (Testing Phase)

When launching social ads for the first time, allocate budget for testing
across channels before committing to a single platform.

| Channel | Budget Share | Minimum Monthly Test Budget | Test Duration |
|---|---|---|---|
| Meta (Facebook/Instagram) | 40% | $500 | 2-4 weeks |
| Google Shopping | 30% | $400 | 2-4 weeks |
| TikTok | 20% | $300 | 2-3 weeks |
| Pinterest | 10% | $200 | 3-4 weeks |

### Post-Testing Reallocation

After the testing phase, reallocate based on actual performance data.

**Decision framework:**
1. Rank channels by ROAS (or CPA if using cost-per-acquisition targets)
2. Allocate 60% of budget to the top-performing channel
3. Allocate 25% to the second-best channel
4. Allocate 15% to testing (rotate between remaining channels and new creative
   formats)

### Channel Selection by Product Type

| Product Category | Primary Channel | Secondary Channel | Notes |
|---|---|---|---|
| Fashion / Apparel | Meta + TikTok | Pinterest | Visual products; UGC and try-on content performs well |
| Home / Kitchen | Meta + Pinterest | Google Shopping | Pinterest for inspiration; Google for intent |
| Electronics / Gadgets | Google Shopping + TikTok | Meta | Google for search intent; TikTok for demonstrations |
| Beauty / Skincare | TikTok + Meta | Pinterest | TikTok for transformations; Meta for retargeting |
| Fitness / Sports | TikTok + Meta | Google Shopping | Demo-heavy products; before/after content |
| Toys / Kids | Meta + Pinterest | Google Shopping | Parent targeting on Meta; seasonal on Pinterest |
| Pet Products | Meta + TikTok | Google Shopping | Pet content is highly shareable; emotional appeal |

---

## Attribution and Tracking Setup

### The Attribution Challenge

Social media advertising for e-commerce faces a fundamental attribution problem:
the ad click and the purchase often happen on different platforms, devices, and
days. Post-iOS 14 privacy changes have further complicated tracking.

### Attribution Models

| Model | Description | Best For |
|---|---|---|
| Last-click | Credit goes to the last touchpoint before purchase | Conservative measurement; undervalues awareness |
| First-click | Credit goes to the first touchpoint in the journey | Understanding customer acquisition channels |
| Linear | Equal credit to all touchpoints | Balanced view of multi-touch journeys |
| Time decay | More credit to touchpoints closer to conversion | Reasonable compromise for most e-commerce sellers |
| Platform-reported | Each platform claims credit for conversions in its window | Inflated; always cross-reference with actual revenue |

### Recommended Tracking Stack

1. **Platform pixels (Meta Pixel, TikTok Pixel, Pinterest Tag, Google Ads tag)**
   - Install all relevant pixels on your owned properties
   - Configure standard e-commerce events (ViewContent, AddToCart, Purchase)
   - Set up Conversions API (server-side) where available for improved accuracy

2. **UTM parameters on all ad links**
   - Format: `?utm_source=meta&utm_medium=paid&utm_campaign={campaign_name}&utm_content={ad_name}`
   - Use consistent naming conventions across all platforms
   - Track UTMs in Google Analytics or your analytics tool

3. **Amazon Attribution (for Amazon sellers)**
   - Create attribution tags for each social channel/campaign
   - Apply tags to landing page links that redirect to Amazon
   - Track clicks, detail page views, add-to-carts, and purchases on Amazon
   - Note: 14-day attribution window; data delayed 48-72 hours

4. **Google Analytics (GA4)**
   - Central source of truth for cross-channel performance
   - Compare platform-reported conversions against GA4 data
   - Use the Model Comparison tool to understand attribution across channels

### Attribution Reality Check

Platform-reported ROAS is almost always higher than actual ROAS because each
platform takes credit for overlapping conversions. A pragmatic approach:
- Track platform-reported ROAS for optimization decisions within each platform
- Track blended ROAS (total ad spend across all channels / total revenue) as the
  true business metric
- If blended ROAS is above target, the channel mix is working regardless of
  individual platform reporting

---

## Creative Best Practices

### Video vs Image Performance

Video consistently outperforms static images on engagement metrics across all
social platforms. However, the production investment differs.

| Format | CTR | CPM | Conversion Rate | Production Effort |
|---|---|---|---|---|
| Static image (product on white) | Baseline | Baseline | Baseline | Low |
| Lifestyle image | 1.2-1.5x | 1.0-1.2x | 1.1-1.3x | Medium |
| Product video (studio) | 1.5-2.0x | 0.8-1.2x | 1.2-1.5x | High |
| UGC video (creator) | 2.0-3.0x | 0.7-1.0x | 1.5-2.5x | Medium (creator cost) |
| UGC video (customer) | 1.8-2.5x | 0.7-1.0x | 1.5-2.0x | Low (seeding cost) |

### UGC (User-Generated Content) Style

UGC-style content consistently outperforms polished brand content on social
platforms because it feels authentic and matches the native content in the feed.

**Characteristics of effective UGC-style ads:**
- Shot on smartphone (not professional camera)
- Natural lighting, real environments (not studio)
- Real person talking to camera or demonstrating product
- Conversational tone, not scripted-sounding
- Raw editing (minimal transitions, no corporate branding overlays)
- Genuine reactions and authentic enthusiasm

**Sourcing UGC content:**
- Send products to micro-influencers (1,000-10,000 followers) for content creation
- Use UGC platforms (Billo, Insense, JoinBrands) to hire content creators
- Encourage customers to share content (post-purchase email with incentive)
- Repurpose positive customer reviews as video scripts for creators

### Creative Testing Framework

**Test hierarchy (test these elements in order of impact):**
1. **Hook (first 3 seconds):** Test 3-5 different opening hooks per product
2. **Format:** Test video vs carousel vs single image
3. **Messaging angle:** Test different value propositions (save time, save money,
   looks great, easy to use, etc.)
4. **Call to action:** Test different CTAs (Shop Now, Learn More, Get Yours)
5. **Thumbnail/cover image:** Test different preview images for video content

**Testing rules:**
- Test one variable at a time for clean data
- Run each creative variation for at least 3-5 days before judging
- Minimum 1,000 impressions per variation before making decisions
- Winner is determined by ROAS/CPA, not by CTR or engagement alone
- Retire losing creatives; iterate on winners with small variations

---

## Retargeting Strategies

Retargeting (remarketing) shows ads to people who have already interacted with
your product or brand. Retargeting audiences convert at 3-5x the rate of cold
audiences and should be a core component of every social ad strategy.

### Retargeting Funnel

```
Viewed product page (past 7 days) -- Highest intent, smallest audience
    |
Viewed product page (8-30 days) -- Moderate intent, medium audience
    |
Added to cart but didn't purchase (past 14 days) -- Very high intent, small
    |
Engaged with social content (past 30 days) -- Awareness level, larger audience
    |
Past purchasers (60-180 days) -- Cross-sell / repeat purchase
```

### Retargeting Campaign Setup

| Audience | Message | Creative | Bid Strategy |
|---|---|---|---|
| Cart abandoners (1-7 days) | "Still thinking about it? Here's why customers love it" | Product image + review quote overlay | Aggressive (highest ROAS audience) |
| Product viewers (1-7 days) | "You checked this out -- here's what makes it special" | Video demonstrating key feature/benefit | Moderate-aggressive |
| Product viewers (8-30 days) | "Remember this? Limited stock available" | Lifestyle image with urgency element | Moderate |
| Social engagers (1-30 days) | "Thanks for your interest -- here's a closer look" | Carousel showing multiple product angles | Moderate |
| Past purchasers (60-180 days) | "Loved your [product]? Check out [complementary product]" | Cross-sell product showcase | Moderate (loyal audience) |

### Retargeting Budget Rule

Allocate 15-25% of total social ad budget to retargeting campaigns. These
campaigns have the highest ROAS but the smallest audience pool. Do not over-
spend on retargeting or you will exhaust the audience and frequency will spike
(causing ad fatigue and negative sentiment).

**Frequency cap:** Limit retargeting ad exposure to 3-5 impressions per person
per week. Above this, diminishing returns set in rapidly.

---

## Scaling Social Ads

### When to Scale

Scale social ad spend only when ALL of the following conditions are met:
1. Current ROAS exceeds target ROAS by at least 20% (margin for efficiency loss)
2. Campaigns have been running for 14+ days with stable performance
3. Creative fatigue has not set in (CTR stable or improving)
4. Landing page / listing conversion rate is stable
5. Inventory can support increased sales velocity for 30+ days

### How to Scale (The 20% Rule)

Never increase ad budget by more than 20% at a time. Large budget jumps reset
the platform's optimization algorithm and can spike CPMs.

**Scaling sequence:**
1. Increase daily budget by 15-20%
2. Monitor performance for 3-5 days
3. If ROAS holds within 15% of pre-scale level, increase again
4. If ROAS drops more than 15%, hold at current level for 7 days
5. If ROAS does not recover, reduce to previous level and investigate

### Horizontal Scaling (Preferred for Sustainable Growth)

Instead of pumping more money into a single winning campaign, duplicate the
approach across new audiences and creatives.

**Methods:**
- Launch new ad sets with different Lookalike percentages (1%, 2-3%, 5%)
- Test new interest-based audiences related to your product
- Expand to new geographic markets (if product and logistics support it)
- Create new creative variations inspired by your best performers
- Add new platforms (if currently only on Meta, test TikTok)

### Vertical Scaling (Quick but Limited)

Increase budget on existing winning campaigns/ad sets.

**Constraints:**
- Budget increases beyond 40-50% total typically degrade ROAS
- Audience saturation happens faster with higher spend
- CPC and CPM increase as you compete for more of the same audience
- Creative fatigue accelerates with higher frequency

### Scaling Red Flags (Stop and Investigate)

| Signal | Threshold | Action |
|---|---|---|
| ROAS dropping week over week | 2 consecutive weeks | Pause scaling; diagnose cause |
| CTR declining | 20%+ drop from baseline | Creative fatigue; rotate new creatives |
| CPM increasing | 30%+ above baseline | Audience saturation; test new audiences |
| Frequency exceeding cap | 5+ impressions/person/week | Reduce budget or expand audience |
| Conversion rate dropping | 15%+ below baseline | Check landing page, pricing, stock issues |

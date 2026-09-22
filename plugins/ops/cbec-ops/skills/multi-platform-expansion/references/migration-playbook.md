# Platform Migration Playbook

A step-by-step operational guide for migrating products from an existing marketplace
to a new platform. This playbook covers everything from pre-migration assessment
through the first 90 days of operation on the new platform.

## Table of Contents

- [Pre-Migration Assessment](#pre-migration-assessment)
- [Account Setup Checklist](#account-setup-checklist)
- [Listing Migration Workflow](#listing-migration-workflow)
- [Inventory and Fulfillment Setup](#inventory-and-fulfillment-setup)
- [Advertising Launch Strategy](#advertising-launch-strategy)
- [Review Bootstrapping](#review-bootstrapping)
- [Multi-Platform Management Tools](#multi-platform-management-tools)
- [Operational SOP for Multi-Platform Sellers](#operational-sop-for-multi-platform-sellers)
- [Common Migration Mistakes](#common-migration-mistakes)
- [90-Day New Platform Launch Timeline](#90-day-new-platform-launch-timeline)

---

## Pre-Migration Assessment

Before committing resources to a new platform, complete this assessment to validate
the opportunity and estimate the investment required.

### 1. Category Viability Check

- **Search the target platform for your product category.** Count the number of
  results, note the price range of page-1 listings, and assess the quality of
  existing listings (images, reviews, descriptions).
- **Check category restrictions.** Some platforms gate certain categories (food,
  beauty, electronics, children's products). Confirm your category is open or that
  you can meet the ungating requirements.
- **Identify the top 5 competitors on the target platform.** Record their review
  counts, pricing, image quality, and advertising activity. This is your benchmark.

### 2. Economics Validation

Calculate the unit economics for your top 3 SKUs on the target platform:

```
Revenue per unit (target platform price)
- Product cost (COGS)
- Shipping to warehouse/fulfillment center
- Platform commission (% of selling price)
- Fulfillment fee (platform fulfillment or 3PL)
- Advertising cost per unit (estimate from CPC benchmarks)
- Returns and refunds allowance (% of revenue)
- Payment processing fee
- VAT/GST/sales tax
= Net profit per unit
```

**Minimum threshold:** Net profit per unit must be positive at a realistic advertising
spend level. If the unit economics are negative even with optimistic assumptions, the
platform may not be viable for this product.

### 3. Operational Readiness Check

- **Fulfillment:** Do you have access to warehousing in the target market, or will
  you use platform fulfillment? What is the inbound shipping cost from your origin?
- **Content:** Can you adapt existing listings (not copy-paste) for the new platform?
  Do you have the resources for platform-native content creation?
- **Customer service:** Can you handle customer inquiries in the target market's
  language within the platform's response time SLA?
- **Inventory:** Can you allocate separate inventory for the new platform without
  depleting stock on your existing platform?
- **Team capacity:** Who will manage the new platform day-to-day during the first
  90 days?

### 4. Compliance and Legal Check

- **Business registration:** Does the platform require a local entity, or can you
  sell cross-border?
- **Tax registration:** Do you need VAT/GST/sales tax registration in the target
  market?
- **Product certifications:** Does your product require certifications for the
  target market (CE, FCC, halal, SASO, etc.)?
- **Import restrictions:** Are there any import bans, quotas, or punitive tariffs
  for your product category?
- **IP considerations:** Is your brand/trademark registered in the target market?
  Are there existing sellers using similar branding?

Refer to `cbec-ops:platform-compliance` for detailed compliance requirements per
market.

---

## Account Setup Checklist

Each platform has distinct registration requirements. Use the relevant checklist
below. All sellers should prepare these universal documents before starting any
platform registration.

### Universal Documents (Prepare in Advance)

- [ ] Business registration certificate / license
- [ ] Government-issued ID of the business owner or authorized representative
- [ ] Bank account details for payout (or Payoneer/WorldFirst virtual account)
- [ ] Tax identification number (EIN, VAT number, etc.)
- [ ] Product images and descriptions ready for initial listings
- [ ] Brand authorization letter (if selling as authorized dealer)
- [ ] Trademark registration certificate (if registering brand)

### Amazon

- [ ] Professional seller account registration ($39.99/month)
- [ ] Identity verification (video call or document upload)
- [ ] US: EIN or SSN required; EU: VAT number in at least one EU country
- [ ] Brand Registry application (requires registered trademark with serial number)
- [ ] Category approval applications for gated categories
- [ ] FBA shipment plan for initial inventory
- [ ] Estimated setup time: 2-4 weeks (longer if category approval needed)

### Shopee

- [ ] Cross-Border Seller Center registration (for international sellers)
- [ ] Business license and ID upload
- [ ] Product catalog preparation (minimum 5-10 listings to activate shop)
- [ ] Shopee Logistics Service (SLS) setup
- [ ] Shop decoration (banner, logo, description)
- [ ] Estimated setup time: 1-2 weeks

### Lazada

- [ ] Global Seller Center registration (for cross-border sellers)
- [ ] Business license and ID verification
- [ ] LazMall application (if applicable, requires brand authorization)
- [ ] LGS (Lazada Global Shipping) setup for cross-border fulfillment
- [ ] Estimated setup time: 1-3 weeks (LazMall approval may take longer)

### TikTok Shop

- [ ] TikTok Shop Seller Center registration
- [ ] Business license and legal representative ID
- [ ] US: SSN or EIN required
- [ ] Product compliance documentation for regulated categories
- [ ] Initial video/live content plan (critical for platform success)
- [ ] Creator affiliate commission strategy
- [ ] Estimated setup time: 1-2 weeks

### Walmart Marketplace

- [ ] Application submission (approval required, not open registration)
- [ ] US business tax ID (EIN) required
- [ ] US warehouse or fulfillment address
- [ ] Demonstrated e-commerce track record (provide existing platform metrics)
- [ ] WFS enrollment (recommended for Walmart+ badge)
- [ ] Estimated setup time: 2-6 weeks (application review is the bottleneck)

### Mercado Libre

- [ ] Seller registration (individual or business)
- [ ] Brazil: CPF (individual) or CNPJ (business) required
- [ ] Mexico: RFC (tax ID) required
- [ ] Cross-border seller program enrollment (if selling from outside LATAM)
- [ ] Mercado Pago account setup for payments
- [ ] Mercado Envios integration
- [ ] Estimated setup time: 1-3 weeks

### Noon

- [ ] Seller portal registration
- [ ] Trade license (UAE or KSA) or cross-border agreement
- [ ] Product certification documents (halal, ESMA, SASO where applicable)
- [ ] FBN enrollment for Noon Fulfillment
- [ ] Estimated setup time: 2-4 weeks

### Coupang

- [ ] Korean business registration number (BRN) or cross-border partnership
- [ ] All product information translated to Korean
- [ ] Rocket Delivery / FLC enrollment
- [ ] Korean customer service capability (in-house or outsourced)
- [ ] Estimated setup time: 3-6 weeks

### Ozon

- [ ] Russian legal entity or cross-border seller registration
- [ ] Product documentation in Russian
- [ ] FBO/FBS enrollment for Ozon fulfillment
- [ ] Payment processing setup (verify sanctions compliance)
- [ ] Estimated setup time: 2-4 weeks

### Allegro

- [ ] Seller account registration
- [ ] EU-based business documentation or cross-border registration
- [ ] Polish VAT registration (recommended)
- [ ] All listings prepared in Polish
- [ ] Allegro One Fulfillment enrollment (optional but recommended)
- [ ] Estimated setup time: 1-3 weeks

---

## Listing Migration Workflow

Listing migration is not listing duplication. Each platform has its own search
algorithm, buyer expectations, content format, and keyword ecosystem. Effective
migration requires adaptation, not copy-paste.

### Content Adaptation

#### Title Format

Titles must be adapted to each platform's algorithm and display conventions.

| Platform | Max Length | Format Emphasis | Example Structure |
|---|---|---|---|
| Amazon | 200 chars (recommended < 150) | Keyword-rich, structured | Brand + Primary Keyword + Key Feature + Product Type + Spec |
| Shopee | 120 chars | Eye-catching, use special characters | Keyword + Feature + Emoji + Size/Variant |
| TikTok Shop | 100 chars | Concise, benefit-focused | Product Type + Key Benefit + Spec |
| Walmart | 75 chars (recommended) | Clean, shopper-friendly | Brand + Product Type + Key Feature + Size |
| Mercado Libre | 60 chars | Direct, clear | Product Type + Brand + Key Spec + Model |
| Lazada | 150 chars | Similar to Shopee with LazMall branding | Brand + Product Type + Feature + Spec |

**Adaptation rules:**
- Always research the top-performing listing titles on the target platform to match
  the native style.
- Do not assume keywords that work on Amazon will work on Shopee or TikTok Shop.
  Each platform has its own search behavior.
- Respect character limits strictly. Truncated titles look unprofessional and lose
  keyword value.

#### Description Style

| Platform | Format | Key Differences |
|---|---|---|
| Amazon | A+ Content (Brand Registry) or text-only | Structured modules, comparison charts, brand story. Text descriptions are secondary. |
| Shopee | Rich HTML with images inline | Image-heavy descriptions with embedded graphics. Text blocks between product images. |
| TikTok Shop | Short, benefit-focused | Concise descriptions; buyers make decisions from video, not description. |
| Walmart | Rich media modules | Similar to Amazon A+ but with Walmart's formatting requirements. |
| Mercado Libre | Text with structured attributes | Structured product attributes are more important than free-text description. |

#### Keyword Approach

| Step | Action |
|---|---|
| 1 | Research keywords natively on the target platform (do not import your Amazon keyword list wholesale) |
| 2 | Use the target platform's autocomplete suggestions for seed keywords |
| 3 | Analyze top 10 competitor listings on the target platform for keyword patterns |
| 4 | Use platform-specific keyword tools if available (Shopee Keyword Ads tool, Walmart Search Insights) |
| 5 | Build a separate keyword list for each platform, ranked by platform-specific search volume |
| 6 | Map keywords to listing elements (title, bullets, description, backend) per platform's optimization rules |

### Image Requirements Adaptation

Images should be adapted for each platform's display context and buyer expectations.

| Specification | Amazon | Shopee | TikTok Shop | Walmart | Mercado Libre | Lazada |
|---|---|---|---|---|---|---|
| **Aspect ratio** | 1:1 | 1:1 or 2:3 | 1:1 | 1:1 | 1:1 | 1:1 |
| **Min resolution** | 1000x1000 | 800x800 | 600x600 | 1000x1000 | 500x500 | 800x800 |
| **Recommended** | 2000x2000 | 1200x1200 | 1080x1080 | 2000x2000 | 1200x1200 | 1200x1200 |
| **Max images** | 9 | 9 | 9 | 25 | 12 | 8 |
| **Main image bg** | Pure white | White or clean | White or clean | Pure white | White preferred | White preferred |
| **Text on images** | Not on main | Encouraged (infographics) | Minimal | Not on main | Allowed | Encouraged |
| **Video** | 1 video slot | Prioritized | Critical | Supported | Supported | Prioritized |

**Platform-specific image tips:**

- **Amazon:** Strict white-background main image policy. Infographics in secondary
  slots. A+ Content modules allow additional image-text combinations.
- **Shopee:** Buyers expect colorful, eye-catching images. Infographic-style images
  with text overlays and benefit callouts perform well. Video is strongly weighted
  in search ranking.
- **TikTok Shop:** Product images matter less than video. Invest more in short-form
  video content (15-60 seconds) showing the product in action. Product images are
  secondary to video content.
- **Walmart:** Similar to Amazon white-background standards. Rich media modules in
  the description allow for lifestyle and infographic content.
- **Mercado Libre:** Image quality bar is lower than Amazon, but high-quality images
  still outperform. Multiple angles and detail shots are important.

### Category Mapping

Product categories do not map 1:1 across platforms. Each platform has its own
category tree (browse nodes).

**Migration process:**

1. **Identify your current category path.** Example on Amazon: Home & Kitchen >
   Kitchen & Dining > Kitchen Utensils & Gadgets > Cooking Utensils.
2. **Search the target platform for similar products.** Note which category the top
   competitors are listed in.
3. **Browse the target platform's category tree.** Find the most specific applicable
   category. Avoid placing products in broad parent categories.
4. **Check category-specific requirements.** Some categories on the target platform
   may require different attributes, certifications, or product specifications.
5. **Document the mapping.** Maintain a spreadsheet mapping source category to target
   category for each platform.

| Source (Amazon US) | Shopee (SG) | TikTok Shop | Walmart |
|---|---|---|---|
| Home & Kitchen > Kitchen Utensils | Home & Living > Kitchenware | Home & Kitchen > Kitchen Tools | Home > Kitchen > Kitchen Gadgets & Utensils |
| Beauty & Personal Care > Skin Care | Beauty > Skin Care | Beauty & Personal Care > Skincare | Beauty > Skin Care |
| Electronics > Headphones | Mobile & Gadgets > Earphones | Electronics > Audio > Headphones | Electronics > Audio > Headphones |

### Pricing Adaptation

Do not use the same price across all platforms. Each platform has a different fee
structure, competitive landscape, and buyer price sensitivity.

**Pricing calculation per platform:**

```
Target retail price = (COGS + Shipping + Platform fees + Ad cost per unit + Returns allowance)
                      / (1 - Target net margin %)

Compare to:
- Top 5 competitor prices on the target platform
- Your existing platform price (avoid large discrepancies if buyers cross-shop)
- Platform price parity policies (Amazon's fair pricing policy)
```

**Key adjustments by platform:**

| Factor | How It Affects Pricing |
|---|---|
| Commission rates | Higher commission (Mercado Libre 11-22%) vs lower (Shopee 2-10%) directly affects margin |
| Fulfillment costs | FBA vs. Shopee SLS vs. self-ship have different cost structures |
| Advertising costs | Amazon CPCs ($0.80-$3.00) vs. Shopee CPCs ($0.05-$0.50) affect required margin |
| Buyer price sensitivity | SEA buyers are more price-sensitive than US/EU buyers; adjust price points accordingly |
| Currency and taxes | VAT, GST, import duties vary by market and may need to be included in or added to the listed price |
| Competitor pricing | Price to market, not to cost. The same product may sell at very different prices on different platforms |

---

## Inventory and Fulfillment Setup

### Inventory Allocation Strategy

**Rule: Never allocate 100% of inventory to the new platform.** The new platform is
unproven. Start with a conservative allocation and increase as performance data
validates demand.

| Phase | New Platform Allocation | Current Platform Allocation | Reserve |
|---|---|---|---|
| Phase 1 (Test) | 15-20% of production | 70-75% | 10% safety stock |
| Phase 2 (Validate) | 25-30% | 60-65% | 10% safety stock |
| Phase 3 (Scale) | Based on actual velocity data | Based on actual velocity data | 10% safety stock |

### Fulfillment Setup by Platform Type

#### Platform Fulfillment (FBA, WFS, FBN, FBT, etc.)

1. **Enroll in the platform's fulfillment program.**
2. **Create inbound shipment plan** for initial inventory (3 months of projected
   sales for the new platform).
3. **Ship to the platform's receiving warehouse.** Allow 2-4 weeks for receiving
   and processing.
4. **Configure inventory settings:** reorder alerts, minimum stock levels, automatic
   replenishment (if available).
5. **Test the cycle:** Place a test order to verify fulfillment speed, packaging
   quality, and tracking accuracy.

#### Third-Party Logistics (3PL)

1. **Select a 3PL with experience on the target platform.** Verify that they offer
   integration with the platform's order management system.
2. **Negotiate rates** based on projected volume. Get quotes for storage, pick and
   pack, shipping, and returns processing.
3. **Ship initial inventory** to the 3PL warehouse. Allow 1-2 weeks for receiving
   and setup.
4. **Integrate order flow:** Automate order import from the platform to the 3PL
   system. Test end-to-end with a trial order.
5. **Set up returns handling:** Define the return address, inspection process, and
   restocking workflow.

#### Cross-Border Direct Shipping

1. **Identify shipping partners** that service the target market (4PX, Yanwen, YunExpress
   for China-origin; regional carriers for other origins).
2. **Calculate landed cost** including international shipping, customs duties, and
   last-mile delivery.
3. **Set realistic delivery time expectations** in the listing (10-25 days for
   cross-border is common; set expectations at the high end).
4. **Implement tracking integration** so buyers can monitor shipments.
5. **Prepare for returns:** Cross-border returns are expensive. Consider offering
   refund-without-return for low-cost items rather than paying reverse logistics.

### Multi-Platform Inventory Sync

When selling the same SKU across multiple platforms, inventory synchronization is
critical to avoid overselling.

**Options:**

| Method | Complexity | Cost | Best For |
|---|---|---|---|
| Manual spreadsheet tracking | Low | Free | < 20 SKUs, 2 platforms |
| Multi-channel listing tool (see Management Tools section) | Medium | $50-$500/month | 20-200 SKUs, 2-4 platforms |
| ERP/OMS integration (Ordoro, Cin7, Brightpearl) | High | $200-$2,000+/month | 200+ SKUs, 4+ platforms |
| Dedicated inventory per platform (no sync needed) | Low | Higher inventory investment | When stock levels support it |

**Overselling prevention rules:**
- Set buffer stock (10-15%) deducted from available quantity across all platforms.
- Configure automatic listing deactivation when stock falls below a threshold.
- Use a single source of truth for inventory counts (one system, not per-platform).
- Monitor sync frequency: near real-time for high-velocity products, hourly for
  moderate, daily for slow movers.

---

## Advertising Launch Strategy

Advertising on a new platform follows a different strategy than advertising on an
established platform. The goal in the first 30-60 days is data collection and
visibility, not profitability.

### Phase 1: Discovery (Days 1-14)

**Objective:** Collect keyword and conversion data.

- Launch auto/broad campaigns (if available) on top 3-5 SKUs.
- Set moderate daily budgets ($20-$50 per SKU depending on platform and category).
- Target ACoS is not the priority at this stage. Accept 40-60% ACoS to gain data.
- Enable all ad placements to gather data on which positions convert.
- On TikTok Shop: prioritize creator affiliate relationships over self-managed ads
  during this phase. Reach out to 20-50 creators in your category.

### Phase 2: Optimization (Days 15-45)

**Objective:** Identify winning keywords and ad configurations.

- Analyze Phase 1 data: identify converting keywords, non-converting keywords, and
  high-impression/low-click keywords.
- Create targeted campaigns with proven converting keywords (exact match or
  equivalent on the platform).
- Add negative keywords/targets for irrelevant traffic identified in Phase 1.
- Reduce bids on low-performing placements. Increase bids on high-converting
  placements.
- Target ACoS: 25-40% (moving toward breakeven on advertising).
- On TikTok Shop: identify top-performing creators from Phase 1 and deepen those
  relationships. Increase commission rates for proven performers.

### Phase 3: Scale (Days 46-90)

**Objective:** Achieve sustainable advertising performance and begin scaling.

- Expand campaign structure: add Sponsored Brands / Display (if available on the
  platform).
- Increase budgets on proven campaigns.
- Launch campaigns for additional SKUs beyond the initial 3-5.
- Begin A/B testing ad copy, images, and targeting strategies.
- Target ACoS: 15-25% (sustainable profitability).
- Build a complete advertising funnel if the platform supports it (awareness ->
  consideration -> conversion).

### Platform-Specific Advertising Notes

| Platform | Key Difference from Amazon |
|---|---|
| Shopee | Lower CPCs but also lower conversion rates. Flash sale and voucher ads are critical. Budget for platform campaigns (9.9, 11.11, 12.12). |
| TikTok Shop | Creator-driven sales often outperform self-managed ads. Allocate 30-50% of ad budget to creator commissions. Video content quality is the primary determinant of ad performance. |
| Walmart | Lower competition means lower CPCs (30-50% less than Amazon). Fewer ad types available. WFS badge significantly improves conversion rate. |
| Mercado Libre | Ad system is simpler than Amazon. Focus on Product Ads (sponsored search). Campaign participation (sales events) is critical for visibility. |
| Lazada | Sponsored search and discovery ads are the primary tools. LazLive (live streaming) is an increasingly important sales channel. Campaign participation is essential. |

---

## Review Bootstrapping

New listings on any platform face the cold-start problem: no reviews mean lower
conversion rates, which mean fewer sales, which means fewer reviews. Breaking this
cycle requires a deliberate strategy.

### Legitimate Review Generation Tactics

All methods below are compliant with platform policies. Never purchase fake reviews,
use review manipulation services, or violate platform Terms of Service.

#### 1. Vine / Early Reviewer Programs (Where Available)

- **Amazon Vine:** Enroll products in the Vine program. Costs vary by marketplace
  (free in some, fee-based in others). Vine reviewers receive free product and
  leave honest reviews.
- **Availability:** Amazon-only. Other platforms do not have equivalent programs.

#### 2. Product Insert Cards

- Include a card in the packaging thanking the buyer and encouraging them to leave
  a review. Do not offer incentives for reviews (this violates most platform
  policies).
- Keep the language neutral: "We would love to hear your feedback" rather than
  "Please leave a 5-star review."
- Include a QR code linking to the review page to reduce friction.

#### 3. Post-Purchase Follow-Up

- Use the platform's buyer messaging system (where available) to send a follow-up
  message after delivery asking for feedback.
- Amazon allows automated follow-up via the "Request a Review" button. Other
  platforms may have similar tools.
- Time the follow-up 3-7 days after delivery (enough time to use the product, not
  so long that they have forgotten about it).

#### 4. Existing Customer Base Leverage

- If you have an existing customer base from another platform or DTC, encourage them
  to purchase and review on the new platform (do not offer free product in exchange
  for reviews, but you can direct existing customers to your new storefront).
- Email marketing to existing customers announcing your new platform presence.

#### 5. Social Proof Transfer

- While reviews do not transfer between platforms, you can reference your brand's
  overall track record in your listing images (for example, "Trusted by 10,000+
  customers" with appropriate disclaimers) where platform policy allows.
- Display press mentions, awards, or certifications as social proof while building
  platform-specific reviews.

#### 6. Competitive Pricing During Launch

- Price aggressively during the first 30-60 days to maximize sales volume and
  review accumulation rate. Accept lower margins during the review-building phase.
- Consider coupons or limited-time promotions to increase unit velocity.

### Review Accumulation Benchmarks

| Platform | Reviews Needed for Competitive Positioning | Typical Time to Reach |
|---|---|---|
| Amazon US | 25-100+ (category dependent) | 3-6 months with Vine + organic |
| Shopee | 10-50 (lower bar than Amazon) | 1-3 months with active promotion |
| TikTok Shop | Reviews matter less; creator content is primary social proof | Ongoing |
| Walmart | 10-25 (lower competition means lower bar) | 2-4 months |
| Mercado Libre | 10-30 | 2-4 months |

---

## Multi-Platform Management Tools

As the number of platforms increases, manual management becomes unsustainable.
These tools help centralize operations.

### Listing Management and Syndication

| Tool | Platforms Supported | Key Features | Approximate Cost |
|---|---|---|---|
| **Sellbrite** (by GoDaddy) | Amazon, eBay, Walmart, Etsy, Shopify | Inventory sync, listing creation, order management | $29-$179/month |
| **ChannelAdvisor** | Amazon, eBay, Walmart, Google, Shopee, Lazada + 100s | Enterprise-grade multichannel management, analytics | Custom pricing ($1K+/month) |
| **Listing Mirror** | Amazon, eBay, Walmart, Etsy, Shopify, BigCommerce | Listing sync, inventory sync, order routing | $99-$499/month |
| **Sellbery** | Amazon, eBay, Shopify, Walmart, Google Shopping | Automated product listing sync | $195-$395/month |
| **CedCommerce** | Amazon, eBay, Walmart, TikTok Shop, Shopee, Lazada | Platform-specific integration apps | Varies ($20-$200/month per integration) |
| **LitCommerce** | Amazon, eBay, Etsy, Walmart, TikTok Shop + others | Listing sync, order management | $29-$69/month |

### Inventory and Order Management

| Tool | Key Features | Approximate Cost |
|---|---|---|
| **Ordoro** | Inventory sync, dropship automation, shipping | $59-$149/month |
| **Cin7** (DEAR Inventory) | Full inventory management, multi-warehouse, B2B + B2C | $349-$999/month |
| **Brightpearl** (by Sage) | ERP for retail/wholesale, omnichannel order management | Custom pricing ($500+/month) |
| **Skubana** (by Extensiv) | Inventory, orders, analytics, 3PL management | Custom pricing |
| **Linnworks** | Multi-channel inventory, order processing, shipping | Custom pricing ($150+/month) |

### Pricing and Repricing

| Tool | Key Features | Approximate Cost |
|---|---|---|
| **RepricerExpress** | Automated repricing for Amazon + eBay | $79-$399/month |
| **Informed.co** | AI repricing for Amazon + Walmart | $99-$499/month |
| **Prisync** | Competitor price tracking across platforms | $99-$399/month |
| **Seller Snap** | Game-theory repricing for Amazon | $250-$800/month |

### Analytics and Reporting

| Tool | Key Features | Approximate Cost |
|---|---|---|
| **Sellerboard** | Profit analytics for Amazon | $19-$79/month |
| **DataHawk** | SEO, sales, and market analytics for Amazon | Custom pricing |
| **Sellics** (Perpetua) | Analytics and advertising management | $250+/month |
| **Putler** | Multi-channel analytics dashboard | $20-$50/month |

### Choosing the Right Tool Stack

| Seller Scale | Recommended Approach |
|---|---|
| **2 platforms, < 50 SKUs** | Listing Mirror or Sellbrite for sync + spreadsheet for analytics |
| **2-3 platforms, 50-200 SKUs** | Listing Mirror or LitCommerce + Ordoro + platform-native analytics |
| **3-5 platforms, 200-1000 SKUs** | ChannelAdvisor or Linnworks + Cin7 + dedicated analytics tools |
| **5+ platforms or 1000+ SKUs** | Enterprise ERP (Brightpearl/Cin7) + ChannelAdvisor + custom reporting |

---

## Operational SOP for Multi-Platform Sellers

Managing multiple platforms requires structured daily, weekly, and monthly routines
to prevent operational breakdown.

### Daily Tasks (30-60 minutes per platform)

| Task | Priority | Platform-Agnostic |
|---|---|---|
| Check and respond to customer messages | Critical | Handle within platform SLA (typically 24 hrs) |
| Review and process new orders | Critical | Ensure fulfillment triggers are working |
| Check account health / performance metrics | High | Monitor for policy violations, late shipments, negative feedback |
| Review advertising spend and performance | High | Pause underperforming campaigns, check daily budget caps |
| Monitor inventory levels | High | Identify low-stock SKUs across platforms |
| Handle returns and refund requests | Medium | Process within platform SLA |

### Weekly Tasks (2-4 hours)

| Task | Priority |
|---|---|
| Inventory reorder assessment: calculate days of stock remaining per platform, trigger reorders | Critical |
| Advertising performance review: adjust bids, add/remove keywords, review ACoS by campaign | High |
| Competitor monitoring: check top competitor pricing, new listings, review activity | Medium |
| Cross-platform pricing consistency check: ensure no platform has a pricing error or policy violation | Medium |
| Performance metrics review: conversion rate, session traffic, buy box (Amazon), seller score | Medium |

### Monthly Tasks (4-8 hours)

| Task | Priority |
|---|---|
| Full P&L review per platform: revenue, COGS, fees, advertising, returns, net profit | Critical |
| Listing optimization audit: identify underperforming listings for content refresh | High |
| Inventory health review: identify aged inventory, plan promotions to clear slow movers | High |
| Platform policy and fee update review: check for announced changes to fees, policies, or features | Medium |
| Tool and software review: assess whether current tools are meeting needs, evaluate alternatives | Low |
| Strategic review: is the multi-platform strategy working? Should any platform be deprioritized? | Medium |

### Escalation and Decision Matrix

| Scenario | Action |
|---|---|
| Account suspension on any platform | Immediate: stop advertising, preserve cash flow. Within 24 hrs: submit appeal. Do not wait. |
| Inventory stockout on primary platform | Pause advertising on primary. Reallocate from new platform if possible. Expedite reorder. |
| New platform not profitable by month 6 | Review: Is the issue fixable (bad listings, wrong pricing, insufficient ads) or structural (wrong category, wrong platform)? If structural, exit gracefully. |
| Negative review spike on any platform | Investigate root cause (product quality, shipping damage, listing accuracy). Address within 48 hrs. |
| Platform fee increase announcement | Recalculate unit economics. If margin drops below threshold, adjust pricing or consider exiting the platform. |

---

## Common Migration Mistakes

### 1. Copy-Pasting Listings Without Adaptation

**The mistake:** Exporting Amazon listings and importing them directly into Shopee
or Walmart without any changes.

**Why it fails:** Each platform has different title format conventions, keyword
algorithms, image requirements, and buyer expectations. An Amazon-optimized title
(long, keyword-dense) looks spammy on Walmart (which prefers short, clean titles).
A text-heavy Amazon description converts poorly on Shopee where buyers expect
image-rich descriptions.

**The fix:** Treat each platform as a new listing project. Research the target
platform's top sellers in your category and match their style. Adapt every element:
title, images, bullets, description, backend keywords.

### 2. Underestimating the Review Cold-Start Problem

**The mistake:** Assuming that a product that sells well on Amazon (with 500+
reviews) will immediately sell well on a new platform with zero reviews.

**Why it fails:** Reviews are the primary trust signal on most marketplaces. A
listing with zero reviews competes against listings with dozens or hundreds. Buyers
default to the reviewed option even at a higher price.

**The fix:** Budget for 30-90 days of below-target conversion rates while reviews
accumulate. Use every legitimate review generation tactic available. Price
aggressively during the cold-start period to maximize unit velocity.

### 3. Spreading Inventory Too Thin

**The mistake:** Splitting existing inventory across platforms without increasing
total production, leading to stockouts on the primary platform.

**Why it fails:** Stockouts on the primary platform (where you have reviews, ranking,
and established sales) are far more costly than slow sales on the new platform. Lost
organic rank on Amazon can take weeks or months to recover.

**The fix:** Increase total inventory investment before expansion. Each platform
should have independent stock allocation. Never rob the primary platform to feed
the new one.

### 4. Ignoring Platform-Specific Customer Expectations

**The mistake:** Applying Amazon customer service standards to Shopee, or Shopee
response norms to Walmart.

**Why it fails:** Buyer expectations vary by platform and region. Shopee buyers in
SEA expect chat-like responsiveness (minutes, not hours). Amazon buyers expect Prime-
speed delivery. Mercado Libre buyers in Brazil expect COD options. Mismatch leads
to poor ratings and account health issues.

**The fix:** Research the target platform's customer service SLAs and buyer
expectations before launch. Configure response templates in the local language. Set
up notifications for new messages on each platform.

### 5. No Exit Strategy

**The mistake:** Committing heavily to a new platform without defining conditions
under which you would exit.

**Why it fails:** Without clear kill criteria, failing platforms consume resources
indefinitely. Sunk cost bias keeps sellers investing in platforms that will never be
profitable.

**The fix:** Before launch, define specific exit criteria. For example: "If the
platform is not breakeven by month 6, or if monthly revenue is below $5,000 by
month 4, we will liquidate remaining inventory and close the account." Write it
down. Review it monthly.

### 6. Using the Same Advertising Strategy Everywhere

**The mistake:** Applying Amazon PPC tactics directly to Shopee, TikTok Shop, or
Walmart without adjustment.

**Why it fails:** Each platform's advertising system has different strengths,
limitations, and buyer behavior. Amazon PPC is keyword-driven with high CPCs;
Shopee ads are cheaper but less targeted; TikTok Shop is creator-driven with video
as the primary ad unit. What works on one platform may waste money on another.

**The fix:** Learn each platform's advertising system independently. Start with
the platform's recommended campaign structure for new sellers. Optimize based on
platform-specific data, not assumptions from other platforms.

### 7. Neglecting the Primary Platform During Expansion

**The mistake:** Redirecting too much attention and budget to the new platform,
causing performance decline on the established platform.

**Why it fails:** The established platform is generating the majority of revenue
and profit. A 5% decline on a $100K/month platform costs more than a 50% increase
on a $5K/month new platform.

**The fix:** Set a rule: the primary platform must not lose more than 5% of
key metrics (revenue, conversion rate, organic rank) during the expansion period.
If it does, immediately rebalance attention and resources back to the primary
platform.

---

## 90-Day New Platform Launch Timeline

A structured timeline for launching on a new marketplace. Adjust based on platform
and product specifics, but maintain the phased approach.

### Pre-Launch (Weeks -4 to 0)

| Week | Task |
|---|---|
| Week -4 | Complete Pre-Migration Assessment. Confirm category viability, calculate unit economics, verify compliance requirements. |
| Week -3 | Submit platform registration. Begin account setup and verification. Order initial inventory for the new platform. |
| Week -2 | Prepare adapted listings: titles, images, descriptions, keywords (platform-native, not copied). Set up fulfillment integration (FBA, WFS, 3PL, etc.). |
| Week -1 | Finalize all listing content. Create initial advertising campaigns (in draft). Confirm inventory is received at fulfillment center or ready to ship. Set up multi-platform management tools. |
| Week 0 | **LAUNCH.** Publish listings. Activate advertising campaigns. Begin daily monitoring routine. |

### Month 1: Establish Presence (Weeks 1-4)

| Week | Focus | Key Metrics to Track |
|---|---|---|
| Week 1 | Monitor listing indexing and search visibility. Verify fulfillment works (place test orders). Adjust ad bids based on initial data. | Impressions, clicks, orders |
| Week 2 | First optimization pass: adjust titles, keywords, and images based on Week 1 data. Increase ad budget on performing products. Pause ads on non-performers. | CTR, conversion rate, ACoS |
| Week 3 | Begin review generation efforts (insert cards, follow-up messages, Vine enrollment if Amazon). Monitor account health metrics. | Review count, seller rating |
| Week 4 | **Month 1 review.** Compile performance data. Calculate actual vs. projected unit economics. Decide: continue, adjust, or pause. | Revenue, net profit, reviews accumulated, account health |

**Month 1 success criteria:**
- At least 1 product generating organic (non-ad) sales.
- No account health violations.
- Unit economics within 20% of pre-launch projections (adjusted for launch-phase
  advertising).

### Month 2: Optimize and Expand (Weeks 5-8)

| Week | Focus | Key Metrics to Track |
|---|---|---|
| Week 5 | Listing optimization round 2: A/B test images, refine keywords, adjust pricing based on competitive data. | Conversion rate change, session growth |
| Week 6 | Expand SKU count: add 5-10 additional products based on Month 1 learnings. Launch ads for new SKUs. | New SKU performance, total revenue |
| Week 7 | Advertising optimization: build targeted campaigns from auto-campaign data. Implement negative keywords. Test new ad types (if available). | ACoS improvement, ROAS |
| Week 8 | **Month 2 review.** Assess profitability trend. Evaluate whether to proceed to full scale or extend optimization phase. | Revenue trend, net margin trend, review accumulation rate |

**Month 2 success criteria:**
- At least 3 products profitable after advertising costs.
- Overall platform ROAS > 2.0.
- Review accumulation on track (see benchmarks above).

### Month 3: Scale or Exit (Weeks 9-12)

| Week | Focus | Key Metrics to Track |
|---|---|---|
| Week 9 | If Month 2 criteria met: expand to full relevant catalog. If not met: double down on optimization before scaling. | Full catalog performance |
| Week 10 | Scale advertising: increase budgets on proven campaigns. Launch brand/display campaigns if available. | Total ad spend, total ad revenue, ACoS at scale |
| Week 11 | Operational hardening: automate inventory sync, set up reorder alerts, document SOPs for ongoing platform management. | Operational efficiency metrics |
| Week 12 | **90-Day review.** Comprehensive assessment of the new platform's performance. Make strategic decision: scale further, maintain current level, or exit. | Total revenue, net profit, contribution to overall business, ROI vs. investment |

**Month 3 decision criteria:**

| Scenario | Decision |
|---|---|
| Platform is profitable and growing | Continue investment. Move to Phase 4 (Optimize) in the main skill file. |
| Platform is breakeven with positive trajectory | Continue for 90 more days with focused optimization. Revisit at 180-day mark. |
| Platform is unprofitable but showing improvement | Extend to 180 days with a tighter budget. Define hard exit criteria for the 180-day review. |
| Platform is unprofitable with no improvement trend | Exit. Liquidate remaining inventory via discounts. Document lessons learned. Redirect resources to primary platform or evaluate a different expansion target. |

---

## Quick Reference: Migration Checklist

Use this consolidated checklist to track progress through the migration process.

### Pre-Migration

- [ ] Category viability confirmed on target platform
- [ ] Unit economics calculated and positive (at realistic assumptions)
- [ ] Compliance and certification requirements identified
- [ ] Budget allocated: inventory, advertising, content, tools
- [ ] Team capacity assigned for 90-day launch period
- [ ] Exit criteria defined and documented

### Account and Setup

- [ ] Platform account registered and verified
- [ ] Fulfillment method chosen and set up
- [ ] Payment / payout method configured
- [ ] Multi-platform management tools integrated
- [ ] Inventory allocated and shipped to fulfillment center

### Listing Preparation

- [ ] Keywords researched natively on target platform
- [ ] Titles adapted to platform format and conventions
- [ ] Images adapted to platform specs and style
- [ ] Descriptions written in platform-native style
- [ ] Category mapping completed
- [ ] Pricing set based on platform-specific economics
- [ ] Backend keywords / search terms populated

### Launch

- [ ] Listings published and indexed
- [ ] Advertising campaigns activated
- [ ] Daily monitoring routine established
- [ ] Customer service capability confirmed
- [ ] Review generation plan activated

### 90-Day Reviews

- [ ] Month 1 review completed (Week 4)
- [ ] Month 2 review completed (Week 8)
- [ ] Month 3 / 90-day review completed (Week 12)
- [ ] Strategic decision made: scale, maintain, optimize, or exit

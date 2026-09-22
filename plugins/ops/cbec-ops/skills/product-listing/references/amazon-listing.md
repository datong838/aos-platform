# Amazon Listing Optimization Guide

Comprehensive reference for creating and optimizing product listings on Amazon. Covers
all marketplaces (US, UK, DE, JP, etc.) with US-centric defaults.

## Table of Contents

- [Title Formula](#title-formula)
- [Bullet Points](#bullet-points)
- [Product Description and A+ Content](#product-description-and-a-content)
- [Backend Search Terms](#backend-search-terms)
- [Image Requirements](#image-requirements)
- [Variation Strategy](#variation-strategy)
- [Amazon SEO Signals](#amazon-seo-signals)
- [Common Amazon Listing Mistakes](#common-amazon-listing-mistakes)

---

## Title Formula

Amazon titles serve as the primary ranking factor. The A9/COSMO algorithm heavily
weights keyword presence and position within the title.

### Structure

```
Brand + Primary Keyword + Key Feature + Product Type + Size/Quantity + Key Benefit
```

### Rules

- **Maximum length**: 200 characters (some categories cap at 150 or 80; check
  category style guide).
- **First 80 characters** are visible on mobile and in search results; front-load
  the primary keyword here.
- Use title case (capitalize first letter of major words).
- Separate logical sections with hyphens (-) or commas; avoid pipes (|).
- Do not include price, promotional language ("Best Seller", "Hot Sale"), or
  subjective claims ("Amazing", "Perfect").
- Include the brand name first (required by Amazon style guide).
- Spell out numbers under 10; use numerals for 10 and above.
- Include relevant specs: size, quantity/count, color, material where applicable.

### Title Templates by Category

**Electronics**:
```
[Brand] [Product Type] [Key Feature] - [Connectivity/Compatibility], [Spec], [Benefit]
Example: Anker USB-C Charger 65W Fast Charging - Compatible with MacBook and iPhone, GaN III Technology, Compact Foldable Design
```

**Home and Kitchen**:
```
[Brand] [Material] [Product Type] [Size/Set] - [Key Feature], [Use Case], [Benefit]
Example: OXO Stainless Steel Mixing Bowl Set of 3 - Non-Slip Base, Dishwasher Safe, Nested for Easy Storage
```

**Apparel**:
```
[Brand] [Gender/Audience] [Product Type] [Style] - [Material], [Key Feature], [Size Range Available]
Example: Hanes Men's Crew Neck T-Shirt 6-Pack - 100% Cotton, Tagless Comfort, Sizes S-3XL
```

**Beauty and Personal Care**:
```
[Brand] [Product Type] [Key Ingredient] - [Size/Volume], [Skin Type/Concern], [Benefit]
Example: CeraVe Moisturizing Cream with Hyaluronic Acid - 19 oz, For Dry to Very Dry Skin, Fragrance Free
```

**Toys and Games**:
```
[Brand] [Product Type] [Theme/Character] - [Age Range], [Piece Count], [Key Feature]
Example: LEGO City Space Exploration Shuttle Set - Ages 6+, 486 Pieces, Includes 3 Astronaut Minifigures
```

---

## Bullet Points

Amazon allows 5 bullet points (called "Key Product Features") for most categories.
These appear prominently on the product detail page and are indexed for search.

### Format: Benefit-First

```
[KEYWORD-RICH BENEFIT HEADER] - Supporting detail that explains the feature,
provides a specific measurement or proof point, and addresses a common buyer concern.
```

### Bullet Point Strategy (5-Bullet Framework)

| Bullet | Focus | Purpose |
|--------|-------|---------|
| 1 | Primary benefit / USP | Hook the reader with the #1 reason to buy |
| 2 | Key feature / specification | Provide the technical detail power buyers need |
| 3 | Quality / materials / durability | Build trust and justify the price |
| 4 | Ease of use / convenience | Remove friction and objections |
| 5 | What's included / guarantee | Set expectations and reduce risk |

### Rules

- Each bullet should be 150-250 characters. Under 200 is ideal for mobile.
- Begin each bullet with a capitalized benefit phrase (acts as a scannable header).
- Integrate 1-2 secondary keywords per bullet naturally.
- Do not use HTML, special characters, or emojis (Amazon strips or penalizes these).
- Avoid repeating the same keyword across multiple bullets; distribute the keyword list.
- Address one specific buyer concern per bullet.
- Use specific numbers ("holds 32 oz", "lasts 12 hours") instead of vague claims
  ("large capacity", "long-lasting").

### Example Bullets (Wireless Earbuds)

```
1. CRYSTAL-CLEAR SOUND QUALITY - Custom 12mm dynamic drivers deliver deep bass and
   detailed highs so you hear every note during workouts and commutes.

2. 36-HOUR TOTAL BATTERY LIFE - Earbuds provide 8 hours per charge with 28 additional
   hours from the compact charging case. A 10-minute quick charge gives 90 minutes
   of playback.

3. SECURE FIT FOR ACTIVE USE - Three sizes of silicone ear tips and flexible ear hooks
   keep the earbuds locked in during running, gym workouts, and cycling. IPX5
   sweat and water resistant.

4. SEAMLESS BLUETOOTH 5.3 CONNECTION - Pairs instantly with iPhone and Android devices.
   Multipoint connection lets you switch between phone and laptop without re-pairing.

5. COMPLETE KIT INCLUDED - Package contains wireless earbuds, charging case, USB-C
   cable, 3 ear tip sizes (S/M/L), 2 ear hook sizes, quick start guide, and
   18-month manufacturer warranty.
```

---

## Product Description and A+ Content

### Standard Product Description

The standard description field supports up to 2000 characters of plain text. It appears
below the fold on the product detail page.

**Guidelines**:
- Use short paragraphs (2-3 sentences each).
- Reinforce key benefits not fully covered in bullets.
- Include 2-3 additional keywords naturally.
- Tell a brief brand or product story.
- End with a clear call to action or satisfaction guarantee statement.
- Do not use HTML tags (Amazon may strip them inconsistently).

### A+ Content (Enhanced Brand Content)

Available to Brand Registered sellers. Replaces the standard description with rich
media modules. A+ Content can increase conversion rate by 3-10%.

**Module Strategy (recommended layout)**:

| Position | Module Type | Content |
|----------|------------|---------|
| 1 | Brand header / logo banner | Establish brand identity |
| 2 | Product hero with feature highlights | Main product image with 3-4 callout icons |
| 3 | Comparison chart | Compare variants or compare to previous model |
| 4 | Feature deep-dive (image + text) | Expand on the #1 differentiating feature |
| 5 | Lifestyle banner | Full-width in-use image |
| 6 | Technical specifications table | Dimensions, materials, compatibility |
| 7 | Brand story / cross-sell | Link to other products in the catalog |

**A+ Content Rules**:
- Do not include pricing, promotional claims, or time-sensitive language.
- Do not reference competitor products by name.
- Use high-resolution images (minimum 970 px wide for full-width modules).
- Alt text on every image (accessibility and indexing).
- A+ Content text is not directly indexed by Amazon search, but it contributes to
  conversion rate which indirectly affects ranking.

### Premium A+ Content

Available to brands enrolled in the Brand Registry with a Brand Story. Adds
interactive modules: video, hover hotspots, carousel, and Q&A.

- Video module: up to 3 minutes, auto-plays on mute.
- Carousel module: up to 5 slides of image + text.
- Use Premium A+ to tell a richer product story and increase time on page.

---

## Backend Search Terms

Amazon provides a hidden search terms field (also called "generic keywords") that is
not visible to shoppers but is indexed for search ranking.

### Capacity

- **250 bytes** total (not characters). Standard ASCII characters = 1 byte each.
  Accented or CJK characters consume 2-3 bytes.
- Amazon ignores content beyond the byte limit entirely.

### What to Include

- Synonyms and alternate names not in the title or bullets.
- Common misspellings and abbreviations.
- Complementary use-case terms ("gift for dad", "office desk accessory").
- Spanish or other language translations if selling in the US market.
- Long-tail keyword phrases that did not fit in the title.
- Plural or singular forms not already present (Amazon handles some stemming but
  not all).

### What to Exclude

- Words already in the title (Amazon does not double-count; duplicates waste space).
- Brand names (yours is already indexed; competitor names are prohibited).
- ASINs or UPC codes.
- Subjective or promotional terms ("best", "cheapest", "amazing").
- Temporary statements ("new", "on sale now").
- Offensive or irrelevant terms.
- Commas (use spaces only; commas waste a byte and are not needed as separators).
- Quotation marks, semicolons, or other punctuation.

### Format

```
synonym1 synonym2 alternate-spelling use-case-term long tail phrase misspelling
```

All lowercase. Space-separated. No punctuation. No repetition of title words.

### Example

**Title**: "Anker USB-C Charger 65W Fast Charging - GaN III, Compact Foldable"

**Backend search terms**:
```
type c wall adapter power brick macbook pro charger laptop charger gan charger
usbc pd charger 65 watt cargador usb c travel charger slim portable phone charger
ipad charger galaxy charger pixel charger thunderbolt charging block power adapter
```

---

## Image Requirements

### Main Image

- **Background**: Pure white (RGB 255, 255, 255).
- **Product fill**: Product must occupy at least 85% of the image area.
- **No text, logos, badges, or watermarks** on the main image.
- **No props, accessories, or additional products** unless part of the listed item.
- **Minimum**: 1000 x 1000 px (enables zoom). Recommended: 2000 x 2000 px.
- **Format**: JPEG (.jpg) preferred. PNG and GIF accepted.
- **Color mode**: sRGB.

### Secondary Images (Slots 2-8)

Recommended 7-9 image strategy:

| Slot | Image Type | Description |
|------|-----------|-------------|
| 2 | Lifestyle / in-use | Product being used by target demographic |
| 3 | Infographic - features | 3-5 benefit callouts with icons and text |
| 4 | Scale and dimensions | Product with measurements or size reference |
| 5 | Infographic - how it works | Step-by-step usage or assembly |
| 6 | Close-up / material detail | Texture, build quality, craftsmanship |
| 7 | Package contents / what's included | Flat lay of everything in the box |
| 8 | Comparison or before/after | Show improvement or advantage |

### Video

- One video slot available. Up to 1 minute is typical.
- Show the product in use, demonstrate key features, and reinforce bullet points.
- Include captions (many shoppers watch on mute).
- Do not include pricing, promotional language, or external website URLs.

### Image Optimization Tips

- Use consistent lighting and color treatment across all images for a professional look.
- Design infographic text for mobile readability (minimum 24pt equivalent at 1000px width).
- Test images at mobile thumbnail size (approximately 150 x 150 px) to ensure the main
  image is recognizable.
- Seasonal images (holiday themes) can boost conversion during peak periods but must be
  swapped back after the season.

---

## Variation Strategy

Amazon variations (parent-child relationships) group related products on a single
detail page. Properly structured variations consolidate reviews and sales rank.

### Variation Types

| Variation Theme | Examples | Best For |
|----------------|----------|----------|
| Size | S, M, L, XL | Apparel, containers, furniture |
| Color | Black, White, Blue | Accessories, electronics, home decor |
| Size-Color | S-Black, M-Blue | Apparel with multiple options |
| Count/Quantity | 1-Pack, 3-Pack, 6-Pack | Consumables, multi-packs |
| Style | Modern, Classic, Vintage | Furniture, decor |
| Pattern | Solid, Striped, Floral | Textiles, apparel |

### When to Merge (Use Variations)

- Products are fundamentally the same item in different sizes or colors.
- Merging will consolidate review count (significant ranking advantage).
- Shoppers naturally expect to choose size/color on one page.
- The price range across variations is within 2-3x (e.g., $15 small to $35 large is fine).

### When to Keep Separate

- Products target different keywords or use cases.
- The price difference is extreme (a $10 item and a $200 item should not share a page).
- Products have different main images that would confuse shoppers if grouped.
- Each product has enough reviews to rank independently.

### Variation Best Practices

- The parent ASIN is a non-buyable placeholder; ensure it has a complete title and
  category assignment.
- Each child ASIN should have its own unique main image showing that specific variation.
- Bullet points can be shared or unique per child; customize where differences are
  meaningful (e.g., different size has different capacity spec).
- If adding a new variation to an existing listing, match the existing variation theme.
- Monitor for "variation abuse" flags; Amazon may split variations that do not
  logically belong together.

---

## Amazon SEO Signals

Amazon's A9/COSMO search algorithm ranks listings based on three signal categories:

### 1. Relevance Signals

How well the listing matches the search query.

| Signal | Impact | Optimization |
|--------|--------|-------------|
| Title keyword match | Very High | Primary keyword in first 80 characters |
| Bullet keyword match | High | Distribute secondary keywords across bullets |
| Backend search terms | Medium | Capture synonyms and long-tail phrases |
| Category / browse node | High | Use the most specific correct category |
| Product attributes | Medium | Fill all applicable attribute fields |

### 2. Performance Signals

How well the listing converts and sells.

| Signal | Impact | Optimization |
|--------|--------|-------------|
| Conversion rate (unit session %) | Very High | Optimize images, price, reviews, copy |
| Sales velocity | Very High | Drive initial sales via PPC and promotions |
| Click-through rate (CTR) | High | Main image quality, title clarity, price competitiveness |
| Best Seller Rank (BSR) | Medium | Sustained sales momentum |

### 3. Customer Satisfaction Signals

How well the product meets buyer expectations.

| Signal | Impact | Optimization |
|--------|--------|-------------|
| Review rating (stars) | High | Deliver quality; accurate listing sets right expectations |
| Review count | High | Use Amazon Vine, Request a Review, follow-up emails |
| Return rate | Medium | Accurate descriptions, size guides, clear images |
| A-to-Z claims | Medium | Responsive customer service, clear shipping |
| Seller account health | Low | Maintain metrics across the account |

### Ranking Flywheel

```
Better listing -> Higher CTR -> More sessions -> Higher conversion ->
More sales -> Better BSR -> Better organic rank -> More impressions -> (repeat)
```

PPC (Sponsored Products) jumpstarts this flywheel for new listings by driving
initial sessions and sales when organic rank is zero.

---

## Common Amazon Listing Mistakes

### Title Mistakes

- **Keyword stuffing**: Repeating the same keyword multiple times or cramming
  unrelated keywords. The algorithm does not reward repetition.
- **Exceeding character limits**: Amazon may suppress or truncate titles that exceed
  the category limit.
- **Missing brand name**: Required by style guide; omission can lead to listing
  suppression.
- **Promotional language in title**: Words like "Sale", "Discount", "Free Shipping"
  violate Amazon policy.
- **Ignoring mobile truncation**: Only the first 80 characters show on mobile; burying
  the primary keyword at position 150 means most shoppers never see it.

### Bullet Point Mistakes

- **Feature-only bullets**: "Made of silicone" tells the shopper nothing. "Made of
  food-grade silicone so it is safe for the dishwasher and will not stain" converts.
- **Too long**: Bullets over 300 characters are walls of text on mobile.
- **Too short**: Single-phrase bullets waste an opportunity to integrate keywords and
  address objections.
- **Using HTML or emojis**: Amazon inconsistently renders or strips these.

### Image Mistakes

- **Only 3-4 images**: Using fewer than 7 images leaves conversion on the table.
- **Non-white main image background**: Can trigger listing suppression.
- **Text unreadable on mobile**: Infographic text designed for desktop is illegible
  at mobile thumbnail size.
- **No lifestyle images**: Product-only shots fail to help the shopper envision ownership.

### Backend Mistakes

- **Duplicating title words**: Wastes the limited 250-byte space.
- **Using commas**: Commas consume bytes and are not needed; spaces suffice.
- **Including competitor brand names**: Violates Amazon policy and risks account
  suspension.
- **Exceeding byte limit**: Amazon ignores the entire field if it exceeds 250 bytes.

### Variation Mistakes

- **Grouping unrelated products**: Merging products that share no logical variation
  theme triggers Amazon to split them and can lead to policy warnings.
- **Missing child images**: All variations showing the same image confuses shoppers and
  increases returns.
- **Ignoring the parent listing**: A parent with no title or miscategorized browse node
  can suppress child visibility.

### Structural Mistakes

- **Wrong browse node / category**: Placing a product in the wrong category means it
  will not appear in filtered searches or browse results.
- **Empty product attributes**: Shoppers who filter by material, size, or feature will
  never see the listing if those attributes are blank.
- **No A+ Content when eligible**: Leaving the standard text description when A+ Content
  is available sacrifices 3-10% potential conversion uplift.

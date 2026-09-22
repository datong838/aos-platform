# FBA Inventory Management Playbook

A complete operational guide for managing inventory through Amazon's Fulfillment
by Amazon (FBA) program. This reference covers the full FBA lifecycle from
shipment creation to removal orders.

## Table of Contents

1. [FBA Shipment Creation Workflow](#1-fba-shipment-creation-workflow)
2. [Labeling Requirements](#2-labeling-requirements)
3. [Shipping to FBA](#3-shipping-to-fba)
4. [Inventory Performance Index (IPI) Management](#4-inventory-performance-index-ipi-management)
5. [Long-Term Storage Fee Avoidance](#5-long-term-storage-fee-avoidance)
6. [Stranded Inventory Resolution](#6-stranded-inventory-resolution)
7. [FBA Restock Limits and How to Optimize](#7-fba-restock-limits-and-how-to-optimize)
8. [Multi-Channel Fulfillment (MCF)](#8-multi-channel-fulfillment-mcf)
9. [Removal and Disposal Orders](#9-removal-and-disposal-orders)
10. [FBA New Selection Program](#10-fba-new-selection-program)

---

## 1. FBA Shipment Creation Workflow

### Step-by-Step Process

**Step 1: Prepare Your Inventory in Seller Central**

1. Navigate to Seller Central > Inventory > Manage FBA Inventory.
2. Select the SKUs you want to send to FBA.
3. Click "Send/Replenish Inventory" to start the shipment workflow.

**Step 2: Choose Shipping Plan**

Amazon's "Send to Amazon" workflow guides you through shipment creation:

1. **Set ship-from address:** Your supplier's address, your warehouse, or your
   3PL's address. This determines which FBA fulfillment centers Amazon assigns.
2. **Select packing type:**
   - Individual products: Each unit is a different SKU.
   - Case-packed products: Multiple units of the same SKU in one case.
3. **Enter quantities:** Input the number of units for each SKU.
4. **Confirm packing details:** Box dimensions, weight per box, number of boxes.

**Step 3: Review Shipment Splits**

Amazon may split your inventory across multiple fulfillment centers (FC).
Options:

- **Amazon-optimized shipment splits (default):** Amazon distributes inventory
  across FCs for fastest delivery. Lower per-unit fees but multiple
  destinations.
- **Minimal shipment splits:** Consolidates to fewer FCs. Amazon charges an
  inbound placement service fee for this convenience.

**Step 4: Print Labels and Ship**

1. Print box labels (unique to each shipment).
2. Print FNSKU labels if using merchant-fulfilled labeling.
3. Arrange carrier pickup or drop-off.
4. Enter tracking information in Seller Central.

**Step 5: Monitor Receiving**

Track shipment status in Seller Central > Shipments:
- **Shipped:** Carrier has the shipment.
- **Delivered:** FC received the shipment at the dock.
- **Checked in:** FC has started processing.
- **Receiving:** Units are being counted and stowed.
- **Closed:** All units received and available for sale.

Typical receiving timeline: 5-14 business days from delivery to available.
During Q4 peak season, expect 14-21+ days.

### Common Shipment Creation Errors

| Error | Cause | Fix |
|-------|-------|-----|
| "Exceeds restock limit" | Storage capacity exceeded for this storage type | Improve IPI score or wait for limit reset (weekly) |
| "ASIN not eligible for FBA" | Product category restricted or ASIN flagged | Check category approval requirements |
| "Hazmat review required" | Product flagged as potentially hazardous | Submit MSDS/SDS documentation |
| "Box weight exceeds 50 lb" | Individual box too heavy | Repack into smaller boxes |

---

## 2. Labeling Requirements

### FNSKU Labels (Product Labels)

**What:** FNSKU (Fulfillment Network Stock Keeping Unit) is a unique barcode
that links a specific product to your seller account.

**When required:** All FBA inventory must have an FNSKU label unless you opt
into commingled inventory (not recommended for most sellers).

**Specifications:**
- Format: Code 128A barcode
- Minimum size: 1" x 2" (25mm x 51mm)
- Recommended size: 1" x 3" (25mm x 76mm)
- Must include: FNSKU barcode, product title (truncated), condition
- Print on white, non-reflective labels
- Must cover any existing scannable barcodes on the product packaging

**Options for labeling:**
1. **Label yourself:** Print FNSKU labels from Seller Central and apply to
   each unit. Cost: ~$0.01-0.05 per label (label stock + printer).
2. **Supplier labels:** Send FNSKU label files to your supplier and have them
   apply during production or packing. Preferred for large orders.
3. **Amazon labeling service:** Amazon applies FNSKU labels at the FC for a
   per-unit fee (~$0.55/unit). Convenient but expensive at scale.
4. **3PL labeling:** Your prep center or 3PL applies labels. Typical cost:
   $0.15-0.30 per unit.

### Shipping Labels (Box Labels)

**What:** Unique labels generated for each box in a shipment, identifying the
destination FC and shipment contents.

**Requirements:**
- Print on full-sheet label paper or tape printed labels to box exterior.
- One label per box (on a flat surface, not a seam or edge).
- Must be scannable -- do not fold or crease.
- Do not reuse boxes with old FBA shipping labels (remove or cover old labels).

### Box Content Information

Amazon requires you to declare what is in each box. Three options:

1. **2D barcode on label (recommended):** Seller Central generates a label
   that encodes box contents. Fastest receiving.
2. **Manual entry in Seller Central:** Specify which SKUs and quantities are
   in each box via the web interface.
3. **Amazon counts at FC:** You skip box content info, but Amazon charges a
   manual processing fee and receiving is slower.

### Pallet Labels (for LTL/FTL Shipments)

If shipping palletized freight:
- 4 labels per pallet (one on each side).
- Pallet dimensions: max 40" x 48" standard.
- Max pallet height: 72" (including pallet).
- Max pallet weight: 1,500 lbs.
- Stretch wrap all pallets securely.

---

## 3. Shipping to FBA

### Option A: Amazon Partnered Carrier (APC)

Amazon negotiates discounted rates with UPS (small parcel) and various LTL
carriers.

**Advantages:**
- Discounted shipping rates (often 30-50% below retail rates)
- Integrated tracking in Seller Central
- Simplified claims process for lost/damaged shipments
- Voided shipments automatically handled

**When to use:**
- Shipping from a US address to US FBA
- Small parcel (individual boxes under 50 lbs)
- LTL palletized shipments within the US

**Process:**
1. Select "Amazon Partnered Carrier" during shipment creation.
2. Enter box dimensions and weights.
3. Accept the estimated shipping cost.
4. Print UPS labels (small parcel) or schedule LTL pickup.
5. Cost is charged to your seller account.

### Option B: Own Freight (Non-Partnered Carrier)

Use your own shipping account or freight forwarder.

**When to use:**
- Shipping internationally (from China/supplier country to US FBA)
- Have negotiated better rates with your own carrier
- Shipping to FBA in non-US marketplaces (EU, JP, AU)
- Oversized or heavy shipments where APC rates are not competitive

**Cross-Border FBA Shipping (China to US Example):**

1. **Supplier ships domestically** to your freight forwarder's warehouse in
   China (Shenzhen, Yiwu, Shanghai).
2. **Freight forwarder handles:**
   - Export customs declaration (China side)
   - Ocean freight (18-30 days) or air freight (5-10 days)
   - Import customs clearance (US side, using your IOR/importer of record)
   - Duty payment (based on HS code and declared value)
   - Last-mile delivery to FBA fulfillment center(s)
3. **You provide the freight forwarder with:**
   - FBA shipping labels and destination FC addresses
   - Commercial invoice with product details and declared values
   - Packing list with box dimensions and weights
   - Any required compliance documents (FCC, CPSIA, etc.)

**Shipping Cost Benchmarks (China to US FBA, 2024-2025):**

| Method | Transit Time | Cost per kg (approx) | Best For |
|--------|-------------|---------------------|----------|
| Express air (DHL/FedEx/UPS) | 3-5 days | $6-12 | Urgent restocks < 100 kg |
| Standard air freight | 7-12 days | $4-7 | Medium urgency, 100-500 kg |
| Fast sea (express LCL) | 15-20 days | $2-4 | Balanced speed/cost |
| Standard sea (LCL) | 25-35 days | $1-2.50 | Cost-optimized bulk |
| Full container (FCL) | 25-35 days | $0.50-1.50 | High volume (5+ CBM) |

**Note:** Rates fluctuate based on fuel surcharges, peak season, and carrier
availability. Always get 3+ quotes from freight forwarders.

### Shipping Best Practices

- **Never ship all inventory in one shipment.** Split into 2-3 shipments on
  different vessels to reduce risk of total loss.
- **Insure high-value shipments.** Cargo insurance typically costs 0.3-0.5%
  of declared value. Worth it for shipments above $10,000.
- **Pad your timeline.** Add 1 week buffer to every transit estimate. Port
  congestion, weather, and customs delays are normal.
- **Pre-clear customs.** Work with your freight forwarder to file customs
  documentation before the shipment arrives at the US port.

---

## 4. Inventory Performance Index (IPI) Management

### What Is IPI?

The Inventory Performance Index is Amazon's composite score (0-1000) measuring
how efficiently you manage FBA inventory. Amazon updates the score weekly.

### IPI Score Thresholds

| Score Range | Status | Impact |
|------------|--------|--------|
| 0-399 | Poor | Storage limits imposed, higher storage fees |
| 400-549 | Fair | Standard storage limits |
| 550-799 | Good | Expanded storage limits |
| 800-1000 | Excellent | Maximum storage capacity |

### IPI Components and Optimization

**Component 1: Excess Inventory Percentage**

- **What:** Percentage of units Amazon considers overstocked (projected to take
  longer than 90 days to sell at current velocity).
- **Weight:** High
- **How to improve:**
  - Run promotions on excess units (coupons, deals, price reductions).
  - Create removal orders for units with no path to profitable sell-through.
  - Stop sending inventory for slow-moving SKUs until existing stock sells down.
  - Use the "Manage Excess Inventory" tool in Seller Central for recommendations.

**Component 2: Sell-Through Rate**

- **What:** Units sold and shipped over the past 90 days divided by average
  units in FBA during that period.
- **Weight:** High
- **How to improve:**
  - Optimize listings (better images, keywords, A+ content).
  - Increase advertising spend on products with available inventory.
  - Lower prices on slow-moving items to increase velocity.
  - Avoid sending too much inventory relative to sales velocity.

**Component 3: Stranded Inventory Percentage**

- **What:** Percentage of inventory in FBA without an active listing.
- **Weight:** Medium
- **How to improve:**
  - Check stranded inventory report daily.
  - Fix listing errors within 24 hours.
  - Set up Stranded Inventory Auto-Removal in settings (auto-creates removal
    orders for inventory stranded > 30 days).

**Component 4: In-Stock Rate**

- **What:** Percentage of time your replenishable FBA SKUs are in stock.
- **Weight:** Medium
- **How to improve:**
  - Maintain consistent replenishment for top-selling SKUs.
  - Use Amazon's restock recommendations as a baseline.
  - Factor in longer lead times during peak season.

### IPI Recovery Plan (If Score < 400)

1. **Week 1:** Remove all excess inventory with < 30 days of projected
   sell-through. Fix all stranded inventory listings.
2. **Week 2-4:** Run aggressive promotions on remaining excess. Focus
   advertising on high-velocity SKUs to boost sell-through rate.
3. **Week 4-8:** Monitor weekly IPI updates. Score typically improves 50-100
   points within 4-6 weeks if excess inventory is reduced and sell-through
   increases.
4. **Ongoing:** Set alerts for IPI drops below 500. Review excess inventory
   report weekly.

---

## 5. Long-Term Storage Fee Avoidance

### Fee Structure

Amazon charges long-term storage fees (LTSF) on inventory stored in FBA for
extended periods. Fees are assessed on the 15th of each month.

| Storage Duration | Fee (per cubic foot) | Fee (per unit) | Charged |
|-----------------|---------------------|---------------|---------|
| 271-365 days | $6.90 | $0.15 | Whichever is greater |
| 365+ days | $6.90 | $0.15 | Whichever is greater |

**Note:** These fees are IN ADDITION to regular monthly storage fees ($0.87/cf
Jan-Sep, $2.40/cf Oct-Dec for standard size).

### LTSF Avoidance Strategy

**Prevention (Best Approach):**

1. **Track inventory age daily.** Use the Inventory Age report in Seller
   Central or download via SP-API.
2. **Set internal alerts:**
   - Day 60: Review sell-through trajectory. If below plan, start promotions.
   - Day 90: Escalate. Consider removal if promotion is not working.
   - Day 150: Final decision -- liquidate, remove, or accept LTSF.
3. **Right-size initial shipments.** Never send more than 60-75 days of supply
   to FBA unless you have high confidence in sell-through rate.
4. **Use the Inventory Age tool** in Seller Central to identify units
   approaching 271 days.

**Removal Before LTSF Hits:**

- Create removal orders by the 14th of the month (LTSF assessed on 15th).
- Removal typically takes 10-14 business days to process.
- Start the removal process at day 200 to ensure units are out before day 271.

**Cost Comparison (Remove vs. Pay LTSF):**

| Action | Cost per Unit | When to Choose |
|--------|--------------|---------------|
| Removal to your address | $0.97-1.04 | Units have resale value elsewhere |
| Removal to 3PL | $0.97-1.04 + 3PL fee | Plan to sell on other channels |
| Liquidation | ~90% loss of value | Units have minimal resale value |
| Pay LTSF | $0.15+ per month | Units will sell within 30 days |
| Disposal | $0.15-0.30 | Units have zero value |

---

## 6. Stranded Inventory Resolution

### What Is Stranded Inventory?

Inventory stored in FBA that cannot be sold because it lacks an active,
buyable listing. You pay storage fees on stranded inventory but earn zero
revenue.

### Common Causes and Fixes

| Cause | Identification | Resolution |
|-------|---------------|------------|
| Listing suppressed (missing info) | Suppressed Listings report | Add required product details (images, descriptions, compliance) |
| Listing suppressed (policy violation) | Account Health Dashboard | Address the specific policy violation cited |
| ASIN deleted | Stranded Inventory report shows "No active listing" | Recreate the listing or open a case with Seller Support |
| Listing closed by seller (accidental) | Manage Inventory shows "Closed" status | Relist by clicking "Relist" in Manage Inventory |
| IP complaint | Account Health > Intellectual Property | File counter-notice or contact rights owner |
| Pricing error | Pricing alerts | Adjust price to acceptable range |
| Brand mismatch | Brand Registry conflict | Verify brand ownership, update brand info |
| Safety complaint | Product Safety alerts | Provide documentation proving compliance |

### Stranded Inventory Resolution Workflow

```
Step 1: Check Stranded Inventory report (daily)
  |
  +--> Seller Central > Inventory Planning > Fix Stranded Inventory
  |
Step 2: Identify cause for each stranded ASIN
  |
  +--> Click "Edit" next to stranded ASIN to see reason
  |
Step 3: Fix the listing issue
  |
  +--> Missing info    --> Add required attributes and images
  +--> Suppressed      --> Address compliance issue, submit documentation
  +--> Deleted         --> Open Seller Support case to reinstate
  +--> IP complaint    --> Counter-notice or remove problematic content
  |
Step 4: Verify listing is active
  |
  +--> Check "Active" status in Manage Inventory
  +--> Verify the listing is buyable (search for ASIN on Amazon)
  |
Step 5: If unfixable within 14 days, create removal order
  |
  +--> Do not let inventory sit stranded for 30+ days
  +--> Amazon may dispose of stranded inventory after extended periods
```

### Prevention

- Set up **automatic fixes** in Seller Central > Inventory Planning > Stranded
  Inventory Settings. Amazon can auto-relist inventory when common issues are
  detected.
- Monitor Account Health Dashboard daily for new suppression notices.
- Keep backup product images, compliance documents, and listing content
  accessible for quick resubmission.

---

## 7. FBA Restock Limits and How to Optimize

### How Restock Limits Work

Amazon sets per-storage-type capacity limits that cap how many cubic feet of
inventory you can have in FBA at any time (in-stock + inbound + receiving).

**Storage types:**
- Standard-size
- Oversize
- Apparel
- Footwear
- Flammable (hazmat)
- Aerosol

**Limit calculation factors:**
- IPI score (higher score = higher limits)
- Sales volume and velocity
- Historical sell-through rate
- Available FC capacity (varies by season)

### How to Check Your Limits

Seller Central > Inventory Performance > Restock Limits

The dashboard shows:
- **Maximum shipment quantity:** Total units you can have in FBA + in transit.
- **Current utilization:** Units currently in FBA + inbound.
- **Available capacity:** Room for additional shipments.

### Optimization Strategies

**Strategy 1: Improve IPI Score**

The single most impactful lever. See Section 4 above. Every 100-point IPI
improvement typically increases restock limits by 15-30%.

**Strategy 2: Remove Non-Performing Inventory**

Every excess unit occupies capacity that could hold a fast-selling SKU.
Aggressively remove inventory with < 30 days projected sell-through to free
capacity for better products.

**Strategy 3: Increase Sales Velocity**

Amazon rewards sellers who sell through inventory quickly. Higher velocity leads
to higher limits over time.

- Increase ad spend on products with available inventory.
- Run promotions to boost sell-through rate.
- Optimize listings to improve organic conversion rate.

**Strategy 4: Use AWD (Amazon Warehousing and Distribution)**

AWD is Amazon's upstream storage solution. Inventory in AWD does not count
against FBA restock limits. AWD automatically replenishes FBA based on your
sales velocity.

- **Cost:** $0.56/cubic foot/month (lower than FBA storage).
- **Benefit:** Bypass FBA restock limits entirely.
- **Limitation:** Slower replenishment to FBA (2-5 days transfer time).
- **Best for:** Bulk inventory storage when FBA limits are constraining.

**Strategy 5: Ship Little and Often**

Instead of one large shipment per month, send 2-4 smaller shipments. This
keeps FBA inventory lean and maximizes available capacity utilization.

**Strategy 6: Request Capacity Increase**

Amazon periodically offers sellers the ability to request additional capacity
via the Capacity Manager in Seller Central. You bid a reservation fee per
cubic foot. If your bid is accepted, you get additional capacity. The
reservation fee is refunded as you sell through inventory.

---

## 8. Multi-Channel Fulfillment (MCF)

### What Is MCF?

Multi-Channel Fulfillment allows you to use FBA inventory to fulfill orders
from non-Amazon channels (your Shopify store, eBay, Walmart, TikTok Shop,
etc.).

### When to Use MCF

- You sell on multiple platforms and want centralized fulfillment.
- Your non-Amazon channel volume does not justify a separate 3PL.
- You want to leverage FBA's delivery speed for off-Amazon orders.

### MCF Pricing (US, Standard-Size)

| Delivery Speed | Per Unit Fee (approx) |
|---------------|----------------------|
| Standard (3-5 days) | $4.50-6.00 |
| Expedited (2-3 days) | $5.50-8.00 |
| Priority (1-2 days) | $8.00-12.00 |

Fees vary by product size/weight. Check the current FBA fee schedule for
exact rates.

### MCF Workflow

```
Step 1: Receive order on external channel (Shopify, eBay, etc.)
  |
Step 2: Create MCF order
  +--> Manual: Seller Central > Orders > Create Multi-Channel Fulfillment Order
  +--> Automated: Use integration (Shopify FBA app, Sellbrite, ChannelAdvisor)
  |
Step 3: Amazon picks, packs, and ships from FBA inventory
  |
Step 4: Tracking number provided -- share with customer on external channel
  |
Step 5: Customer receives delivery in unbranded (or optionally branded) box
```

### MCF Considerations

- **Branding:** MCF orders ship in unbranded Amazon boxes by default. You
  can opt into blank boxes (no Amazon branding) for an additional fee.
- **Returns:** MCF does not handle returns. You must manage return logistics
  separately (accept returns at your address or a 3PL).
- **Blocked channels:** Amazon previously blocked MCF for certain competitor
  marketplaces. Check current MCF policies for your target channels.
- **Inventory allocation:** MCF orders draw from the same FBA inventory pool
  as Amazon orders. Ensure you account for MCF volume in your restock
  planning to avoid stockouts on Amazon.

---

## 9. Removal and Disposal Orders

### When to Create Removal Orders

- Inventory approaching 271 days in FBA (LTSF avoidance).
- Stranded inventory that cannot be relisted.
- Seasonal products at end of season.
- Products being discontinued.
- Damaged or defective units flagged by Amazon.
- Inventory in wrong marketplace (cannot be transferred cross-border).

### Removal Order Types

**Return to Seller:**
- Units shipped back to your address.
- Fee: $0.97-1.04 per standard-size unit; $3.12-7.13 per oversize unit.
- Transit time: 10-14 business days.
- You receive units and can resell on other channels, donate, or recycle.

**Return to 3PL:**
- Same as above but shipped to your 3PL's address.
- Useful for redistributing to other channels without handling inventory
  yourself.

**Liquidation:**
- Amazon sells units to wholesale liquidators through the FBA Liquidations
  program.
- You receive approximately 5-10% of your average selling price.
- No removal fee -- Amazon handles everything.
- Processing time: 30-60 days.

**Disposal:**
- Amazon disposes of (destroys) units at the FC.
- Fee: $0.15-0.30 per standard-size unit; $0.30-1.00 per oversize unit.
- Use only when units have zero resale value and removal shipping cost exceeds
  unit value.

### Creating Removal Orders

**Manual (Individual SKU):**
1. Seller Central > Inventory > Manage FBA Inventory.
2. Select SKU(s) to remove.
3. Click "Action" > "Create Removal Order."
4. Choose: Return to address / Liquidate / Dispose.
5. Enter quantity and confirm.

**Bulk (Multiple SKUs):**
1. Seller Central > Inventory > Removal Order.
2. Download removal order template.
3. Fill in SKUs, quantities, and disposition.
4. Upload completed template.

**Automated:**
- Set up automatic removal rules in Seller Central for inventory exceeding
  a specified age threshold.
- Example: Auto-remove units stored > 250 days.

### Tracking Removal Orders

Seller Central > Orders > Removal Order Detail

Statuses:
- **Pending:** Order submitted, waiting for processing.
- **Processing:** FC is picking units.
- **Shipped:** Units in transit to your address.
- **Completed:** Units delivered (return) or processed (liquidation/disposal).
- **Cancelled:** Order was cancelled before processing.

---

## 10. FBA New Selection Program

### What Is It?

Amazon's FBA New Selection program offers fee incentives for new-to-FBA ASINs
to encourage sellers to expand their FBA catalog.

### Benefits (Subject to Change -- Verify Current Terms)

- **Free monthly storage** for a limited number of units per eligible ASIN
  (typically first 50-100 units for up to 90 days).
- **Free liquidation** for unsold new-to-FBA inventory (no liquidation fees).
- **Free removals** for a limited quantity.
- **Discounted inbound shipping** via Amazon Partnered Carrier for the first
  shipment.

### Eligibility

- Parent ASIN must be new to FBA (never previously sent to FBA by any seller).
- Professional selling plan required.
- Account must be in good standing.
- Product must not be in a restricted or gated category.
- Some categories may be excluded (check program terms).

### How to Enroll

1. Seller Central > Growth > FBA New Selection.
2. Review eligible ASINs (Amazon auto-identifies qualifying products).
3. Enroll eligible ASINs with one click.
4. Send first shipment within the program window (typically 90 days from
   enrollment).

### Strategic Use

- **Test new products with reduced risk.** The free storage and liquidation
  benefits reduce the downside of a new product that does not sell well.
- **Pair with a small initial order.** Send 30-50 units of a new product to
  validate demand before committing to a large order.
- **Stack with launch promotions.** Combine New Selection benefits with
  coupons, Vine reviews, and PPC campaigns for a cost-efficient launch.
- **Monitor expiration.** Benefits expire after 90 days or when unit limits
  are exceeded. Set a calendar reminder to review sell-through before benefits
  expire.

---

## Quick Reference: FBA Checklist for New Shipments

- [ ] Product FNSKU labels printed and applied (covering original barcodes)
- [ ] Box content information entered in Seller Central
- [ ] Box dimensions and weights accurate
- [ ] Shipping labels printed and affixed to boxes
- [ ] No old labels on reused boxes (removed or covered)
- [ ] Hazmat documentation submitted (if applicable)
- [ ] Carrier selected (APC or own freight)
- [ ] Tracking entered in Seller Central
- [ ] Estimated receiving date factored into inventory plan
- [ ] Restock limit capacity confirmed before shipping

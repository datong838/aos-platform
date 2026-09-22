# Customs and Import Duties Guide

Comprehensive reference for cross-border e-commerce customs clearance,
import duty calculation, documentation requirements, and country-specific
regulations.

## Table of Contents

1. [HS Code Classification](#1-hs-code-classification)
2. [Import Duty Calculation](#2-import-duty-calculation)
3. [De Minimis Thresholds by Country](#3-de-minimis-thresholds-by-country)
4. [Required Documentation](#4-required-documentation)
5. [Common Restricted and Prohibited Items](#5-common-restricted-and-prohibited-items)
6. [Country-Specific Requirements](#6-country-specific-requirements)
7. [Customs Broker Selection](#7-customs-broker-selection)
8. [Common Customs Delays and How to Avoid Them](#8-common-customs-delays-and-how-to-avoid-them)
9. [Anti-Dumping Duties and Safeguard Measures](#9-anti-dumping-duties-and-safeguard-measures)

---

## 1. HS Code Classification

The Harmonized System (HS) code is the universal classification system for
traded goods. Every product you import must have the correct HS code. Getting
it wrong results in wrong duty rates, customs holds, penalties, or seizure.

### HS Code Structure

```
Chapter  Heading  Subheading  National suffix
  XX   .   XX   .   XX     .   XX XX
  |        |        |          |
  |        |        |          Country-specific (varies)
  |        |        6-digit: international standard
  |        4-digit: product group
  2-digit: product category

Example: 9503.00.00.90
  95 = Toys, games, sports equipment
  9503 = Tricycles, scooters, pedal cars and similar wheeled toys
  9503.00 = (subheading)
  .00.90 = US national suffix
```

The first 6 digits are internationally harmonized. Digits 7-10 are
country-specific. Always use the destination country's tariff schedule
to determine the full code.

### How to Find the Correct HS Code

**Step 1: Start with the product's primary material and function.**
HS codes classify by what a product IS and what it DOES, not what it is
called commercially.

**Step 2: Use official tariff lookup tools.**

| Country | Tariff Lookup Tool | URL |
|---------|-------------------|-----|
| US | USITC Harmonized Tariff Schedule | hts.usitc.gov |
| EU | TARIC Database | ec.europa.eu/taxation_customs/dds2/taric |
| UK | UK Trade Tariff | trade-tariff.service.gov.uk |
| Australia | Australian Customs Tariff | ftaportal.dfat.gov.au |
| Japan | Japan Customs Tariff | customs.go.jp |
| Canada | CBSA Customs Tariff | cbsa-asfc.gc.ca/trade-commerce/tariff-tarif |

**Step 3: Cross-reference with similar products.**
Search for similar products that have been imported previously. Customs
ruling databases show how specific products were classified.

**Step 4: When uncertain, get a binding ruling.**
Most customs authorities offer binding tariff classification rulings. This
takes 4-12 weeks but gives you legal certainty. The ruling is binding on
customs officers for the specific product described.

### Common HS Code Mistakes

| Mistake | Example | Consequence |
|---------|---------|-------------|
| Using origin country code | CN HS code used for US import | Wrong duty rate applied |
| Classifying by brand name | "iPhone case" is not an HS category | Must classify by material + function |
| Ignoring material composition | Plastic container vs glass container | Different chapters, different duty rates |
| Using outdated codes | HS codes update every 5 years | Rejected filing, delays |
| Guessing similar product | "It's like a widget" | Customs may reclassify and charge penalties |

### HS Code Best Practices

- Maintain an HS code master list for all your SKUs
- Have your customs broker verify codes before first shipment
- Review codes annually (HS revisions occur regularly)
- Keep product spec sheets (material, function, dimensions) to support
  classification decisions
- Document your classification reasoning for audit defense

---

## 2. Import Duty Calculation

Import duties are calculated on the customs value of goods, which in most
countries is the CIF (Cost, Insurance, Freight) value.

### Basic Duty Calculation Formula

```
Customs Value (CIF) = Product cost + International freight + Insurance

Import Duty = Customs Value x Duty Rate (%)

Total Import Taxes = Import Duty + VAT/GST on (Customs Value + Import Duty)
                   + Any additional taxes (excise, consumption, etc.)
```

### Example Calculation (US Import)

```
Product: LED desk lamps from China
HS Code: 9405.42 (electric lamps and lighting)
Unit cost (FOB): $8.00
Quantity: 5,000 units
Total FOB value: $40,000
Ocean freight: $2,000
Insurance: $200

CIF Value: $40,000 + $2,000 + $200 = $42,200
Duty Rate: 3.9% (normal MFN rate)
Import Duty: $42,200 x 3.9% = $1,645.80

Section 301 tariff (if applicable): $42,200 x 7.5% = $3,165.00
Total Duty: $1,645.80 + $3,165.00 = $4,810.80

Duty per unit: $4,810.80 / 5,000 = $0.96 per unit

Note: US does not charge VAT. State sales tax applies at point of sale.
```

### Example Calculation (EU Import)

```
Product: Silicone kitchen utensils from China
HS Code: 3924.10 (tableware and kitchenware of plastics)
Unit cost (FOB): $2.50
Quantity: 10,000 units
Total FOB value: $25,000
Ocean freight: $1,800
Insurance: $150

CIF Value: $25,000 + $1,800 + $150 = $26,950
Duty Rate: 6.5%
Import Duty: $26,950 x 6.5% = $1,751.75

VAT Base: $26,950 + $1,751.75 = $28,701.75
VAT (Germany 19%): $28,701.75 x 19% = $5,453.33

Total Import Taxes: $1,751.75 + $5,453.33 = $7,205.08
Tax per unit: $7,205.08 / 10,000 = $0.72 per unit
```

### Duty Rate Sources by Country

| Country/Region | Rate Type | Typical Range | Where to Check |
|---------------|-----------|--------------|---------------|
| US | MFN (Column 1) | 0-25% | hts.usitc.gov |
| US | Section 301 (China) | 7.5-25% additional | ustr.gov |
| EU | MFN (Common Customs Tariff) | 0-17% | TARIC database |
| UK | UK Global Tariff | 0-16% | trade-tariff.service.gov.uk |
| Australia | General rate | 0-10% | Australian Customs Tariff |
| Japan | MFN rate | 0-15% | Japan Customs |
| Canada | MFN rate | 0-18% | CBSA Tariff |

### Special Duty Programs

- **GSP (Generalized System of Preferences)**: reduced or zero-duty rates
  for qualifying goods from developing countries. Check eligibility by
  HS code and origin country. Note: US GSP for China products is largely
  suspended.
- **Free Trade Agreements (FTAs)**: preferential rates if goods qualify
  under specific FTAs. Requires certificate of origin.
- **Foreign Trade Zones / Bonded Warehouses**: defer duty payment until
  goods enter domestic commerce. Useful for cross-border sellers who may
  re-export some inventory.

---

## 3. De Minimis Thresholds by Country

De minimis is the value below which imports are duty-free and/or tax-free.
Critical for direct-to-consumer (DTC) cross-border sellers shipping
individual parcels.

| Country | Duty-Free Threshold | Tax-Free Threshold | Notes |
|---------|-------------------|--------------------|-------|
| **US** | $800 | $800 | Highest in the world; covers most DTC parcels |
| **Canada** | CAD $20 (duty), CAD $40 (tax) | CAD $40 | Very low; most parcels incur duty + GST |
| **EU** | EUR 150 (duty) | EUR 0 (VAT always applies since July 2021) | IOSS required for VAT collection at sale |
| **UK** | GBP 135 (duty) | GBP 0 (VAT always applies) | Seller must register for UK VAT for parcels under GBP 135 |
| **Australia** | AUD $1,000 | AUD $1,000 | Generous threshold for DTC |
| **Japan** | JPY 10,000 (~$67) | Included in duty threshold | Low threshold; most parcels incur duties |
| **Singapore** | SGD $400 | SGD $400 | Relatively generous |
| **South Korea** | $150 | Included | Moderate threshold |
| **Mexico** | $50 | $50 | Very low; duties apply to most imports |
| **Brazil** | $50 | $50 (via Remessa Conforme) | Recently reduced; very complex customs |

### De Minimis Strategy for DTC Sellers

- **US market**: the $800 de minimis makes direct-from-China DTC viable for
  most products. Ship individual parcels via express or postal service.
- **EU/UK market**: IOSS/UK VAT registration is mandatory for sellers shipping
  parcels valued under EUR 150/GBP 135. VAT is collected at checkout and
  remitted by the seller.
- **Australia**: AUD $1,000 threshold makes DTC shipping attractive; GST
  applies above this threshold but is collected by platform for orders under
  AUD $1,000 (marketplace facilitator rule).

---

## 4. Required Documentation

Every commercial import requires a set of core documents. Missing or
incorrect documents cause delays and additional costs.

### Core Documents

| Document | Purpose | Who Prepares | Critical Fields |
|----------|---------|-------------|----------------|
| **Commercial Invoice** | States the value and terms of sale | Seller/exporter | Seller/buyer names, product description, HS code, quantity, unit price, total value, currency, Incoterms, country of origin |
| **Packing List** | Details physical contents of each package | Seller/exporter | Carton numbers, dimensions, weights (gross/net), contents per carton, total cartons |
| **Bill of Lading (BOL)** | Contract of carriage (sea); title document | Shipping line/forwarder | Shipper, consignee, notify party, port of loading/discharge, container number, seal number |
| **Airway Bill (AWB)** | Contract of carriage (air) | Airline/forwarder | Shipper, consignee, airport of departure/arrival, weight, dimensions |
| **Certificate of Origin** | Proves where goods were manufactured | Chamber of Commerce or exporter | Must match origin claimed for duty purposes; required for FTA preferential rates |

### Supplementary Documents (as required)

| Document | When Required |
|----------|-------------|
| **FDA Prior Notice** | Food, beverages, dietary supplements, cosmetics entering US |
| **CPSC Certificate** | Children's products entering US |
| **FCC Declaration** | Electronic devices entering US |
| **CE Declaration of Conformity** | Products sold in EU (most manufactured goods) |
| **REACH SVHC Declaration** | Chemical-containing products entering EU |
| **Phytosanitary Certificate** | Wood packaging, plant-based products |
| **Fumigation Certificate** | Wood packaging (ISPM 15 compliance) |
| **MSDS/SDS** | Products containing chemicals, batteries |
| **Lab Test Reports** | Products requiring safety testing (toys, electronics, textiles) |
| **Import License** | Certain controlled goods (varies by country) |
| **Textile Labeling Certificate** | Apparel and textiles (fiber content, care labels) |

### Document Consistency Rule

All documents for a single shipment must match exactly:

- Product descriptions must be identical across invoice, packing list, and BOL
- Quantities must reconcile (invoice qty = packing list total qty)
- Values must be consistent (invoice total = declared customs value)
- Weights must align (packing list gross weight ~ BOL weight)
- Shipper/consignee names and addresses must match across all documents

**A single discrepancy triggers customs examination.** Review all documents
as a set before shipping.

---

## 5. Common Restricted and Prohibited Items

Every country restricts certain product categories. These restrictions range
from outright bans to requiring specific permits or certifications.

### US Restricted/Regulated Items

| Category | Regulating Agency | Requirements |
|----------|------------------|-------------|
| Food and beverages | FDA | Prior notice, facility registration, food labeling compliance |
| Cosmetics | FDA | Ingredient labeling, no banned ingredients |
| Drugs/supplements | FDA | Strict manufacturing standards, NDI notification for new ingredients |
| Electronics | FCC | FCC ID or SDoC for radio-frequency devices |
| Children's products | CPSC | CPSIA testing (lead, phthalates), tracking labels, CPC certificate |
| Textiles | CPSC/FTC | Flammability testing, fiber content labeling |
| Laser products | FDA/CDRH | Performance standards, variance reports |
| Pesticides | EPA | EPA registration required |
| Alcohol | TTB | Federal importer permit, state licenses |
| Tobacco | TTB/FDA | Federal permit, health warnings |
| Firearms/weapons | ATF | Import permit, prohibited for most cross-border sellers |

### EU Restricted/Regulated Items

| Category | Regulation/Directive | Requirements |
|----------|---------------------|-------------|
| Most manufactured goods | CE Marking Directives | CE mark + Declaration of Conformity |
| Electronics | EMC Directive, LVD, RoHS | Testing, technical documentation |
| Toys | Toy Safety Directive (EN 71) | Third-party testing, CE marking |
| Cosmetics | EU Cosmetics Regulation | Safety assessment, CPNP notification, responsible person in EU |
| Food contact materials | Regulation 1935/2004 | Migration testing, declaration of compliance |
| Chemicals | REACH | SVHC screening, registration for volumes >1 ton/year |
| Electrical waste | WEEE Directive | Producer registration, recycling fee |
| Batteries | Batteries Directive | Collection/recycling scheme, labeling |
| Packaging | Packaging Directive / EPR | Extended Producer Responsibility registration per country |
| Textiles | Textile Regulation | Fiber composition labeling |

### Australia Restricted Items

| Category | Regulating Agency | Requirements |
|----------|------------------|-------------|
| Electronics/radio | ACMA | Compliance mark or supplier's declaration |
| Therapeutic goods | TGA | Registration or listing on ARTG |
| Food | FSANZ | Food Standards Code compliance |
| Cosmetics | NICNAS/AICIS | Industrial chemical assessment |
| Biosecurity risk items | DAWE | Biosecurity import conditions, inspection |

### SEA Market Restrictions (varies by country)

| Country | Notable Restrictions |
|---------|-------------------|
| **Indonesia** | SNI certification for many product categories; halal certification for food/cosmetics; import license (API) required |
| **Thailand** | TISI standards for electronics; FDA Thailand for food/cosmetics/medical devices |
| **Vietnam** | Quality inspection for specific goods; CFS for food imports |
| **Philippines** | BPS certification for electronics; FDA Philippines for food/drugs |
| **Malaysia** | SIRIM certification for electronics; halal certification for food |

---

## 6. Country-Specific Requirements

### United States

**Regulatory agencies and their scope:**

| Agency | Products Covered | Key Requirements |
|--------|-----------------|-----------------|
| **FDA** | Food, drugs, cosmetics, medical devices | Facility registration, prior notice (food), labeling compliance, GMP |
| **CPSC** | Consumer products, especially children's | CPSIA testing, CPC or GCC certificates, tracking labels |
| **FCC** | Electronic devices with radio frequency | FCC ID (intentional radiators) or SDoC (unintentional radiators) |
| **EPA** | Pesticides, chemical products | EPA registration, proper labeling |
| **USDA** | Animal products, plants | APHIS permits, inspection |

**Import bond requirements:**
- Single Entry Bond: for one-time or infrequent imports; typically 100% of
  duty value
- Continuous Bond: for frequent importers (10+ entries/year); minimum $50,000;
  covers all entries for 12 months
- Required for all commercial imports valued over $2,500

**Section 301 tariffs (China-specific):**
- Lists 1-4A: 25% additional duty on billions in Chinese goods
- List 4B: 7.5% additional duty
- Check specific HS codes against USTR exclusion lists
- Some exclusions granted (temporary); verify current status before shipping

**ISF (Importer Security Filing / "10+2"):**
- Required for all ocean shipments to US
- Must be filed 24 hours before vessel departure from origin
- Late or inaccurate ISF: $5,000 penalty per violation
- Your customs broker or forwarder typically files this

### European Union

**CE Marking:**
- Required for most manufactured products sold in the EU
- Not a quality mark; indicates conformity with EU health, safety, and
  environmental requirements
- Seller (importer) is responsible for ensuring compliance
- Requires: technical documentation, Declaration of Conformity, CE mark
  on product and packaging
- Applicable directives vary by product type (LVD, EMC, RoHS, Toy Safety,
  Machinery, PPE, etc.)

**REACH (Registration, Evaluation, Authorisation, Restriction of Chemicals):**
- Applies to all products containing chemicals (nearly everything)
- SVHC (Substances of Very High Concern) screening required
- If product contains SVHC above 0.1% by weight, must notify ECHA and
  inform buyers
- Enforcement increasing; non-compliance leads to market withdrawal

**WEEE (Waste Electrical and Electronic Equipment):**
- Applies to all electrical and electronic products
- Seller must register as a producer in each EU country where they sell
- Must finance collection and recycling of e-waste
- Registration per country; can use compliance schemes (take-back services)
- Penalties for non-registration: product recalls and fines

**EPR (Extended Producer Responsibility) for Packaging:**
- Requires registration and reporting of packaging placed on market
- Applies in DE, FR, ES, IT, AT, and expanding to other EU countries
- Must register with national packaging compliance scheme
- Germany: VerpackG requires Lucid registration
- France: CITEO registration for packaging

**EU VAT:**
- Standard rates: 17-27% depending on member state
- IOSS (Import One-Stop Shop): simplified VAT filing for imports under EUR 150
- OSS (One-Stop Shop): simplified VAT for intra-EU sales
- If selling via Amazon, Marketplace Facilitator rules may apply (Amazon
  collects and remits VAT)

### United Kingdom

**Post-Brexit changes:**
- UKCA marking replaces CE marking for most products (transition periods vary)
- Separate UK customs declarations required (not covered by EU entry)
- UK Global Tariff replaced EU Common Customs Tariff
- GB-NI Protocol: different rules for Northern Ireland (still follows EU rules)

**UK VAT:**
- Standard rate: 20%
- For consignments valued at GBP 135 or less: seller collects VAT at point
  of sale and remits to HMRC
- For consignments over GBP 135: VAT charged at import (buyer or importer pays)
- UK VAT registration required if goods are stored in UK before sale
- Amazon UK is a Marketplace Facilitator: collects/remits VAT for non-UK sellers

**UK Conformity Assessment:**
- UKCA mark required for most products (CE mark accepted during transition)
- UK Authorised Representative required for non-UK manufacturers
- Technical documentation must be available in English

### Australia

**ACMA (Australian Communications and Media Authority):**
- Compliance mark required for electrical and radio communications products
- Responsible Supplier Declaration (RSD) for most products
- Formal approval for high-risk equipment (radio transmitters)

**Therapeutic goods:**
- Regulated by TGA (Therapeutic Goods Administration)
- Products making health claims must be listed or registered on ARTG
- Includes: supplements, medical devices, some cosmetics with therapeutic claims

**Biosecurity:**
- Australia has strict biosecurity controls
- Wood packaging must comply with ISPM 15 (heat treatment/fumigation)
- Certain materials (straw, bamboo, seeds) require pre-clearance
- Random biosecurity inspections can add 3-7 days

**GST (Goods and Services Tax):**
- 10% GST on most imported goods
- For imports under AUD $1,000: GST collected by marketplace (if sold through
  a platform) or by the seller (if sold direct)
- For imports over AUD $1,000: GST collected at border by customs

### Japan

**PSE (Product Safety Electrical Appliance and Materials):**
- Required for electrical products sold in Japan
- Diamond PSE: specific high-risk products (requires third-party testing)
- Circle PSE: other electrical products (self-declaration with testing)
- Testing to Japanese standards (often different from IEC/EN standards)

**Food Sanitation Act:**
- All food, food additives, food containers, and utensils require compliance
- Notification to quarantine station required before import
- Inspection may include laboratory testing (5-10 business days)
- Japanese language labeling required

**JIS (Japanese Industrial Standards):**
- Voluntary for most products but expected by Japanese consumers
- JIS compliance demonstrates quality commitment
- Some government procurement requires JIS compliance

**Japan Customs:**
- Generally efficient clearance (1-3 business days if documents are correct)
- Strict on documentation accuracy
- Country of origin labeling strictly enforced
- Consumption tax: 10% (food items: 8%)

---

## 7. Customs Broker Selection

A customs broker files entry documents and manages clearance with customs
authorities on your behalf. In many countries, only licensed brokers can
file entries.

### Broker Evaluation Criteria

| Criterion | What to Assess | Minimum Standard |
|-----------|---------------|-----------------|
| **License** | Valid customs broker license in destination country | Must be currently licensed and in good standing |
| **Experience** | Years in business, e-commerce client portfolio | 5+ years, 10+ active e-commerce clients |
| **Specialization** | Knowledge of your product category and its regulations | Familiar with your specific product type and HS codes |
| **Technology** | Electronic filing, tracking portal, automated alerts | EDI/ABI capability, online status tracking |
| **Communication** | Response time, proactive updates on holds or issues | Same-day response, proactive notification of exceptions |
| **Error rate** | Historical accuracy of filings | <1% error rate on classifications and values |
| **Pricing** | Per-entry fee, additional charges, hidden costs | Transparent fee schedule; typical US entry: $100-$200 |
| **ISF filing** | Ability to file ISF/10+2 for ocean shipments (US) | Included in service, filed on time |
| **Scalability** | Can handle your growth without service degradation | Ask about capacity and current client load |

### When to Use Your Forwarder's Broker vs Independent Broker

| Scenario | Recommendation |
|----------|---------------|
| Standard products, simple classification | Forwarder's broker is fine |
| Regulated products (FDA, CPSC, CE) | Independent broker with category expertise |
| High-value shipments (>$100K) | Independent broker with audit defense experience |
| Frequent imports (weekly+) | Dedicated broker relationship with volume pricing |
| New HS codes or first-time product import | Independent broker; get a binding ruling |

### Broker Red Flags

- Cannot explain HS code classification decisions
- Files entries with "catch-all" or overly generic HS codes
- Does not proactively inform you of regulatory changes
- Charges excessive "miscellaneous" or "government" fees with no breakdown
- History of penalty assessments with customs
- Unresponsive during customs holds (when you need them most)

---

## 8. Common Customs Delays and How to Avoid Them

### Top Causes of Customs Delays

| Cause | Typical Delay | How to Prevent |
|-------|-------------|---------------|
| **Incorrect HS code** | 5-15 business days (reclassification + possible exam) | Get binding ruling; have broker verify before shipping |
| **Missing documentation** | 3-10 business days | Use document checklist; verify completeness before departure |
| **Value discrepancy** | 5-20 business days (value audit) | Declare accurate values; keep purchase orders as proof |
| **Random examination** | 3-7 business days | Cannot prevent; budget for it in timeline (2-5% of shipments) |
| **FDA hold** | 5-30 business days | File prior notice on time; ensure labeling compliance |
| **CPSC hold** | 7-21 business days | Have CPC/GCC certificates ready; ensure testing is current |
| **Incomplete ISF** | Penalty + possible exam | File ISF 48+ hours before vessel departure |
| **Origin marking violation** | 3-10 business days | Ensure "Made in [Country]" on product and packaging |
| **Anti-dumping investigation** | 10-60 business days (deposit required) | Check AD/CVD orders for your HS code before importing |
| **Intellectual property detention** | 5-30 business days | Verify you have rights to import the brand; avoid counterfeits |

### Timeline Buffer Recommendations

| Shipment Type | Normal Clearance | Buffer for Delays | Total Planning Time |
|--------------|-----------------|-------------------|-------------------|
| Sea freight (standard goods) | 2-5 business days | +7 business days | 7-12 business days |
| Sea freight (regulated goods) | 5-10 business days | +14 business days | 14-24 business days |
| Air freight (standard goods) | 1-3 business days | +5 business days | 4-8 business days |
| Express courier (under de minimis) | 0-1 business days | +2 business days | 1-3 business days |
| First-time importer (any mode) | 5-10 business days | +14 business days | 14-24 business days |

### Pre-Clearance Checklist

Complete this checklist before your shipment departs origin:

- [ ] HS code verified against destination country tariff schedule
- [ ] Duty rate confirmed (including any special tariffs: Section 301, AD/CVD)
- [ ] All required certifications obtained and copies ready to submit
- [ ] Commercial invoice complete with all required fields
- [ ] Packing list matches invoice (quantities, descriptions, weights)
- [ ] Bill of lading/airway bill details match invoice and packing list
- [ ] Certificate of origin prepared if claiming preferential duty rate
- [ ] ISF filed (US ocean shipments) at least 24 hours before departure
- [ ] FDA prior notice filed (US food/cosmetics) before arrival
- [ ] Import bond in place (US) or duty payment method arranged
- [ ] Customs broker notified with full document package
- [ ] Product labeling complies with destination country requirements

---

## 9. Anti-Dumping Duties and Safeguard Measures

Anti-dumping (AD) and countervailing duties (CVD) are additional tariffs
imposed on specific products from specific countries when those products are
sold below fair market value or benefit from government subsidies.

### How Anti-Dumping Duties Work

1. Domestic industry files petition claiming foreign goods are "dumped" at
   below-market prices
2. Government agency investigates (US: DOC/ITC; EU: European Commission)
3. If dumping is confirmed and domestic industry is harmed, AD duty is imposed
4. AD duty rates can range from 5% to over 300%
5. AD orders last 5 years, renewable indefinitely

### Current High-Impact AD/CVD Orders (China-origin)

| Product Category | US AD/CVD Rate Range | EU AD/CVD Rate Range |
|-----------------|---------------------|---------------------|
| Steel products | 20-500%+ | 15-85% |
| Aluminum products | 15-375% | 15-50% |
| Solar panels/cells | 15-250% | 0-50% (measures expired for some) |
| Wooden furniture | 5-300% | N/A |
| Ceramic tile | 100-400% | 30-70% |
| Quartz surface products | 300%+ | N/A |
| Cast iron cookware | 5-80% | N/A |
| Electric bikes | N/A | 18-79% |

### How to Check for AD/CVD Orders

**US:**
- Search the DOC AD/CVD order database at enforcement.trade.gov
- Enter your HS code and country of origin
- Check both existing orders and active investigations

**EU:**
- Search the Official Journal of the EU for trade defense measures
- Check ec.europa.eu/trade/policy/accessing-markets/trade-defence

### Impact on Cross-Border Sellers

- AD/CVD duties are charged IN ADDITION to normal customs duties
- If your product is subject to AD/CVD, the total duty can make it uneconomical
- Cash deposit required at import; final rate determined after annual review
- Evasion (transshipping through third countries to avoid AD duty) is illegal
  and heavily penalized
- If you discover your product is subject to AD/CVD after importing, you cannot
  avoid the duty retroactively

### Safeguard Measures

Safeguard measures are temporary tariffs imposed on surges of imports that
cause injury to domestic industry, regardless of whether dumping or subsidies
are involved.

- Typically broader than AD/CVD (apply to all countries, not just one)
- US Section 201 and Section 301 tariffs are types of safeguard measures
- Time-limited but can be extended
- Check current measures before committing to a product/route

### Best Practice

Before committing to any product import, check:

1. Is this HS code subject to AD/CVD orders from my origin country?
2. Are there active investigations that could result in new orders?
3. What is the cash deposit rate currently required?
4. Are there any safeguard measures (Section 201, Section 301, EU safeguards)?
5. Can I source from an alternative country to avoid these duties?

If AD/CVD duties apply, model the total landed cost with and without these
duties. Many products become unviable with AD/CVD, and sellers who ignore
this discover the problem only when their goods are held at customs with a
demand for a massive cash deposit.

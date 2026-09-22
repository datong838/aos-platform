---
name: risk-management
description: >
  Use when assessing business risks, planning for account suspension scenarios,
  diversifying supply chain, creating contingency plans, evaluating insurance
  needs, or responding to active crises in cross-border e-commerce operations.
---

# Risk Management

Skill type: Pattern (risk matrices and decision trees)

Identify, assess, and mitigate risks across every layer of a cross-border
e-commerce business. This skill provides structured frameworks for proactive
risk planning and rapid crisis response so that a single point of failure
never becomes a business-ending event.

## Core Principle

Hope is not a strategy. For every critical dependency (single supplier, single
account, single market), there must be a documented contingency plan. The time
to build the backup is when you do not need it.

Every seller who operates long enough will face an account suspension, a
shipment seizure, a supplier default, or a demand collapse. The difference
between sellers who survive and those who do not is preparation executed before
the crisis arrives.

---

## Risk Assessment Matrix

Evaluate each risk category on two axes:

- **Likelihood**: Low (< 10%), Medium (10-40%), High (> 40%)
- **Impact**: Low (< 5% revenue), Medium (5-20% revenue), High (> 20% revenue)

Priority = Likelihood x Impact. Address High/High first, then High/Medium and
Medium/High, and so on.

### 1. Account Risk

| Risk | Likelihood | Impact | Priority |
|---|---|---|---|
| Primary account suspension | Medium | Critical | **Highest** |
| Listing suppression (IP complaint) | High | Medium | High |
| Review manipulation penalty | Medium | High | High |
| Policy violation warning | High | Low | Medium |
| Account verification delay | Low | Medium | Low |

Mitigation summary: multi-account strategy (compliant), brand registry,
proactive policy monitoring, clean review practices.

### 2. Supply Chain Risk

| Risk | Likelihood | Impact | Priority |
|---|---|---|---|
| Primary supplier default | Medium | Critical | **Highest** |
| Quality defect batch | High | High | **Highest** |
| Factory shutdown (government/COVID) | Low | Critical | High |
| Raw material price spike | Medium | Medium | Medium |
| Supplier capacity constraint | Medium | Medium | Medium |

Mitigation summary: dual sourcing, pre-shipment inspection, safety stock,
geographic diversification.

### 3. Financial Risk

| Risk | Likelihood | Impact | Priority |
|---|---|---|---|
| Cash flow crunch (slow reimbursement) | High | High | **Highest** |
| Currency fluctuation loss | High | Medium | High |
| Tariff/duty rate increase | Medium | High | High |
| Payment processor hold | Low | High | Medium |
| Tax audit / compliance penalty | Low | Medium | Low |

Mitigation summary: cash reserves (minimum 3 months opex), hedging, landed
cost buffer, multi-processor setup.

### 4. Logistics Risk

| Risk | Likelihood | Impact | Priority |
|---|---|---|---|
| Customs seizure / hold | Medium | High | High |
| Carrier delay (port congestion) | High | Medium | High |
| Warehouse damage / loss | Low | High | Medium |
| Last-mile delivery failure spike | Medium | Medium | Medium |
| Shipping cost surge (peak season) | High | Low | Medium |

Mitigation summary: compliant documentation, multi-carrier strategy,
cargo insurance, buffer lead times.

### 5. Market Risk

| Risk | Likelihood | Impact | Priority |
|---|---|---|---|
| Demand collapse (trend shift) | Medium | Critical | **Highest** |
| New competitor undercutting price | High | Medium | High |
| Negative viral review / PR event | Low | High | Medium |
| Seasonal demand miscalculation | Medium | Medium | Medium |
| Market saturation | Medium | Medium | Medium |

Mitigation summary: diversified product portfolio, brand moat, sentiment
monitoring, conservative seasonal forecasting.

### 6. Platform Risk

| Risk | Likelihood | Impact | Priority |
|---|---|---|---|
| Platform fee increase | High | Medium | High |
| Algorithm change (ranking drop) | High | Medium | High |
| Platform policy change | Medium | Medium | Medium |
| Platform market exit (region) | Low | High | Medium |
| API / integration breaking change | Low | Low | Low |

Mitigation summary: multi-platform presence, own-channel development (DTC),
policy change monitoring, adaptable listing strategy.

---

## The "What If" Checklist

For every critical dependency, answer these four questions and document the
answers. Review quarterly.

### Template

```
DEPENDENCY: [Name the dependency]
CATEGORY:   [Account / Supplier / Logistics / Financial / Platform / Market]

1. WHAT IF IT FAILS?
   Describe the failure scenario in concrete terms.
   Example: "Our sole supplier in Shenzhen stops production for 30+ days."

2. HOW LONG CAN WE SURVIVE?
   Calculate runway in days/weeks based on current inventory, cash, and
   alternative capacity.
   Example: "Current FBA stock covers 18 days of sales at current velocity."

3. WHAT IS THE BACKUP?
   Name the specific alternative: backup supplier, second account, reserve
   cash, alternative logistics route.
   Example: "Secondary supplier in Dongguan (qualified, MOQ negotiated,
   sample approved, not yet ordered)."

4. HOW FAST CAN THE BACKUP ACTIVATE?
   Measure in days from decision to first deliverable result.
   Example: "First PO to delivery: 21 days. Gap: 3 days uncovered."
```

### Critical Dependencies to Assess

Run the checklist for each of these:

- [ ] Primary selling account (per platform)
- [ ] Top supplier (by revenue contribution)
- [ ] Primary freight forwarder / logistics partner
- [ ] Primary payment / payout channel
- [ ] Top 3 SKUs (by revenue share)
- [ ] Primary warehouse / fulfillment center
- [ ] Key staff / contractors with irreplaceable knowledge
- [ ] Domain, hosting, and software subscriptions
- [ ] Banking and financial institution relationships

---

## Account Risk Mitigation

### Multi-Account Considerations

Operating multiple seller accounts is permitted on some platforms under
specific conditions and prohibited on others. Approach with full compliance.

**Amazon**: Multiple accounts require legitimate business justification and
separate legal entities. Amazon actively detects linked accounts through
IP address, browser fingerprint, bank account, tax ID, and behavioral
patterns. Violations result in suspension of all linked accounts.

Compliant approaches:
- Separate legal entities with distinct EINs / tax IDs
- Separate bank accounts per entity
- Separate physical addresses and internet connections
- Distinct product catalogs (no overlapping ASINs)
- Document the business justification

**Shopee / Lazada**: Generally one account per phone number / ID.
Multi-store features available in some markets. Check current local policy.

**TikTok Shop**: One shop per business license in most markets. Some markets
allow multiple shops under one entity.

### Brand Registry as Protection

Brand registry provides a defensive moat:
- Report IP violations against your listings
- Access to enhanced content tools
- Higher listing trust score
- Easier reinstatement path if suspended
- Protection against hijackers

Register your brand on every platform where you sell. Maintain trademark
registrations in every jurisdiction where you operate.

---

## Supply Chain Diversification Strategy

### The 2-1-1 Rule

For any SKU contributing more than 15% of revenue:

- **2** qualified suppliers who can produce the item
- **1** backup supplier in a different geographic region
- **1** documented alternative product that serves the same customer need

### Supplier Tier Framework

| Tier | Role | Share of Volume | Requirements |
|---|---|---|---|
| Primary | Main production | 60-70% | Full audit, contract, insurance |
| Secondary | Overflow + backup | 20-30% | Audit, sample approved, MOQ agreed |
| Emergency | Last resort | 0% (standby) | Sample approved, pricing agreed, no commitment |

### Geographic Diversification Targets

Do not concentrate all sourcing in one country. Maintain qualified suppliers
in at least two of these regions:

- **China** (Shenzhen, Yiwu, Dongguan): largest variety, mature export infra
- **Vietnam**: competitive labor costs, growing export capacity
- **India**: textiles, handicrafts, pharmaceuticals, IT hardware
- **Turkey**: textiles, home goods, proximity to EU
- **Mexico**: proximity to US, USMCA benefits
- **Thailand / Indonesia**: electronics assembly, natural products

See `references/supply-chain-risk.md` for detailed framework.

---

## Financial Risk Management

### Cash Reserve Targets

| Business Stage | Minimum Cash Reserve |
|---|---|
| Launch (0-6 months) | 4 months of total operating expenses |
| Growth (6-18 months) | 3 months of total operating expenses |
| Established (18+ months) | 2 months of total operating expenses + credit facility |

Operating expenses include: inventory reorders, shipping, platform fees,
advertising, payroll, SaaS subscriptions, and loan payments.

### Insurance Checklist

- [ ] Cargo / marine insurance (covers in-transit loss or damage)
- [ ] Product liability insurance (required by Amazon and most platforms)
- [ ] Business interruption insurance
- [ ] Trade credit insurance (covers buyer / platform default)
- [ ] Cyber / data breach insurance (if handling customer data directly)

### Currency Hedging

For sellers with significant exposure to non-home currencies:

- Use forward contracts to lock exchange rates on large purchase orders
- Maintain multi-currency accounts (Payoneer, Wise, OFX) to time conversions
- Price products with a currency buffer (3-5% margin above break-even FX rate)
- Review FX exposure monthly; hedge when exposure exceeds 20% of monthly revenue

---

## Crisis Response Playbooks

### Playbook 1: Account Suspended

**Timeline: First 24 Hours**

1. Do NOT panic-submit an appeal. Read the suspension notice carefully.
2. Identify the exact reason code and policy cited.
3. Preserve all evidence: download order data, listing data, correspondence.
4. Assess financial exposure: pending payouts, FBA inventory value.
5. Notify team and pause all advertising spend on the account.
6. Begin drafting Plan of Action (see `references/account-health.md`).

**Timeline: Days 2-7**

7. Submit Plan of Action with root cause, corrective actions, and preventive
   measures.
8. Activate backup account if available and compliant.
9. Redirect traffic from external channels to backup listings.
10. Monitor appeal response; prepare escalation path.

**Timeline: Days 7-30**

11. If first appeal denied, revise POA addressing specific feedback.
12. Escalate to executive seller support or legal channels.
13. Evaluate long-term impact: liquidate FBA inventory if reinstatement
    unlikely.
14. Document lessons learned and update preventive checklist.

### Playbook 2: Shipment Seized at Customs

**Timeline: First 48 Hours**

1. Contact freight forwarder for seizure notice details.
2. Identify the reason: documentation error, prohibited item, IP claim,
   regulatory non-compliance.
3. Gather all shipping documents: commercial invoice, packing list, HS codes,
   certificates, test reports.
4. Engage customs broker to file response / protest.
5. Assess inventory impact: calculate days of stock remaining.

**Timeline: Days 3-14**

6. Provide requested documentation to customs authority.
7. If IP claim: contact rights holder, provide proof of authorization.
8. Activate alternative inventory (backup warehouse, different port).
9. Expedite replacement shipment via air if critical.
10. Update compliance documentation to prevent recurrence.

### Playbook 3: Supplier Default

**Timeline: First 48 Hours**

1. Confirm the default: communicate directly, verify through local contacts.
2. Assess current inventory position across all warehouses.
3. Calculate runway: days of stock at current sales velocity.
4. Contact secondary supplier, place emergency order.
5. Evaluate whether to reduce advertising to slow sales velocity.

**Timeline: Days 3-14**

6. Negotiate with emergency (Tier 3) supplier if secondary cannot cover gap.
7. Adjust pricing if needed to manage demand while supply recovers.
8. Update FBA restock limits and expectations.
9. Communicate delays to customers if fulfillment is affected.
10. Source samples from new suppliers to replace defaulted supplier permanently.

### Playbook 4: Demand Collapse

**Timeline: First 7 Days**

1. Verify the signal: distinguish temporary dip from structural decline.
2. Check external factors: competitor launch, algorithm change, seasonal shift,
   negative press.
3. Reduce advertising spend to limit loss on declining ROAS.
4. Audit listing for suppression, review changes, or buy box loss.
5. Poll customers / analyze reviews for sentiment shifts.

**Timeline: Days 7-30**

6. If structural: liquidate excess inventory (deals, outlet, B2B, liquidation).
7. Redirect budget to better-performing SKUs or markets.
8. Test repositioning: new keywords, images, pricing, bundles.
9. Evaluate product lifecycle: sunset if recovery is unlikely.
10. Document the pattern for future product selection screening.

---

## Risk Review Cadence

### Quarterly Risk Review (90 minutes)

**Agenda:**

1. **Risk register update** (20 min) -- Review each category in the risk matrix.
   Update likelihood and impact ratings based on current data.

2. **"What If" checklist refresh** (20 min) -- For each critical dependency,
   verify the backup is still valid. Check: is the secondary supplier still
   operating? Is the backup account in good standing? Is the cash reserve at
   target level?

3. **Incident review** (15 min) -- Review any risk events that materialized
   since last review. What worked? What failed? Update playbooks.

4. **Emerging risks** (15 min) -- Scan for new risks: regulatory changes,
   platform policy updates, geopolitical shifts, competitor moves.

5. **Action items** (20 min) -- Assign owners and deadlines for mitigation
   tasks identified in steps 1-4.

### Monthly Quick Checks (15 minutes)

- Review account health dashboards across all platforms
- Check supplier communication and order status
- Verify cash reserve balance against target
- Scan platform policy change announcements
- Review insurance coverage expiration dates

---

## Red Flags

Stop and reassess immediately when any of these conditions is true:

- **Single account dependency**: More than 80% of revenue flows through one
  seller account with no backup strategy documented.

- **Single supplier dependency**: One supplier produces more than 70% of your
  inventory by value and no secondary supplier is qualified.

- **Cash reserve below minimum**: Cash on hand covers less than 30 days of
  operating expenses.

- **No product liability insurance**: Selling physical products without
  product liability coverage in the destination market.

- **Compliance gaps**: Operating without required certifications, licenses,
  or documentation for your product category.

- **No customs documentation backup**: Original shipping documents exist in
  only one location with no copies or digital backups.

- **Ignored account health warnings**: Platform account health metrics in
  yellow/warning zone for more than 14 days without corrective action.

- **Key person risk**: One individual holds all supplier relationships,
  account credentials, or operational knowledge with no documentation or
  cross-training.

- **Concentration in one market**: More than 85% of revenue from a single
  country or platform with no expansion plan.

- **Untested contingency plans**: Playbooks exist on paper but have never
  been rehearsed or partially activated.

---

## Cross-References

RELATED: cbec-ops:platform-compliance, cbec-ops:supplier-sourcing, cbec-ops:order-fulfillment, cbec-ops:financial-management

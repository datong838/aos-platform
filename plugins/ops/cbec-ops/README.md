# CBEC-OPS: Cross-Border E-Commerce Operations Skills

A comprehensive AI agent skills suite for cross-border e-commerce operations, covering the full seller lifecycle from market research to multi-platform expansion.

## Skills Overview

### Phase 1: Discover
- **market-research** - Evaluate and rank target markets before committing resources
- **product-selection** - Find and validate winning products with data-driven scoring

### Phase 2: Source
- **supplier-sourcing** - Find, vet, and negotiate with manufacturers and wholesalers
- **pricing-strategy** - Calculate landed costs and set profitable prices

### Phase 3: Launch
- **product-listing** - Create optimized listings across platforms (Amazon, Shopee, TikTok Shop)
- **inventory-management** - Plan stock levels, reorder points, and FBA/3PL operations
- **order-fulfillment** - Manage shipping, customs, and last-mile delivery

### Phase 4: Grow
- **advertising-marketing** - Run PPC campaigns, social media, and influencer marketing
- **customer-service** - Handle reviews, returns, and dispute resolution
- **brand-building** - Register brands, protect IP, and build brand equity

### Phase 5: Optimize
- **data-analytics** - Track KPIs, run A/B tests, diagnose performance issues
- **financial-management** - Manage P&L, cash flow, taxes, and currency risk

### Phase 6: Protect & Expand
- **platform-compliance** - Stay compliant with platform policies, handle suspensions
- **risk-management** - Identify risks, create contingency plans, respond to crises
- **seasonal-planning** - Prepare for peak seasons with inventory, ads, and listing optimization
- **multi-platform-expansion** - Evaluate and execute expansion to new platforms

## Usage

Install as a Claude Code plugin to enable AI-assisted cross-border e-commerce operations.

## Architecture

Built following the [superpowers](https://github.com/obra/superpowers) skills pattern:
- Each skill has a `SKILL.md` with YAML frontmatter (name + description)
- Reference files in `references/` for detailed data and templates
- Progressive disclosure: core workflow in SKILL.md, details loaded on demand
- Flat namespace: all skills equally discoverable

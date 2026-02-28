**One-liner:** We decompose the full cost of delivering any product (physical or SaaS) so you can see unit economics and arbitrage across regions, channels, or components.

---

**Pricing arbitrage — any product with a price**

**What it is**  
An agent that visits live sites (retail, marketplaces, SaaS pricing pages) and extracts every **cost component** of delivering that product — not just list price, but shipping, duties, add-ons, regional tiers, etc. You get normalized unit economics; then you arb (US vs intl, region vs region, or by component).

**Physical / shipping**  
- Unit price, shipping cost, duties, fulfillment or minimum order.  
- Example: *Hosui Chojuro pears* — US retail price vs same (or equivalent) from intl source + shipping; output = US price, intl price, shipping, total landed, margin.  
- Same flow for any SKU: the agent finds where it’s sold, extracts the components, and you compare.

**SaaS / digital**  
- Base price, per-seat or usage tiers, add-ons, regional pricing, tax/VAT, currency.  
- Example: US list vs EU/rest-of-world list + tax; or breakdown by tier so you see where the margin sits (e.g. enterprise vs SMB).

**Output**  
Structured rows per product: product/id, region or source, each component (price, shipping, tax, etc.), total delivered cost, and derived margin or arb opportunity. Use this to rank opportunities or feed a pricing strategy.

**Why an agent**  
Many sites have no API, anti-scrape, or dynamic/geo pricing. The agent uses a real browser (and optionally geo/proxy) to see what a user in that region sees, then extracts and normalizes — so you get component-level unit economics instead of a single headline number.

---

QA testing + swarm of browser agents. They all have different personas (test if they would even use your product, a conversion rate from your landing page). Then, they test bottlenecks in your product.

Tech
use orchestrator claude + browser use subagents. retries and self healing.
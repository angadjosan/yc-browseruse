**One-liner:** We find prices live on the web, spot when there’s a cheaper option or mismatch, and give ecommerce providers the unit economics to dropship or arb — for any product, physical or SaaS.

**In short:** You set an AI-powered pricing alert — when there's a cheaper option or a mismatch (e.g. intl + shipping &lt; US retail), you get notified.

---

**Pricing arbitrage — any product with a price**

**What it is**  
An agent that visits **live** sites (retail, marketplaces, SaaS pricing pages) and extracts every **cost component** of delivering that product — not just list price, but shipping, duties, add-ons, regional tiers, etc. You see when there’s a cheaper option or a mismatch (e.g. US vs intl + shipping). Ecommerce providers use this to **dropship** or arb: list where the margin is, source where it’s cheaper. Same idea for SaaS (regional/tier mismatches).

**Physical / shipping**  
- Unit price, shipping cost, duties, fulfillment or minimum order.  
- We find prices **live**; when there’s a mismatch (e.g. intl + shipping &lt; US retail), ecommerce providers can dropship — sell in one market, fulfill from the cheaper source.  
- Example: *Hosui Chojuro pears* — US retail price vs same (or equivalent) from intl source + shipping; output = US price, intl price, shipping, total landed, margin.  
- Same flow for any SKU: the agent finds where it’s sold, extracts the components, and you compare.

**SaaS / digital**  
- Base price, per-seat or usage tiers, add-ons, regional pricing, tax/VAT, currency.  
- Example: US list vs EU/rest-of-world list + tax; or breakdown by tier so you see where the margin sits (e.g. enterprise vs SMB).

**Output**  
Structured rows per product: product/id, region or source, each component (price, shipping, tax, etc.), total delivered cost, and derived margin or arb opportunity. Use this to rank opportunities or feed a pricing strategy.

**Why an agent**  
Many sites have no API, anti-scrape, or dynamic/geo pricing. The agent uses a real browser (and optionally geo/proxy) to see what a user in that region sees, then extracts and normalizes — so you get component-level unit economics instead of a single headline number.



4) “Logged-in Research Agent” for procurement / pricing intelligence
What it does: Logs into competitor dashboards or vendor portals, extracts key pricing/features, diffs weekly, alerts.
Why it wins: “no more brittle scraping” + recurring value.
Sponsor usage
Browser Use: login + extraction
Convex: scheduled monitoring + diff store
Laminar: trace + extraction proof
HUD: eval: “field extraction accuracy”
Vercel: timeline UI of changes
Demo moment: “We caught a pricing change behind login and generated a one-pager for sales.”

---
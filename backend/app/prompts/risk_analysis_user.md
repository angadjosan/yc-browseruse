Perform a compliance risk assessment for this product.

## PRODUCT URL
{product_url}

## PRODUCT INFORMATION
{product_info}

## ANALYSIS INSTRUCTIONS

### Step 1: Product Feature Extraction
First, identify the product's key compliance-relevant features:
- What data does it collect? (personal data, financial data, health data, children's data?)
- How does it process that data? (storage, analytics, AI/ML, sharing with third parties?)
- Who are its users? (consumers, businesses, specific industries?)
- Where does it operate? (US-only, EU, global? which specific states/countries?)
- What integrations does it have? (third-party services, APIs, data imports/exports?)

### Step 2: Regulatory Mapping
For each feature identified above, map it to specific regulatory obligations. Use the trigger pattern:
"[Feature X] → [creates obligation Y] → [under regulation Z, specifically article/section N]"

### Step 3: Deduplication and Prioritization
Remove any risks that:
- Overlap with another risk you've already identified (keep the more specific one)
- Cannot be tied to a specific product feature
- Apply to every company generally (e.g., "pay taxes") rather than this product specifically

### Step 4: Output

Return ONLY a JSON array. No markdown, no explanation, no preamble. Start with [ and end with ].

Each risk object:
```
{{
  "regulation_title": "Specific regulation name and article/section",
  "risk_category": "DATA_PRIVACY|SECTOR_SPECIFIC|CONSUMER_PROTECTION|ACCESSIBILITY|SECURITY_STANDARDS|AI_GOVERNANCE|CONTENT_MODERATION|INTERNATIONAL_TRADE",
  "risk_rationale": "This product [specific feature] which [specific data handling] which triggers [specific requirement]. [1-2 more sentences on concrete exposure].",
  "product_features_affected": ["feature 1", "feature 2"],
  "jurisdiction": "Specific jurisdiction (e.g., 'EU', 'California, US', 'United Kingdom')",
  "scope": "What aspects of the product are affected",
  "source_url": "https://official-government-source.gov/specific-page",
  "check_interval_seconds": 86400,
  "initial_search_query": "Specific search query to find current regulation text and recent amendments",
  "monitoring_focus": "What specific part of the regulation page to watch for changes"
}}
```

Target 5-8 risks. Quality over quantity — each risk must pass the false-positive checklist.
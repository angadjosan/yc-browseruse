"""Product analysis service: extracts product info and generates compliance risks.

Workflow:
1. Use browser-use agent to extract product information from landing page
2. Use Claude to analyze product and generate list of compliance risks
3. Create watches for each identified risk
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from app.config import get_config
from app.services.watch_service import WatchService

logger = logging.getLogger(__name__)


class ProductAnalyzer:
    """Analyzes product pages and generates compliance risk watches."""

    def __init__(self):
        self.config = get_config()
        self.watch_service = WatchService()
        self._anthropic = None

    def _get_anthropic(self):
        if self._anthropic is None and self.config.get("anthropic_api_key"):
            from anthropic import Anthropic
            self._anthropic = Anthropic(api_key=self.config["anthropic_api_key"])
        return self._anthropic

    async def analyze_product_url(
        self,
        product_url: str,
        organization_id: str,
    ) -> Dict[str, Any]:
        """Main workflow: analyze product, generate risks, create watches.

        Returns:
            Dict with:
                - product_info: extracted product information
                - risks: list of identified risks
                - watches: list of created watch objects
        """
        logger.info(f"Starting product analysis for URL: {product_url}")

        # Step 1: Extract product information using browser-use
        product_info = await self.extract_product_info(product_url)
        if not product_info or not product_info.get("content"):
            raise ValueError("Failed to extract product information from URL")

        # Step 2: Generate compliance risks using Claude
        risks = await self.generate_risk_analysis(product_info, product_url)
        if not risks:
            raise ValueError("Failed to generate compliance risk analysis")

        # Step 3: Create watches for each risk
        watches = await self.create_watches_from_risks(risks, organization_id, product_url)

        return {
            "product_info": product_info,
            "risks": risks,
            "watches": watches,
        }

    async def extract_product_info(self, product_url: str) -> Dict[str, Any]:
        """Step 1: Use browser-use agent to extract product information.

        Uses the custom browser-use model to navigate the product page and
        extract use cases and relevant information.
        """
        from browser_use import Agent, Browser, ChatBrowserUse, Tools, ActionResult

        extracted_data: Dict[str, str] = {}
        tools = Tools()

        @tools.action("Save the extracted product information")
        async def save_product_info(content: str) -> ActionResult:
            extracted_data["content"] = content
            return ActionResult(extracted_content=content)

        task_prompt = f"""Navigate to {product_url} and extract comprehensive information about this product/service.

Focus on:
1. What the product/service does (core functionality)
2. All use cases and features
3. Target users/industries
4. Data handling and processing
5. Integrations and third-party services
6. Geographic regions served
7. Any compliance or regulatory mentions

Search for additional information online if needed to get a complete picture.

Use the save_product_info action to save your findings."""

        use_cloud = bool(self.config.get("browser_use_api_key"))
        browser = Browser(headless=True, use_cloud=use_cloud)
        llm = ChatBrowserUse()

        agent = Agent(
            task=task_prompt,
            llm=llm,
            browser=browser,
            tools=tools,
            use_vision="auto",
        )

        try:
            history = await asyncio.wait_for(agent.run(max_steps=30), timeout=300.0)
        except asyncio.TimeoutError:
            raise RuntimeError("Browser agent timed out extracting product info")
        finally:
            try:
                await browser.close()
            except Exception:
                pass

        content = extracted_data.get("content", "")

        # Extract final URL
        url = product_url
        try:
            urls = history.urls()
            if urls:
                url = urls[-1] if isinstance(urls[-1], str) else product_url
        except Exception:
            pass

        return {
            "content": content.strip(),
            "url": url,
        }

    async def generate_risk_analysis(
        self,
        product_info: Dict[str, Any],
        product_url: str,
    ) -> List[Dict[str, Any]]:
        """Step 2: Use Claude to analyze product and generate compliance risks.

        Takes product information and generates a comprehensive list of regulatory
        risks with deep analysis of exposure points.

        Returns list of risks, each containing:
            - regulation_title: Name of the regulation
            - risk_rationale: Why this regulation applies
            - jurisdiction: Geographic scope
            - scope: What aspects are affected
            - source_url: Official regulation URL
            - check_interval_seconds: How often to monitor
            - current_state: Initial snapshot of regulation
        """
        client = self._get_anthropic()
        if not client:
            raise RuntimeError("ANTHROPIC_API_KEY required for risk analysis")

        prompt = f"""You are a compliance expert. Analyze this product/service and identify ALL potential regulatory and compliance risks.

PRODUCT URL: {product_url}

PRODUCT INFORMATION:
{product_info.get('content', '')[:8000]}

Your task:
1. Understand what the product/service does in detail
2. Identify every regulation that could apply (major AND minor/microscopic risks)
3. For each risk, determine exact regulatory exposure points
4. Find the specific regulations and their current state

Focus on finding microscopic regulatory differences that humans might miss. Include:
- Data privacy regulations (GDPR, CCPA, etc.)
- Industry-specific regulations
- Financial compliance
- Healthcare compliance (HIPAA, etc.)
- Accessibility requirements
- Security standards
- Consumer protection laws
- Employment law
- International regulations
- Emerging regulations

For EACH identified risk, provide:
- regulation_title: Official name of the regulation
- risk_rationale: 2-3 sentences explaining WHY this regulation applies to this product
- jurisdiction: Geographic scope (e.g., "EU", "California", "United States", "Global")
- scope: What aspects of the product are affected
- source_url: Official URL to the regulation text (use real government/official sources)
- check_interval_seconds: How often to check (3600=hourly, 86400=daily, 604800=weekly)
- initial_search_query: What to search for to find current regulation state

Return ONLY valid JSON array (no markdown fences):
[
  {{
    "regulation_title": "...",
    "risk_rationale": "...",
    "jurisdiction": "...",
    "scope": "...",
    "source_url": "https://...",
    "check_interval_seconds": 86400,
    "initial_search_query": "..."
  }}
]

Be thorough - aim for 10-20 risks minimum, including both major and minor regulatory exposures."""

        try:
            response = client.messages.create(
                model=self.config.get("claude_model", "claude-sonnet-4-20250514"),
                max_tokens=8192,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
                system="You are a compliance expert. Return only the JSON array, no other text or markdown fences.",
            )
            text = response.content[0].text if response.content else "[]"
            risks = self._parse_json_array(text)

            # Fetch current state for all risks in parallel
            async def _fetch_one(risk: Dict[str, Any]) -> None:
                risk["current_state"] = await self._fetch_initial_regulation_state(risk)

            await asyncio.gather(*[_fetch_one(r) for r in risks], return_exceptions=True)

            return risks
        except Exception:
            logger.exception("Risk analysis failed")
            raise

    async def _fetch_initial_regulation_state(self, risk: Dict[str, Any]) -> str:
        """Fetch the initial/current state of a regulation using browser-use."""
        from browser_use import Agent, Browser, ChatBrowserUse, Tools, ActionResult

        extracted_data: Dict[str, str] = {}
        tools = Tools()

        @tools.action("Save the current regulation text")
        async def save_regulation_state(content: str) -> ActionResult:
            extracted_data["content"] = content
            return ActionResult(extracted_content=content)

        source_url = risk.get("source_url", "")
        search_query = risk.get("initial_search_query", risk.get("regulation_title", ""))

        if source_url and source_url.startswith("http"):
            nav_instruction = f"Navigate to {source_url}"
        else:
            nav_instruction = f'Search Google for: "{search_query}"'

        task_prompt = f"""Find and extract the current text of this regulation:

Regulation: {risk.get('regulation_title', 'Unknown')}
Jurisdiction: {risk.get('jurisdiction', 'Unknown')}

Steps:
1. {nav_instruction}
2. Navigate to the official regulation page
3. Extract the FULL regulatory text (be thorough)
4. Use save_regulation_state to save the text

Extract ALL relevant regulatory language."""

        use_cloud = bool(self.config.get("browser_use_api_key"))
        browser = Browser(headless=True, use_cloud=use_cloud)
        llm = ChatBrowserUse()

        agent = Agent(
            task=task_prompt,
            llm=llm,
            browser=browser,
            tools=tools,
            use_vision="auto",
        )

        try:
            history = await asyncio.wait_for(agent.run(max_steps=25), timeout=180.0)
        except asyncio.TimeoutError:
            logger.warning(f"Timed out fetching regulation state for {risk.get('regulation_title')}")
            return ""
        finally:
            try:
                await browser.close()
            except Exception:
                pass

        content = extracted_data.get("content", "")
        return content.strip()

    async def create_watches_from_risks(
        self,
        risks: List[Dict[str, Any]],
        organization_id: str,
        product_url: str,
    ) -> List[Dict[str, Any]]:
        """Step 3: Create a watch for each identified risk."""
        watches = []

        for risk in risks:
            # Validate Claude-generated URL — discard hallucinated non-URLs
            source_url = risk.get("source_url", "") or ""
            if not source_url.startswith(("http://", "https://")):
                risk["source_url"] = ""

            watch_name = f"{risk.get('regulation_title', 'Compliance Risk')}"
            description = f"{risk.get('risk_rationale', '')}\n\nJurisdiction: {risk.get('jurisdiction', 'Unknown')}\nScope: {risk.get('scope', 'Unknown')}"

            check_interval = risk.get("check_interval_seconds", 86400)  # Default: daily

            # Convert check_interval_seconds to schedule
            if check_interval >= 604800:  # Weekly
                schedule = {"cron": "0 9 * * 1", "timezone": "UTC"}  # Monday 9 AM
            elif check_interval >= 86400:  # Daily
                schedule = {"cron": "0 9 * * *", "timezone": "UTC"}  # Daily 9 AM
            else:  # Hourly or more frequent
                schedule = {"cron": "0 * * * *", "timezone": "UTC"}  # Every hour

            config = {
                "schedule": schedule,
                "product_url": product_url,
                "targets": [
                    {
                        "name": risk.get("regulation_title", "Regulation"),
                        "description": risk.get("risk_rationale", ""),
                        "starting_url": risk.get("source_url"),
                        "search_query": risk.get("initial_search_query", risk.get("regulation_title", "")),
                        "extraction_instructions": "Extract the full regulatory text and any recent updates or amendments.",
                    }
                ],
            }

            # Create watch with extended metadata
            watch = await self.watch_service.create_watch(
                organization_id=organization_id,
                name=watch_name,
                description=description,
                watch_type="regulation",
                config=config,
                integrations={},
                regulation_title=risk.get("regulation_title"),
                risk_rationale=risk.get("risk_rationale"),
                jurisdiction=risk.get("jurisdiction"),
                scope=risk.get("scope"),
                source_url=risk.get("source_url"),
                check_interval_seconds=check_interval,
                current_regulation_state=risk.get("current_state", ""),
            )
            watches.append(watch)

        logger.info(f"Created {len(watches)} watches from risk analysis")
        return watches

    def _parse_json_array(self, text: str) -> List[Dict[str, Any]]:
        """Extract JSON array from text that may contain markdown fences or prose."""
        text = text.strip()
        # Strip markdown code fences
        if "```" in text:
            import re
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                text = match.group(1).strip()
        # Find JSON array
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                pass
        return []

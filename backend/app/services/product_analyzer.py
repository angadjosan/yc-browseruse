"""Product analysis service: extracts product info and generates compliance risks.

Workflow:
1. Use browser-use agent to extract product information from landing page
2. Use Claude to analyze product and generate list of compliance risks
3. Create watches for each identified risk
"""
import hashlib
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from app.config import get_config
from app.services.watch_service import WatchService

logger = logging.getLogger(__name__)

# Type alias for the log callback
LogFn = Callable[[str], None]

def _noop_log(msg: str) -> None:
    pass


def _extract_history_steps(history: Any, log: LogFn) -> None:
    """Pull every available detail out of a browser-use AgentHistory and log it."""
    # Log all URLs visited
    try:
        urls = history.urls()
        if urls:
            for u in urls:
                log(f"  Visited: {u}")
    except Exception:
        pass

    # Log action results / extracted content
    try:
        ec = history.extracted_content()
        if ec:
            for i, chunk in enumerate(ec):
                text = str(chunk).strip()
                if text:
                    preview = text[:300] + ("..." if len(text) > 300 else "")
                    log(f"  Extracted [{i+1}]: {preview}")
    except Exception:
        pass

    # Log model outputs / thoughts
    try:
        model_outputs = history.model_actions()
        if model_outputs:
            for i, action in enumerate(model_outputs):
                if isinstance(action, dict):
                    thought = (action.get("current_state") or {}).get("next_goal") or action.get("thought") or ""
                    act = action.get("action") or ""
                    if thought:
                        log(f"  Agent thought [{i+1}]: {thought}")
                    if act:
                        log(f"  Agent action [{i+1}]: {act}")
                else:
                    log(f"  Agent step [{i+1}]: {str(action)[:200]}")
    except Exception:
        pass

    # Log final result
    try:
        fr = history.final_result()
        if fr:
            text = str(fr).strip()
            if text:
                preview = text[:500] + ("..." if len(text) > 500 else "")
                log(f"  Final result: {preview}")
    except Exception:
        pass


class ProductAnalyzer:
    """Analyzes product pages and generates compliance risk watches."""

    def __init__(self, log_fn: Optional[LogFn] = None):
        self.config = get_config()
        self.watch_service = WatchService()
        self._anthropic = None
        self._log = log_fn or _noop_log

    def _get_anthropic(self):
        if self._anthropic is None and self.config.get("anthropic_api_key"):
            from anthropic import Anthropic
            self._anthropic = Anthropic(api_key=self.config["anthropic_api_key"])
        return self._anthropic

    def _has_browser_use(self) -> bool:
        if not self.config.get("browser_use_api_key"):
            return False
        try:
            from browser_use import Agent, Browser, ChatBrowserUse  # noqa: F401
            return True
        except ImportError:
            return False

    async def analyze_product_url(
        self,
        product_url: str,
        organization_id: str,
    ) -> Dict[str, Any]:
        """Main workflow: analyze product, generate risks, create watches."""
        log = self._log
        log(f"Starting product analysis for {product_url}")

        # Step 1: Extract product information using browser-use
        log("─── STEP 1: Scraping product page ───")
        product_info = await self.extract_product_info(product_url)
        if not product_info or not product_info.get("content"):
            raise ValueError("Failed to extract product information from URL")

        content = product_info["content"]
        log(f"Extraction complete — {len(content)} characters scraped")
        # Show a preview of what was extracted
        preview = content[:600].replace("\n", " ").strip()
        log(f"Content preview: {preview}...")

        # Step 2: Generate compliance risks using Claude
        log("─── STEP 2: Analyzing compliance risks with Claude ───")
        risks = await self.generate_risk_analysis(product_info, product_url)
        if not risks:
            raise ValueError("Failed to generate compliance risk analysis")

        # Step 3: Create watches for each risk
        log("─── STEP 3: Creating watches ───")
        watches = await self.create_watches_from_risks(risks, organization_id, product_url)

        log(f"All done — {len(watches)} watches active")
        return {
            "product_info": product_info,
            "risks": risks,
            "watches": watches,
        }

    async def extract_product_info(self, product_url: str) -> Dict[str, Any]:
        """Step 1: Use browser-use agent to extract product information."""
        log = self._log

        if not self._has_browser_use():
            log("Browser-use not available — using mock extraction")
            return {
                "content": f"[MOCK] Product information from {product_url}. Install browser-use for real extraction.",
                "url": product_url,
            }

        from browser_use import Agent, Browser, ChatBrowserUse, Tools, ActionResult

        extracted_data: Dict[str, str] = {}
        tools = Tools()

        @tools.action("Save the extracted product information")
        async def save_product_info(content: str) -> ActionResult:
            extracted_data["content"] = content
            log(f"Agent saved product info ({len(content)} chars)")
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
        log(f"Launching browser agent (cloud={use_cloud}) → {product_url}")
        log(f"Max steps: 30")
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
            log("Agent running...")
            history = await agent.run(max_steps=30)
            log("Agent finished — extracting results")
            _extract_history_steps(history, log)
        finally:
            try:
                await browser.close()
            except Exception:
                pass

        content = extracted_data.get("content", "")
        if not content:
            try:
                fr = history.final_result()
                if isinstance(fr, str) and fr.strip():
                    content = fr
                elif isinstance(fr, dict) and fr.get("content"):
                    content = fr["content"]
            except Exception:
                pass

        if not content:
            try:
                ec = history.extracted_content()
                if ec:
                    parts = [str(x) for x in ec if x]
                    content = "\n".join(parts)
            except Exception:
                pass

        # Extract final URL
        url = product_url
        try:
            urls = history.urls()
            if urls:
                url = urls[-1] if isinstance(urls[-1], str) else product_url
        except Exception:
            pass

        log(f"Product extraction yielded {len(content)} chars from {url}")
        return {
            "content": content.strip() or "No content extracted.",
            "url": url,
        }

    async def generate_risk_analysis(
        self,
        product_info: Dict[str, Any],
        product_url: str,
    ) -> List[Dict[str, Any]]:
        """Step 2: Use Claude to analyze product and generate compliance risks."""
        log = self._log
        client = self._get_anthropic()
        if not client:
            raise RuntimeError("ANTHROPIC_API_KEY required for risk analysis")

        model = self.config.get("claude_model", "claude-sonnet-4-20250514")
        log(f"Calling Claude ({model}) for risk analysis...")
        content_len = len(product_info.get("content", ""))
        log(f"Sending {min(content_len, 8000)} chars of product info to Claude")

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
                model=model,
                max_tokens=8192,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
                system="You are a compliance expert. Return only the JSON array, no other text or markdown fences.",
            )
            text = response.content[0].text if response.content else "[]"
            log(f"Claude responded — {len(text)} chars, parsing risks...")
            risks = self._parse_json_array(text)
            log(f"Parsed {len(risks)} risks from Claude response")

            for i, risk in enumerate(risks):
                title = risk.get("regulation_title", "Unknown")
                jurisdiction = risk.get("jurisdiction", "")
                log(f"  Risk {i+1}/{len(risks)}: {title} ({jurisdiction})")

            # Now fetch current state for each risk
            log("─── Fetching current regulation state for each risk ───")
            for i, risk in enumerate(risks):
                title = risk.get("regulation_title", "Unknown")
                log(f"Fetching state {i+1}/{len(risks)}: {title}")
                try:
                    current_state = await self._fetch_initial_regulation_state(risk)
                    risk["current_state"] = current_state
                    state_preview = current_state[:200].replace("\n", " ") if current_state else "(empty)"
                    log(f"  Got {len(current_state)} chars: {state_preview}...")
                except Exception as e:
                    log(f"  Failed to fetch state for {title}: {e}")
                    risk["current_state"] = f"Failed to fetch: {e}"

            return risks
        except Exception:
            logger.exception("Risk analysis failed")
            raise

    async def _fetch_initial_regulation_state(self, risk: Dict[str, Any]) -> str:
        """Fetch the initial/current state of a regulation using browser-use."""
        log = self._log

        if not self._has_browser_use():
            return f"Initial state for {risk.get('regulation_title', 'regulation')} (browser-use unavailable)"

        from browser_use import Agent, Browser, ChatBrowserUse, Tools, ActionResult

        extracted_data: Dict[str, str] = {}
        tools = Tools()

        @tools.action("Save the current regulation text")
        async def save_regulation_state(content: str) -> ActionResult:
            extracted_data["content"] = content
            log(f"    Agent saved regulation state ({len(content)} chars)")
            return ActionResult(extracted_content=content)

        source_url = risk.get("source_url", "")
        search_query = risk.get("initial_search_query", risk.get("regulation_title", ""))

        if source_url and source_url.startswith("http"):
            nav_instruction = f"Navigate to {source_url}"
            log(f"  Navigating to: {source_url}")
        else:
            nav_instruction = f'Search Google for: "{search_query}"'
            log(f"  Searching for: {search_query}")

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
            log(f"  Launching regulation scraper agent (max_steps=25)")
            history = await agent.run(max_steps=25)
            log(f"  Regulation scraper finished")
            _extract_history_steps(history, lambda msg: log(f"  {msg}"))
        finally:
            try:
                await browser.close()
            except Exception:
                pass

        content = extracted_data.get("content", "")
        if not content:
            try:
                fr = history.final_result()
                if isinstance(fr, str) and fr.strip():
                    content = fr
            except Exception:
                pass

        return content.strip() or f"Current state of {risk.get('regulation_title', 'regulation')}"

    async def create_watches_from_risks(
        self,
        risks: List[Dict[str, Any]],
        organization_id: str,
        product_url: str,
    ) -> List[Dict[str, Any]]:
        """Step 3: Create a watch for each identified risk."""
        log = self._log
        watches = []

        for i, risk in enumerate(risks):
            watch_name = f"{risk.get('regulation_title', 'Compliance Risk')}"
            description = f"{risk.get('risk_rationale', '')}\n\nJurisdiction: {risk.get('jurisdiction', 'Unknown')}\nScope: {risk.get('scope', 'Unknown')}"

            check_interval = risk.get("check_interval_seconds", 86400)

            if check_interval >= 604800:
                schedule = {"cron": "0 9 * * 1", "timezone": "UTC"}
            elif check_interval >= 86400:
                schedule = {"cron": "0 9 * * *", "timezone": "UTC"}
            else:
                schedule = {"cron": "0 * * * *", "timezone": "UTC"}

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

            log(f"Creating watch {i+1}/{len(risks)}: {watch_name}")
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
            log(f"  Watch created: {watch.get('id', '?')}")

        log(f"All {len(watches)} watches created successfully")
        return watches

    def _parse_json_array(self, text: str) -> List[Dict[str, Any]]:
        """Extract JSON array from text that may contain markdown fences or prose."""
        text = text.strip()
        if "```" in text:
            import re
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                text = match.group(1).strip()
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                pass
        return []

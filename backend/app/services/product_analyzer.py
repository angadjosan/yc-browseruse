"""Product analysis service: extracts product info and generates compliance risks.

Workflow:
1. Use browser-use agent to extract product information from landing page
2. Use Claude to analyze product and generate list of compliance risks
3. Create watches for each identified risk
"""
import asyncio
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
    """Pull every available detail out of a browser-use AgentHistory and log it — FULL output, no truncation."""

    # Log all URLs visited
    try:
        urls = history.urls()
        if urls:
            log(f"  URLs visited ({len(urls)}):")
            for j, u in enumerate(urls):
                log(f"    [{j+1}] {u}")
    except Exception:
        pass

    # Log model outputs / thoughts — full text
    try:
        model_outputs = history.model_actions()
        if model_outputs:
            log(f"  Agent steps ({len(model_outputs)}):")
            for i, action in enumerate(model_outputs):
                if isinstance(action, dict):
                    # Current state
                    cs = action.get("current_state") or {}
                    if cs.get("evaluation_previous_goal"):
                        log(f"    [{i+1}] eval: {cs['evaluation_previous_goal']}")
                    if cs.get("memory"):
                        log(f"    [{i+1}] memory: {cs['memory']}")
                    if cs.get("next_goal"):
                        log(f"    [{i+1}] goal: {cs['next_goal']}")
                    # Action taken
                    act = action.get("action")
                    if act:
                        if isinstance(act, dict):
                            for act_name, act_params in act.items():
                                log(f"    [{i+1}] action: {act_name}({json.dumps(act_params, default=str)[:500]})")
                        else:
                            log(f"    [{i+1}] action: {str(act)[:500]}")
                    # Fallback: thought field
                    thought = action.get("thought") or ""
                    if thought and not cs:
                        log(f"    [{i+1}] thought: {thought}")
                elif isinstance(action, list):
                    for sub in action:
                        if isinstance(sub, dict):
                            for act_name, act_params in sub.items():
                                log(f"    [{i+1}] action: {act_name}({json.dumps(act_params, default=str)[:500]})")
                        else:
                            log(f"    [{i+1}] {str(sub)[:500]}")
                else:
                    log(f"    [{i+1}] {str(action)[:500]}")
    except Exception:
        pass

    # Log action results / extracted content — full text
    try:
        ec = history.extracted_content()
        if ec:
            log(f"  Extracted content ({len(ec)} chunks):")
            for i, chunk in enumerate(ec):
                text = str(chunk).strip()
                if text:
                    # Log full content, split into lines so the scroll rect shows it all
                    lines = text.split("\n")
                    for line in lines[:100]:
                        log(f"    | {line}")
                    if len(lines) > 100:
                        log(f"    | ... ({len(lines) - 100} more lines)")
    except Exception:
        pass

    # Log final result — full text
    try:
        fr = history.final_result()
        if fr:
            text = str(fr).strip()
            if text:
                log(f"  Final result ({len(text)} chars):")
                lines = text.split("\n")
                for line in lines[:150]:
                    log(f"    | {line}")
                if len(lines) > 150:
                    log(f"    | ... ({len(lines) - 150} more lines)")
    except Exception:
        pass


class ProductAnalyzer:
    """Analyzes product pages and generates compliance risk watches."""

    def __init__(self, log_fn: Optional[LogFn] = None, on_risks_found: Optional[Callable[[List[Dict[str, Any]]], None]] = None):
        self.config = get_config()
        self.watch_service = WatchService()
        self._anthropic = None
        self._async_anthropic = None
        self._log = log_fn or _noop_log
        self._on_risks_found = on_risks_found

    def _get_anthropic(self):
        if self._anthropic is None and self.config.get("anthropic_api_key"):
            from anthropic import Anthropic
            self._anthropic = Anthropic(api_key=self.config["anthropic_api_key"])
        return self._anthropic

    def _get_async_anthropic(self):
        if self._async_anthropic is None and self.config.get("anthropic_api_key"):
            from anthropic import AsyncAnthropic
            self._async_anthropic = AsyncAnthropic(api_key=self.config["anthropic_api_key"])
        return self._async_anthropic

    def _has_browser_use(self) -> bool:
        return bool(self.config.get("browser_use_api_key"))

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
        try:
            product_info = await self.extract_product_info(product_url)
        except Exception as e:
            log(f"Browser agent failed ({e}) — falling back to HTTP scrape")
            product_info = None
        if not product_info or not product_info.get("content"):
            log("Browser agent returned empty content — falling back to HTTP scrape")
            fallback_content = await self._http_scrape(product_url, log)
            if not fallback_content:
                raise ValueError("Failed to extract product information from URL")
            product_info = {"content": fallback_content, "url": product_url}

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

Use the save_product_info action to save your findings."""

        use_cloud = bool(self.config.get("browser_use_api_key"))
        log(f"Launching browser agent → {product_url}")
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
            history = await asyncio.wait_for(agent.run(max_steps=3), timeout=90.0)
            log("Agent finished — extracting results")
        except asyncio.TimeoutError:
            raise RuntimeError("Browser agent timed out extracting product info")
        finally:
            try:
                await browser.close()
            except Exception:
                pass

        content = extracted_data.get("content", "")

        # Fallback 1: pull text from agent history if save_product_info was never called
        if not content:
            log("Agent did not call save_product_info — trying history fallback")
            try:
                fr = history.final_result()
                if fr and str(fr).strip():
                    content = str(fr).strip()
                    log(f"  Got {len(content)} chars from history.final_result()")
            except Exception:
                pass
        if not content:
            try:
                chunks = history.extracted_content()
                if chunks:
                    content = "\n".join(str(c) for c in chunks if str(c).strip())
                    log(f"  Got {len(content)} chars from history.extracted_content()")
            except Exception:
                pass

        # Fallback 2: plain HTTP scrape
        if not content:
            log("History fallback empty — falling back to plain HTTP scrape")
            content = await self._http_scrape(product_url, log)

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
            "content": content.strip(),
            "url": url,
        }

    async def generate_risk_analysis(
        self,
        product_info: Dict[str, Any],
        product_url: str,
    ) -> List[Dict[str, Any]]:
        """Step 2: Use Claude to analyze product and generate compliance risks."""
        log = self._log
        client = self._get_async_anthropic()
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

CRITICAL: Your response must be ONLY the raw JSON array. Nothing else.
- No markdown (no ``` or ```json)
- No explanation, no preamble, no "Here is the JSON"
- No text before the opening [ or after the closing ]
- Your entire response must be parseable as JSON. Start with [ and end with ].

Format:
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

Aim for 5-8 risks covering the most significant regulatory exposures. Output ONLY the JSON array."""

        try:
            system = (
                "You are a compliance expert. Your response must be exclusively a single JSON array. "
                "Do not include any markdown, code fences, explanation, or text before or after the array. "
                "Your entire reply must start with '[' and end with ']' and be valid JSON only."
            )
            response = await client.messages.create(
                model=model,
                max_tokens=8192,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
                system=system,
            )
            text = ""
            if response.content:
                for block in response.content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text += block.get("text", "") or ""
                    elif getattr(block, "text", None):
                        text += block.text
            text = text or "[]"
            log(f"Claude response ({len(text)} chars)")
            log("Parsing risks...")
            risks = self._parse_json_array(text)
            log(f"Parsed {len(risks)} risks from Claude response")

            for i, risk in enumerate(risks):
                title = risk.get("regulation_title", "Unknown")
                jurisdiction = risk.get("jurisdiction", "")
                rationale = risk.get("risk_rationale", "")
                log(f"  Risk {i+1}/{len(risks)}: {title} ({jurisdiction})")
                if rationale:
                    log(f"    Rationale: {rationale}")

            # Push risks to frontend immediately so they appear during regulation fetching
            if self._on_risks_found:
                self._on_risks_found(risks)

            # Fetch current state for top N risks in parallel, max 5 concurrent agents
            FETCH_LIMIT = 8
            sem = asyncio.Semaphore(5)
            top_risks = risks[:FETCH_LIMIT]
            log(f"─── Fetching regulation state for top {len(top_risks)}/{len(risks)} risks (max 5 concurrent) ───")

            async def _fetch_one(i_risk: tuple) -> None:
                i, risk = i_risk
                title = risk.get("regulation_title", "Unknown")
                log(f"Fetching state {i+1}/{len(top_risks)}: {title}")
                try:
                    async with sem:
                        current_state = await self._fetch_initial_regulation_state(risk)
                    risk["current_state"] = current_state
                    state_preview = current_state[:200].replace("\n", " ") if current_state else "(empty)"
                    log(f"  Got {len(current_state)} chars: {state_preview}...")
                except Exception as e:
                    log(f"  Failed to fetch state for {title}: {e}")
                    risk["current_state"] = f"Failed to fetch: {e}"

            await asyncio.gather(*[_fetch_one(ir) for ir in enumerate(top_risks)], return_exceptions=True)

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

        task_prompt = f"""Extract a brief summary of this regulation:

Regulation: {risk.get('regulation_title', 'Unknown')}
Jurisdiction: {risk.get('jurisdiction', 'Unknown')}

Steps:
1. {nav_instruction}
2. Extract the key requirements (200-400 words max)
3. Use save_regulation_state to save the text"""

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
            log(f"  Launching regulation scraper agent (max_steps=3)")
            history = await asyncio.wait_for(agent.run(max_steps=3), timeout=60.0)
            log(f"  Regulation scraper finished")
        except asyncio.TimeoutError:
            logger.warning(f"Timed out fetching regulation state for {risk.get('regulation_title')}")
            return ""
        finally:
            try:
                await browser.close()
            except Exception:
                pass

        content = extracted_data.get("content", "")

        # Fallback: pull text from agent history if save action was never called
        if not content:
            try:
                fr = history.final_result()
                if fr and str(fr).strip():
                    content = str(fr).strip()
            except Exception:
                pass
        if not content:
            try:
                chunks = history.extracted_content()
                if chunks:
                    content = "\n".join(str(c) for c in chunks if str(c).strip())
            except Exception:
                pass

        return content.strip()

    async def _http_scrape(self, url: str, log: LogFn) -> str:
        """Plain HTTP GET + basic text extraction, no browser required."""
        try:
            import urllib.request
            import html
            import re

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ComplianceRadar/1.0)"},
            )
            loop = asyncio.get_event_loop()
            response_bytes = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=30).read()),
                timeout=35.0,
            )
            raw = response_bytes.decode("utf-8", errors="replace")
            # Strip scripts/styles/tags
            raw = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
            raw = re.sub(r"<[^>]+>", " ", raw)
            raw = html.unescape(raw)
            # Collapse whitespace
            text = re.sub(r"[ \t]+", " ", raw)
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = text.strip()
            log(f"HTTP scrape yielded {len(text)} chars")
            return text[:12000]
        except Exception as e:
            log(f"HTTP scrape failed: {e}")
            return ""

    async def create_watches_from_risks(
        self,
        risks: List[Dict[str, Any]],
        organization_id: str,
        product_url: str,
    ) -> List[Dict[str, Any]]:
        """Step 3: Create a watch for each identified risk."""
        log = self._log

        async def _create_one(i: int, risk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            source_url = risk.get("source_url", "") or ""
            if not source_url.startswith(("http://", "https://")):
                risk["source_url"] = ""

            watch_name = risk.get("regulation_title", "Compliance Risk")
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
            log(f"  Watch created: {watch.get('id', '?')}")
            return watch

        results = await asyncio.gather(*[_create_one(i, risk) for i, risk in enumerate(risks)], return_exceptions=True)
        watches = [w for w in results if isinstance(w, dict)]
        log(f"All {len(watches)} watches created successfully")
        return watches

    def _find_matching_bracket(self, s: str, open_pos: int) -> int:
        """Return index of matching ']' for '[' at open_pos, or -1. Handles nested brackets."""
        depth = 0
        in_string = None
        escape = False
        i = open_pos + 1
        while i < len(s):
            c = s[i]
            if escape:
                escape = False
                i += 1
                continue
            if c == "\\" and in_string:
                escape = True
                i += 1
                continue
            if in_string:
                if c == in_string:
                    in_string = None
                i += 1
                continue
            if c in ('"', "'"):
                in_string = c
                i += 1
                continue
            if c == "[":
                depth += 1
            elif c == "]":
                if depth == 0:
                    return i
                depth -= 1
            i += 1
        return -1

    def _extract_json_array_candidates(self, raw: str) -> List[str]:
        """Return multiple candidate substrings that might be the JSON array. Caller will try to parse each."""
        import re
        candidates: List[str] = []
        # 1) Markdown code blocks (any fence)
        for pattern in (r"```(?:json)?\s*([\s\S]*?)```", r"~~~(?:json)?\s*([\s\S]*?)~~~"):
            for m in re.finditer(pattern, raw, re.IGNORECASE):
                candidates.append(m.group(1).strip())
        # 2) First '[' with bracket-matched ']'
        start = raw.find("[")
        if start != -1:
            end = self._find_matching_bracket(raw, start)
            if end != -1:
                candidates.append(raw[start : end + 1])
        # 3) Last ']' backwards: find last ']' then find matching '[' (scan backwards by finding first '[' that matches)
        last_close = raw.rfind("]")
        if last_close != -1:
            depth = 0
            for i in range(last_close - 1, -1, -1):
                c = raw[i]
                if c == "]":
                    depth += 1
                elif c == "[":
                    if depth == 0:
                        candidates.append(raw[i : last_close + 1])
                        break
                    depth -= 1
        # 4) Any [ ... ] that contains "regulation_title" (likely our array)
        for m in re.finditer(r"\[\s*\{[^[]*\"regulation_title\"", raw):
            start = m.start()
            end = self._find_matching_bracket(raw, start)
            if end != -1:
                candidates.append(raw[start : end + 1])
        return candidates

    def _try_fix_json(self, s: str) -> str:
        """Apply common fixes so invalid JSON might become valid."""
        s = s.strip()
        # Trailing comma before ] or }
        import re
        s = re.sub(r",\s*\]", "]", s)
        s = re.sub(r",\s*}", "}", s)
        return s

    def _close_truncated_json(self, s: str):
        """Yield candidate strings with closing brackets appended for truncated JSON."""
        base = s.rstrip()
        if base.endswith(","):
            base = base[:-1]
        # Try closing array and/or open objects (truncation often mid-object or mid-array)
        for suffix in ("]", "}]", "}}]", "}}}]"):
            yield base + suffix

    def _parse_json_array(self, text: str) -> List[Dict[str, Any]]:
        """Extract and parse the JSON array from Claude output with high tolerance for wrappers and noise."""
        if not text or not text.strip():
            return []
        raw = text.strip().strip("\ufeff")  # BOM
        # Normalize: sometimes stream ends mid-string
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")

        candidates = self._extract_json_array_candidates(raw)
        if not candidates:
            # Last resort: any substring that looks like [{ ... }]
            start = raw.find("[{")
            if start != -1:
                end = self._find_matching_bracket(raw, start)
                if end != -1:
                    candidates.append(raw[start : end + 1])
        if not candidates and "[" in raw:
            # Maybe bracket matching failed (e.g. escaped quotes). Use first [ to last ].
            start = raw.find("[")
            end = raw.rfind("]")
            if end > start:
                candidates.append(raw[start : end + 1])
            elif start != -1:
                # Truncated or malformed: no closing ]. Use from first [ to end and try closing in parse loop.
                candidates.append(raw[start:])
        if not candidates:
            # Strip control chars and try again (sometimes stream has stray bytes)
            cleaned = "".join(c for c in raw if c == "\n" or c == "\t" or not (ord(c) < 32 or ord(c) == 127))
            if cleaned != raw:
                candidates = self._extract_json_array_candidates(cleaned)
        if not candidates:
            logger.warning(
                "No JSON array candidate found in Claude response (len=%d). Preview: %s",
                len(raw),
                raw[:500].replace("\n", " "),
            )
            return []

        for candidate in candidates:
            if len(candidate) < 10:
                continue
            for s in (candidate, self._try_fix_json(candidate)):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        if all(isinstance(x, dict) for x in parsed):
                            return parsed
                        # Mixed list: take only dict items
                        return [x for x in parsed if isinstance(x, dict)]
                except json.JSONDecodeError as e:
                    # Truncated stream: try closing open brackets/braces
                    near_end = e.pos is not None and e.pos >= max(0, len(s) - 50)
                    if near_end:
                        for suffix in ("]", '"]}', '"]}]', "}]"):
                            try:
                                fixed = s[: e.pos].rstrip()
                                if fixed.endswith(","):
                                    fixed = fixed[:-1]
                                parsed = json.loads(fixed + suffix)
                                if isinstance(parsed, list):
                                    out = [x for x in parsed if isinstance(x, dict)]
                                    if out:
                                        return out
                            except (json.JSONDecodeError, IndexError):
                                continue
                    # Candidate may be truncated (no closing ]): try appending closers
                    if not s.rstrip().endswith("]"):
                        for closer in self._close_truncated_json(s):
                            try:
                                parsed = json.loads(closer)
                                if isinstance(parsed, list):
                                    out = [x for x in parsed if isinstance(x, dict)]
                                    if out:
                                        return out
                            except json.JSONDecodeError:
                                continue
                    continue
        logger.warning(
            "All JSON candidates failed to parse (tried %d). First candidate preview: %s",
            len(candidates),
            candidates[0][:300].replace("\n", " ") if candidates else "",
        )
        return []

# Compliance Change Radar — Technical Design Document

## Table of Contents
1. [System Architecture](#1-system-architecture)
2. [Backend Components](#2-backend-components)
3. [Database Schema](#3-database-schema)
4. [Frontend Pages](#4-frontend-pages)
5. [API Specifications](#5-api-specifications)
6. [Integration Details](#6-integration-details)
7. [Implementation Details](#7-implementation-details)

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
│  Dashboard │ Watch Manager │ History │ Evidence Viewer │ Settings│
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API + WebSocket
┌────────────────────────────┴────────────────────────────────────┐
│                      Backend (FastAPI/Python)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ API Layer    │  │ Job Scheduler│  │ WebSocket    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                   │
│  ┌──────┴──────────────────┴──────────────────┴───────┐          │
│  │           Core Services Layer                       │          │
│  │  • Watch Service    • Orchestrator Engine          │          │
│  │  • Diff Engine      • Evidence Service             │          │
│  │  • Notification Hub • Integration Manager          │          │
│  └─────────────────────────┬───────────────────────────┘          │
└────────────────────────────┼────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                     Agent Infrastructure                         │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ Claude Orchestr. │  │ Browser-Use      │                    │
│  │ (Anthropic)      │  │ Agents           │                    │
│  └──────────────────┘  └──────────────────┘                    │
│                         (ChatBrowserUse LLM)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                    Data & External Services                      │
│  Supabase  │  Redis  │  S3  │  Linear  │  Slack  │  Anthropic  │
│ (local dev)│         │      │          │         │              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

**Frontend:**
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS + shadcn/ui
- Framer Motion (animations)
- React Query (data fetching)
- Zustand (state management)
- WebSocket client (real-time updates)
- **Supabase JS Client** (database + realtime)

**Backend:**
- **Python 3.11+** (FastAPI)
- **browser-use** library (AI-powered browser automation)
- **uv** package manager (instead of pip)
- **Pydantic v2** (type-safe schemas)
- **Supabase** (PostgreSQL + Auth + Realtime + Storage)
- **supabase-py** (Python client)
- Redis (caching, job queue)
- Celery or ARQ (job scheduling)
- **Anthropic Claude API** (orchestrator)
- **ChatBrowserUse** (browser automation LLM - fastest & most cost-effective)

**Infrastructure:**
- **Supabase Local** (development via Docker)
- Docker + Kubernetes (production)
- AWS S3 or Supabase Storage (evidence storage)
- CloudWatch (monitoring)
- GitHub Actions (CI/CD)
- **Browser-Use Cloud** (production browser instances with @sandbox)

---

## 2. Backend Components

### 2.1 Orchestrator Engine

**Purpose:** Claude-powered orchestrator that manages watch execution, creates execution plans, assigns tasks to browser-use agents, and handles retries/self-healing.

**Key Logic:**

```python
from anthropic import Anthropic
from browser_use import Agent, Browser, ChatBrowserUse, Tools, ActionResult
from browser_use.browser import BrowserSession
from pydantic import BaseModel, Field
from typing import List, Optional
import asyncio


class BrowserTask(BaseModel):
    """Pydantic model for browser task definition"""
    id: str
    target_name: str
    task_description: str
    starting_url: Optional[str] = None
    search_query: Optional[str] = None
    extraction_instructions: str
    fallback_strategy: Optional[str] = None


class ExecutionPlan(BaseModel):
    """Pydantic model for execution plan"""
    watch_id: str
    run_id: str
    tasks: List[BrowserTask]
    estimated_duration: int  # seconds


class TaskResult(BaseModel):
    """Pydantic model for task results"""
    task_id: str
    status: str  # 'success', 'failed', 'partial'
    content: Optional[str] = None
    screenshot_path: Optional[str] = None
    content_hash: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    timestamp: int


class OrchestratorEngine:
    """Claude-powered orchestrator for managing watch executions"""

    def __init__(self):
        self.anthropic_client = Anthropic()
        self.browser_use_llm = ChatBrowserUse()

    async def execute_watch(self, watch_id: str) -> dict:
        """Main execution method for a watch"""
        watch = await self.get_watch(watch_id)
        run_id = self.generate_run_id()

        # Initialize run in database
        await self.create_watch_run(run_id, watch_id)

        # Use Claude to create execution plan
        plan = await self.create_execution_plan(watch)

        # Execute tasks with browser-use agents
        results = await self.execute_tasks_with_retries(plan, run_id)

        # Detect changes
        changes = await self.detect_changes(results, watch)

        # Generate evidence if changes detected
        if changes:
            for change in changes:
                await self.generate_evidence(change, run_id)
                await self.trigger_notifications(change, watch)

        return {
            'run_id': run_id,
            'changes': len(changes),
            'status': 'completed'
        }

    async def create_execution_plan(self, watch: dict) -> ExecutionPlan:
        """Use Claude to analyze watch config and create detailed execution plan"""

        prompt = f"""
        You are a compliance monitoring expert. Given this watch configuration,
        create a detailed execution plan for browser automation agents.

        Watch Configuration:
        {json.dumps(watch.config, indent=2)}

        For each target to monitor, create a specific task with:
        1. Starting URL or search query
        2. Exact navigation steps (what to search, what to click, what forms to fill)
        3. What content to extract
        4. Fallback strategy if primary approach fails

        Remember: These agents will use browser-use library which can:
        - Search on Google/DuckDuckGo
        - Navigate to URLs
        - Click elements
        - Fill forms
        - Extract content using LLM
        - Handle multi-step flows
        - Take screenshots

        Return a structured execution plan.
        """

        response = self.anthropic_client.messages.create(
            model="claude-sonnet-4-0",
            max_tokens=4096,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
            system="You are a compliance automation expert. Create precise, executable plans."
        )

        # Parse Claude's response into ExecutionPlan
        plan_data = self.parse_claude_plan(response.content[0].text)

        return ExecutionPlan(
            watch_id=watch.id,
            run_id=self.generate_run_id(),
            tasks=plan_data['tasks'],
            estimated_duration=plan_data['estimated_duration']
        )

    async def execute_tasks_with_retries(
        self,
        plan: ExecutionPlan,
        run_id: str
    ) -> List[TaskResult]:
        """Execute all tasks with retry logic and self-healing"""

        results = []

        # Execute tasks in parallel where possible
        tasks_to_run = []
        for task in plan.tasks:
            tasks_to_run.append(self.execute_single_task_with_retry(task, run_id))

        # Gather all results
        task_results = await asyncio.gather(*tasks_to_run, return_exceptions=True)

        for result in task_results:
            if isinstance(result, Exception):
                # Log exception and create failed result
                results.append(TaskResult(
                    task_id="unknown",
                    status="failed",
                    error=str(result),
                    timestamp=int(time.time())
                ))
            else:
                results.append(result)

        return results

    async def execute_single_task_with_retry(
        self,
        task: BrowserTask,
        run_id: str
    ) -> TaskResult:
        """Execute a single task with retries and self-healing"""

        max_retries = 3
        attempt = 0

        while attempt < max_retries:
            try:
                # Execute task using browser-use agent
                result = await self.execute_browser_use_task(task)

                # Success - store snapshot and return
                await self.store_snapshot(run_id, task.target_name, result)

                return TaskResult(
                    task_id=task.id,
                    status='success',
                    content=result['content'],
                    screenshot_path=result['screenshot_path'],
                    content_hash=result['content_hash'],
                    url=result['url'],
                    timestamp=int(time.time())
                )

            except Exception as error:
                attempt += 1

                if attempt >= max_retries:
                    # Try self-healing with Claude
                    adapted_task = await self.adapt_task(task, error)

                    if adapted_task:
                        try:
                            result = await self.execute_browser_use_task(adapted_task)
                            await self.store_snapshot(run_id, task.target_name, result)

                            return TaskResult(
                                task_id=task.id,
                                status='success',
                                content=result['content'],
                                screenshot_path=result['screenshot_path'],
                                content_hash=result['content_hash'],
                                url=result['url'],
                                timestamp=int(time.time())
                            )
                        except Exception as e:
                            return TaskResult(
                                task_id=task.id,
                                status='failed',
                                error=str(e),
                                timestamp=int(time.time())
                            )

                    # Final failure
                    return TaskResult(
                        task_id=task.id,
                        status='failed',
                        error=str(error),
                        timestamp=int(time.time())
                    )

                # Exponential backoff
                await asyncio.sleep(2 ** attempt)

    async def execute_browser_use_task(self, task: BrowserTask) -> dict:
        """Execute a task using browser-use Agent"""

        # Create custom tools for this task
        tools = Tools()

        # Custom tool to save extracted content
        extracted_data = {}

        @tools.action('Save the extracted compliance content to return')
        async def save_content(content: str) -> ActionResult:
            extracted_data['content'] = content
            return ActionResult(
                extracted_content=content,
                is_done=True,
                success=True
            )

        # Build task prompt
        task_prompt = f"""
        {task.task_description}

        Target: {task.target_name}

        Instructions:
        1. {f"Search for: {task.search_query}" if task.search_query else f"Navigate to: {task.starting_url}"}
        2. {task.extraction_instructions}
        3. Use the save_content action to save what you extract
        4. Take a screenshot of the final page

        Be thorough and extract all relevant compliance information.
        """

        # Create browser-use agent with ChatBrowserUse LLM (optimized for browser automation)
        browser = Browser(
            headless=True,
            use_cloud=True,  # Use Browser-Use Cloud for production
        )

        agent = Agent(
            task=task_prompt,
            llm=self.browser_use_llm,  # ChatBrowserUse - fastest & most accurate
            browser=browser,
            tools=tools,
            max_steps=50,
            use_vision=True,  # Enable screenshots
        )

        # Run agent
        history = await agent.run()

        # Extract results
        final_result = history.final_result()
        screenshots = history.screenshots()
        urls = history.urls()

        # Save screenshot
        screenshot_path = None
        if screenshots:
            screenshot_path = await self.save_screenshot(
                screenshots[-1],
                task.id
            )

        # Hash content
        content = extracted_data.get('content') or final_result
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        return {
            'content': content,
            'screenshot_path': screenshot_path,
            'content_hash': content_hash,
            'url': urls[-1] if urls else None,
            'history': history
        }

    async def adapt_task(self, task: BrowserTask, error: Exception) -> Optional[BrowserTask]:
        """Use Claude to adapt a failed task with alternative strategy"""

        prompt = f"""
        This browser automation task failed:

        Task: {task.task_description}
        Target: {task.target_name}
        Starting URL: {task.starting_url}
        Search Query: {task.search_query}
        Error: {str(error)}

        Suggest an alternative approach that might work:
        1. Different search query?
        2. Different starting URL?
        3. Different navigation strategy?
        4. Use keyboard navigation instead of clicking?

        Provide a modified task configuration that might succeed.
        Return null if no viable alternative exists.
        """

        response = self.anthropic_client.messages.create(
            model="claude-sonnet-4-0",
            max_tokens=2048,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse adaptation
        adapted = self.parse_task_adaptation(response.content[0].text)

        if adapted:
            return BrowserTask(
                id=task.id,
                target_name=task.target_name,
                task_description=adapted['task_description'],
                starting_url=adapted.get('starting_url'),
                search_query=adapted.get('search_query'),
                extraction_instructions=adapted['extraction_instructions']
            )

        return None
```

### 2.2 Production Deployment with @sandbox

**Purpose:** Deploy browser-use agents to production using Browser-Use Cloud with automatic scaling, authentication handling, and proxies.

**Key Logic:**

```python
from browser_use import Browser, sandbox, ChatBrowserUse
from browser_use.agent.service import Agent
import asyncio


class ProductionWatchExecutor:
    """Production-ready watch execution using Browser-Use Cloud"""

    @sandbox(
        cloud_profile_id='compliance-monitor-profile',  # Synced cookies/auth
        cloud_proxy_country_code='us',  # Route through US proxy
        cloud_timeout=30  # 30 minute session timeout
    )
    async def execute_watch_in_production(self, browser: Browser, watch_config: dict):
        """
        Executes a compliance watch in production using Browser-Use Cloud.

        Benefits:
        - Automatic browser provisioning
        - Pre-authenticated with synced cookies
        - Bypasses captchas and bot detection
        - Low latency (agent runs next to browser)
        - Automatic cleanup
        """

        # Browser is already provisioned and authenticated
        agent = Agent(
            task=self.build_watch_task(watch_config),
            browser=browser,
            llm=ChatBrowserUse(),  # Optimized for browser automation
            use_vision=True,
            max_steps=100
        )

        history = await agent.run()

        return {
            'success': history.is_successful(),
            'extracted_content': history.extracted_content(),
            'screenshots': history.screenshot_paths(),
            'urls': history.urls(),
            'duration': history.total_duration_seconds()
        }

    def build_watch_task(self, watch_config: dict) -> str:
        """Build detailed task prompt from watch configuration"""

        targets = watch_config['targets']
        task_parts = [
            "You are a compliance monitoring agent. Your job is to check for changes in regulations and policies.",
            "",
            "Targets to monitor:"
        ]

        for i, target in enumerate(targets, 1):
            task_parts.append(f"\n{i}. {target['name']}")
            task_parts.append(f"   Description: {target['description']}")
            task_parts.append(f"   Search for: {target['search_query']}")
            task_parts.append(f"   Extract: {target['extraction_instructions']}")

        task_parts.append("\nFor each target:")
        task_parts.append("1. Navigate to the source (search if needed)")
        task_parts.append("2. Extract the current version of the regulation/policy")
        task_parts.append("3. Take a screenshot")
        task_parts.append("4. Use save_content to save the extracted text")
        task_parts.append("\nBe thorough and capture all relevant compliance information.")

        return "\n".join(task_parts)


# Usage in FastAPI endpoint
@app.post("/watches/{watch_id}/run")
async def run_watch_production(watch_id: str):
    """Run a watch in production using Browser-Use Cloud"""

    watch_config = await db.get_watch(watch_id)
    executor = ProductionWatchExecutor()

    # This runs in Browser-Use Cloud automatically
    result = await executor.execute_watch_in_production(watch_config=watch_config)

    return result
```

### 2.3 Custom Tools for Compliance Monitoring

**Purpose:** Domain-specific tools that browser-use agents can call during execution.

**Key Logic:**

```python
from browser_use import Tools, ActionResult
from browser_use.browser import BrowserSession
from pydantic import BaseModel, Field
from typing import List, Optional


class ComplianceTools(Tools):
    """Custom tools for compliance monitoring tasks"""

    def __init__(self):
        super().__init__()
        self.extracted_regulations = []

    @Tools.action(
        description='Extract regulation text from the current page with metadata',
        allowed_domains=['*.gov', '*.europa.eu', 'stripe.com', 'aws.amazon.com']
    )
    async def extract_regulation(
        self,
        regulation_name: str,
        regulation_text: str,
        effective_date: Optional[str] = None,
        section_number: Optional[str] = None,
        browser_session: BrowserSession = None
    ) -> ActionResult:
        """
        Extract and structure regulation content.

        Args:
            regulation_name: Name/title of the regulation
            regulation_text: Full text of the regulation section
            effective_date: When this regulation becomes effective
            section_number: Section or article number
            browser_session: Browser session for additional context
        """

        # Store extracted content
        self.extracted_regulations.append({
            'name': regulation_name,
            'text': regulation_text,
            'effective_date': effective_date,
            'section': section_number,
            'url': await browser_session.get_current_url() if browser_session else None
        })

        return ActionResult(
            extracted_content=f"Extracted {regulation_name}",
            long_term_memory=f"Found regulation: {regulation_name} (Section {section_number})",
            success=True
        )

    @Tools.action(
        description='Search for specific regulation by name or number on government sites',
        allowed_domains=['*.gov', '*.europa.eu']
    )
    async def search_regulation(
        self,
        regulation_identifier: str,
        jurisdiction: str = 'US',
        browser_session: BrowserSession = None
    ) -> ActionResult:
        """
        Search for a specific regulation.

        Args:
            regulation_identifier: Regulation name, number, or code (e.g., "GDPR Article 25")
            jurisdiction: Country/region code (US, EU, UK, etc.)
            browser_session: Browser session to perform searches
        """

        search_urls = {
            'US': 'https://www.regulations.gov/search',
            'EU': 'https://eur-lex.europa.eu/homepage.html',
            'UK': 'https://www.legislation.gov.uk/'
        }

        search_url = search_urls.get(jurisdiction, search_urls['US'])

        return ActionResult(
            extracted_content=f"Navigate to {search_url} and search for '{regulation_identifier}'",
            success=True
        )

    @Tools.action(
        description='Check if a page requires authentication or has anti-bot protection'
    )
    async def check_page_accessibility(
        self,
        browser_session: BrowserSession
    ) -> ActionResult:
        """Check if current page is accessible or blocked"""

        if browser_session:
            page_content = await browser_session.get_page_content()

            # Check for common blockers
            blockers = [
                'captcha',
                'cloudflare',
                'access denied',
                'forbidden',
                'please verify you are human'
            ]

            for blocker in blockers:
                if blocker.lower() in page_content.lower():
                    return ActionResult(
                        error=f"Page blocked by {blocker}",
                        extracted_content="Use alternative search strategy or wait before retrying",
                        success=False
                    )

        return ActionResult(
            extracted_content="Page is accessible",
            success=True
        )

    @Tools.action(
        description='Save compliance content with structured metadata for diffing'
    )
    async def save_compliance_snapshot(
        self,
        target_name: str,
        content: str,
        metadata: dict
    ) -> ActionResult:
        """Save a compliance snapshot with metadata"""

        snapshot = {
            'target_name': target_name,
            'content': content,
            'metadata': metadata,
            'timestamp': int(time.time()),
            'content_hash': hashlib.sha256(content.encode()).hexdigest()
        }

        # Store in database
        await self.db.save_snapshot(snapshot)

        return ActionResult(
            extracted_content=f"Saved snapshot for {target_name}",
            long_term_memory=f"Content hash: {snapshot['content_hash']}",
            success=True,
            is_done=True
        )


# Usage in agent
async def run_compliance_watch():
    compliance_tools = ComplianceTools()

    agent = Agent(
        task="Monitor GDPR Article 25 for changes",
        llm=ChatBrowserUse(),
        tools=compliance_tools,
        browser=Browser(use_cloud=True),
        max_steps=50
    )

    history = await agent.run()

    # Get extracted regulations
    regulations = compliance_tools.extracted_regulations

    return regulations
```

### 2.4 Diff Engine

**Purpose:** Detects changes between current and previous snapshots using hash comparison, text diffs, and Claude for semantic analysis.

**Key Logic:**

```python
from difflib import unified_diff
from anthropic import Anthropic
from pydantic import BaseModel
from typing import List, Optional
import hashlib


class TextDiff(BaseModel):
    """Text-level diff result"""
    additions: List[str]
    deletions: List[str]
    unchanged_lines: int
    total_changes: int


class SemanticDiff(BaseModel):
    """Claude-powered semantic diff"""
    summary: str
    impact_level: str  # 'low', 'medium', 'high', 'critical'
    sections_affected: List[str]
    recommended_actions: List[str]
    key_changes: List[dict]


class VisualDiff(BaseModel):
    """Screenshot comparison result"""
    pixel_diff_count: int
    diff_percentage: float
    diff_image_path: Optional[str]


class ChangeDetection(BaseModel):
    """Complete change detection result"""
    has_changes: bool
    text_diff: Optional[TextDiff]
    semantic_diff: Optional[SemanticDiff]
    visual_diff: Optional[VisualDiff]


class DiffEngine:
    """Engine for detecting and analyzing changes in compliance content"""

    def __init__(self):
        self.anthropic_client = Anthropic()

    async def detect_changes(
        self,
        current_snapshot: dict,
        previous_snapshot: dict
    ) -> ChangeDetection:
        """Detect changes between two snapshots"""

        # Quick hash comparison
        if current_snapshot['content_hash'] == previous_snapshot['content_hash']:
            return ChangeDetection(
                has_changes=False,
                text_diff=None,
                semantic_diff=None,
                visual_diff=None
            )

        # Compute text diff
        text_diff = self.compute_text_diff(
            previous_snapshot['content'],
            current_snapshot['content']
        )

        # Compute semantic diff using Claude
        semantic_diff = await self.compute_semantic_diff(
            previous_snapshot['content'],
            current_snapshot['content'],
            current_snapshot.get('target_name', 'Unknown')
        )

        # Compute visual diff if screenshots available
        visual_diff = None
        if current_snapshot.get('screenshot_path') and previous_snapshot.get('screenshot_path'):
            visual_diff = await self.compute_visual_diff(
                previous_snapshot['screenshot_path'],
                current_snapshot['screenshot_path']
            )

        return ChangeDetection(
            has_changes=True,
            text_diff=text_diff,
            semantic_diff=semantic_diff,
            visual_diff=visual_diff
        )

    def compute_text_diff(self, old_content: str, new_content: str) -> TextDiff:
        """Compute line-by-line text diff"""

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = list(unified_diff(old_lines, new_lines, lineterm=''))

        additions = [line[1:] for line in diff if line.startswith('+') and not line.startswith('+++')]
        deletions = [line[1:] for line in diff if line.startswith('-') and not line.startswith('---')]
        unchanged = len(old_lines) - len(deletions)

        return TextDiff(
            additions=additions,
            deletions=deletions,
            unchanged_lines=unchanged,
            total_changes=len(additions) + len(deletions)
        )

    async def compute_semantic_diff(
        self,
        old_content: str,
        new_content: str,
        target_name: str
    ) -> SemanticDiff:
        """Use Claude to analyze semantic changes and impact"""

        prompt = f"""
        Analyze these two versions of compliance document "{target_name}" and identify meaningful changes.

        PREVIOUS VERSION:
        {old_content[:4000]}  # Truncate if too long

        CURRENT VERSION:
        {new_content[:4000]}

        Provide a structured analysis:

        1. SUMMARY (2-3 sentences): What changed overall?

        2. IMPACT LEVEL: Rate as LOW, MEDIUM, HIGH, or CRITICAL based on:
           - LOW: Minor clarifications, typos, formatting
           - MEDIUM: Updated procedures, new examples, scope changes
           - HIGH: New requirements, deadline changes, significant policy shifts
           - CRITICAL: Major legal changes, immediate compliance requirements

        3. SECTIONS AFFECTED: List specific sections/articles that changed

        4. KEY CHANGES: For each major change, explain:
           - What changed
           - Why it matters for compliance
           - Potential business impact

        5. RECOMMENDED ACTIONS: Specific steps the compliance team should take

        Be concise and actionable. Focus on what matters for compliance officers.
        """

        response = self.anthropic_client.messages.create(
            model="claude-sonnet-4-0",
            max_tokens=2048,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
            system="You are a compliance expert analyzing regulatory changes. Be precise and actionable."
        )

        # Parse Claude's response
        analysis = self.parse_semantic_analysis(response.content[0].text)

        return SemanticDiff(
            summary=analysis['summary'],
            impact_level=analysis['impact_level'].lower(),
            sections_affected=analysis['sections_affected'],
            recommended_actions=analysis['recommended_actions'],
            key_changes=analysis['key_changes']
        )

    async def compute_visual_diff(
        self,
        old_screenshot_path: str,
        new_screenshot_path: str
    ) -> VisualDiff:
        """Compute pixel-level screenshot diff"""

        from PIL import Image
        import numpy as np

        # Load images
        old_img = Image.open(old_screenshot_path).convert('RGB')
        new_img = Image.open(new_screenshot_path).convert('RGB')

        # Ensure same size
        if old_img.size != new_img.size:
            new_img = new_img.resize(old_img.size)

        # Convert to numpy arrays
        old_array = np.array(old_img)
        new_array = np.array(new_img)

        # Compute pixel differences
        diff_array = np.abs(old_array - new_array)
        diff_pixels = np.sum(diff_array > 30)  # Threshold for significant difference
        total_pixels = old_array.size
        diff_percentage = (diff_pixels / total_pixels) * 100

        # Create diff image
        diff_image = Image.fromarray(diff_array.astype('uint8'))
        diff_image_path = f"/tmp/diff_{int(time.time())}.png"
        diff_image.save(diff_image_path)

        return VisualDiff(
            pixel_diff_count=int(diff_pixels),
            diff_percentage=round(diff_percentage, 2),
            diff_image_path=diff_image_path
        )

    def parse_semantic_analysis(self, claude_response: str) -> dict:
        """Parse Claude's semantic analysis into structured data"""

        # Simple parser - in production, use more robust parsing
        lines = claude_response.strip().split('\n')

        result = {
            'summary': '',
            'impact_level': 'medium',
            'sections_affected': [],
            'recommended_actions': [],
            'key_changes': []
        }

        current_section = None

        for line in lines:
            line = line.strip()

            if 'SUMMARY' in line.upper():
                current_section = 'summary'
            elif 'IMPACT LEVEL' in line.upper():
                current_section = 'impact'
            elif 'SECTIONS AFFECTED' in line.upper():
                current_section = 'sections'
            elif 'KEY CHANGES' in line.upper():
                current_section = 'changes'
            elif 'RECOMMENDED ACTIONS' in line.upper():
                current_section = 'actions'
            elif line.startswith('-') or line.startswith('•'):
                item = line.lstrip('-•').strip()
                if current_section == 'sections':
                    result['sections_affected'].append(item)
                elif current_section == 'actions':
                    result['recommended_actions'].append(item)
                elif current_section == 'changes':
                    result['key_changes'].append({'description': item})
            elif current_section == 'summary' and line:
                result['summary'] += line + ' '
            elif current_section == 'impact' and line:
                for level in ['critical', 'high', 'medium', 'low']:
                    if level.upper() in line.upper():
                        result['impact_level'] = level
                        break

        result['summary'] = result['summary'].strip()

        return result
```

### 2.5 Evidence Service

**Purpose:** Generates audit-ready evidence bundles with impact memos, diffs, screenshots, and cryptographic verification.

**Key Logic:**

```python
import boto3
import hashlib
import hmac
from anthropic import Anthropic
from pydantic import BaseModel
from typing import List, Optional
import json


class EvidenceBundle(BaseModel):
    """Complete evidence bundle for a detected change"""
    id: str
    run_id: str
    change_id: str
    timestamp: int
    impact_memo: str
    diff_summary: str
    screenshots: List[dict]
    content_hash: str
    audit_metadata: dict
    s3_urls: dict


class EvidenceService:
    """Service for generating and storing audit-ready evidence"""

    def __init__(self):
        self.anthropic_client = Anthropic()
        self.s3_client = boto3.client('s3')
        self.evidence_bucket = 'compliance-radar-evidence'
        self.secret_key = os.getenv('EVIDENCE_SIGNING_KEY')

    async def generate_evidence_bundle(
        self,
        change: ChangeDetection,
        current_snapshot: dict,
        previous_snapshot: dict,
        run_id: str
    ) -> EvidenceBundle:
        """Generate complete evidence bundle for a detected change"""

        bundle_id = self.generate_bundle_id()

        # Generate impact memo using Claude
        memo = await self.generate_impact_memo(
            change.semantic_diff,
            current_snapshot.get('target_name', 'Unknown')
        )

        # Upload screenshots to S3
        screenshot_urls = await self.upload_screenshots(
            bundle_id,
            current_snapshot.get('screenshot_path'),
            previous_snapshot.get('screenshot_path'),
            change.visual_diff.diff_image_path if change.visual_diff else None
        )

        # Upload text diff to S3
        diff_url = await self.upload_diff(
            bundle_id,
            change.text_diff,
            change.semantic_diff
        )

        # Generate audit metadata
        audit_metadata = self.generate_audit_metadata(
            current_snapshot,
            previous_snapshot,
            run_id
        )

        # Sign evidence bundle
        signature = self.sign_evidence(
            current_snapshot['content'],
            audit_metadata
        )

        audit_metadata['verification_signature'] = signature

        bundle = EvidenceBundle(
            id=bundle_id,
            run_id=run_id,
            change_id=change.id,
            timestamp=int(time.time()),
            impact_memo=memo,
            diff_summary=change.semantic_diff.summary,
            screenshots=screenshot_urls,
            content_hash=current_snapshot['content_hash'],
            audit_metadata=audit_metadata,
            s3_urls={
                'diff': diff_url,
                'screenshots': screenshot_urls
            }
        )

        # Store bundle in database
        await self.store_bundle(bundle)

        return bundle

    async def generate_impact_memo(
        self,
        semantic_diff: SemanticDiff,
        target_name: str
    ) -> str:
        """Generate professional impact memo using Claude"""

        prompt = f"""
        Generate a concise compliance impact memo for this detected change.

        Target: {target_name}
        Impact Level: {semantic_diff.impact_level.upper()}

        Change Summary:
        {semantic_diff.summary}

        Key Changes:
        {json.dumps(semantic_diff.key_changes, indent=2)}

        Sections Affected:
        {', '.join(semantic_diff.sections_affected)}

        Format the memo as follows:

        ## What Changed
        [2-3 sentences explaining the change in plain language]

        ## Why It Matters
        [2-3 sentences on compliance/business impact]

        ## Immediate Actions Required
        - [Specific action 1]
        - [Specific action 2]
        - [Specific action 3]

        ## Timeline
        [Expected timeline for review and implementation]

        Keep it professional, concise, and actionable for legal/compliance teams.
        """

        response = self.anthropic_client.messages.create(
            model="claude-sonnet-4-0",
            max_tokens=1500,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
            system="You are a compliance officer writing impact memos for legal teams."
        )

        return response.content[0].text

    async def upload_screenshots(
        self,
        bundle_id: str,
        current_screenshot: Optional[str],
        previous_screenshot: Optional[str],
        diff_image: Optional[str]
    ) -> List[dict]:
        """Upload screenshots to S3 and return URLs"""

        screenshot_urls = []

        uploads = [
            ('current', current_screenshot),
            ('previous', previous_screenshot),
            ('diff', diff_image)
        ]

        for screenshot_type, path in uploads:
            if path and os.path.exists(path):
                s3_key = f"evidence/{bundle_id}/screenshots/{screenshot_type}.png"

                self.s3_client.upload_file(
                    path,
                    self.evidence_bucket,
                    s3_key,
                    ExtraArgs={'ContentType': 'image/png'}
                )

                # Generate presigned URL (valid for 7 days)
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': self.evidence_bucket,
                        'Key': s3_key
                    },
                    ExpiresIn=604800  # 7 days
                )

                screenshot_urls.append({
                    'type': screenshot_type,
                    'url': url,
                    's3_key': s3_key
                })

        return screenshot_urls

    async def upload_diff(
        self,
        bundle_id: str,
        text_diff: TextDiff,
        semantic_diff: SemanticDiff
    ) -> str:
        """Upload structured diff to S3"""

        diff_content = {
            'text_diff': {
                'additions': text_diff.additions,
                'deletions': text_diff.deletions,
                'total_changes': text_diff.total_changes
            },
            'semantic_diff': {
                'summary': semantic_diff.summary,
                'impact_level': semantic_diff.impact_level,
                'sections_affected': semantic_diff.sections_affected,
                'key_changes': semantic_diff.key_changes,
                'recommended_actions': semantic_diff.recommended_actions
            }
        }

        s3_key = f"evidence/{bundle_id}/diff.json"

        self.s3_client.put_object(
            Bucket=self.evidence_bucket,
            Key=s3_key,
            Body=json.dumps(diff_content, indent=2),
            ContentType='application/json'
        )

        url = self.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.evidence_bucket, 'Key': s3_key},
            ExpiresIn=604800
        )

        return url

    def generate_audit_metadata(
        self,
        current_snapshot: dict,
        previous_snapshot: dict,
        run_id: str
    ) -> dict:
        """Generate comprehensive audit metadata"""

        return {
            'run_id': run_id,
            'current_snapshot_timestamp': current_snapshot['timestamp'],
            'previous_snapshot_timestamp': previous_snapshot['timestamp'],
            'source_url': current_snapshot.get('url'),
            'target_name': current_snapshot.get('target_name'),
            'content_integrity': {
                'algorithm': 'SHA-256',
                'current_hash': current_snapshot['content_hash'],
                'previous_hash': previous_snapshot['content_hash']
            },
            'capture_method': 'browser-use-agent',
            'capture_metadata': {
                'user_agent': 'Browser-Use Agent',
                'viewport': '1920x1080',
                'browser': 'Chromium'
            },
            'timestamp_utc': datetime.utcnow().isoformat()
        }

    def sign_evidence(self, content: str, metadata: dict) -> str:
        """Sign evidence with HMAC for integrity verification"""

        message = f"{content}|{json.dumps(metadata, sort_keys=True)}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        return signature

    def verify_evidence(
        self,
        content: str,
        metadata: dict,
        signature: str
    ) -> bool:
        """Verify evidence bundle integrity"""

        expected_signature = self.sign_evidence(content, metadata)
        return hmac.compare_digest(expected_signature, signature)
```

### 2.6 Notification Hub

**Purpose:** Manages integrations with Linear, Slack, and other notification channels.

**Implementation details for Linear, Slack, etc. remain the same as original design**

---

## 3. Database Setup (Supabase Local)

### 3.1 Supabase Local Setup Instructions

**Prerequisites:**
- Docker Desktop installed and running
- Node.js 18+ (for Supabase CLI)
- Python 3.11+ with uv

**Step 1: Install Supabase CLI**

```bash
# macOS/Linux
brew install supabase/tap/supabase

# Windows (via npm)
npm install -g supabase

# Verify installation
supabase --version
```

**Step 2: Initialize Supabase in this repository**

```bash
# Navigate to project root
cd /path/to/yc-browseruse

# Initialize Supabase (creates supabase/ directory)
supabase init

# This creates:
# - supabase/config.toml (Supabase configuration)
# - supabase/seed.sql (seed data)
# - supabase/migrations/ (database migrations)
```

**Step 3: Start Supabase Local Stack**

```bash
# Start all Supabase services (PostgreSQL, Auth, Realtime, Storage, etc.)
supabase start

# This will output:
# - API URL: http://localhost:54321
# - GraphQL URL: http://localhost:54321/graphql/v1
# - DB URL: postgresql://postgres:postgres@localhost:54322/postgres
# - Studio URL: http://localhost:54323 (Database GUI)
# - Inbucket URL: http://localhost:54324 (Email testing)
# - JWT secret, anon key, service_role key
```

**Step 4: Create Database Migrations**

Our migrations are in `supabase/migrations/` directory. They will be automatically run when you start Supabase.

**Step 5: Access Supabase Studio**

Open http://localhost:54323 in your browser to access the Supabase Studio (database GUI, similar to pgAdmin).

**Step 6: Stop Supabase**

```bash
# Stop all services
supabase stop

# Stop and reset database (WARNING: deletes all data)
supabase db reset
```

### 3.2 Database Schema (SQL Migrations)

**Migration: `supabase/migrations/20240101000000_initial_schema.sql`**

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Organizations table
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    product_description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users table (Supabase Auth integration)
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'viewer', -- admin, analyst, viewer
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

-- Watches table
CREATE TABLE watches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB NOT NULL,
    schedule JSONB NOT NULL,
    integrations JSONB,
    status VARCHAR(50) DEFAULT 'active', -- active, paused, archived
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ
);

-- Indexes for watches
CREATE INDEX idx_watches_org ON watches(organization_id);
CREATE INDEX idx_watches_status ON watches(status);
CREATE INDEX idx_watches_next_run ON watches(next_run_at) WHERE status = 'active';

-- Watch runs table
CREATE TABLE watch_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    watch_id UUID REFERENCES watches(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL, -- running, completed, failed, partial
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    tasks_executed INTEGER DEFAULT 0,
    tasks_failed INTEGER DEFAULT 0,
    changes_detected INTEGER DEFAULT 0,
    error_message TEXT
);

-- Indexes for watch_runs
CREATE INDEX idx_runs_watch ON watch_runs(watch_id);
CREATE INDEX idx_runs_started ON watch_runs(started_at DESC);
CREATE INDEX idx_runs_status ON watch_runs(status);

-- Snapshots table (captured content per target per run)
CREATE TABLE snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    watch_id UUID REFERENCES watches(id) ON DELETE CASCADE,
    run_id UUID REFERENCES watch_runs(id) ON DELETE CASCADE,
    target_name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    content_text TEXT,
    content_html TEXT,
    content_hash VARCHAR(64) NOT NULL, -- SHA-256
    screenshot_url TEXT,
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

-- Indexes for snapshots
CREATE INDEX idx_snapshots_watch ON snapshots(watch_id);
CREATE INDEX idx_snapshots_run ON snapshots(run_id);
CREATE INDEX idx_snapshots_target ON snapshots(watch_id, target_name);
CREATE INDEX idx_snapshots_hash ON snapshots(content_hash);

-- Changes table (detected diffs)
CREATE TABLE changes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    watch_id UUID REFERENCES watches(id) ON DELETE CASCADE,
    run_id UUID REFERENCES watch_runs(id) ON DELETE CASCADE,
    target_name VARCHAR(255) NOT NULL,
    previous_snapshot_id UUID REFERENCES snapshots(id),
    current_snapshot_id UUID REFERENCES snapshots(id),
    diff_summary TEXT,
    diff_details JSONB,
    impact_level VARCHAR(20), -- low, medium, high, critical
    detected_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for changes
CREATE INDEX idx_changes_watch ON changes(watch_id);
CREATE INDEX idx_changes_detected ON changes(detected_at DESC);
CREATE INDEX idx_changes_impact ON changes(impact_level);

-- Evidence bundles table
CREATE TABLE evidence_bundles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    change_id UUID REFERENCES changes(id) ON DELETE CASCADE,
    run_id UUID REFERENCES watch_runs(id),
    impact_memo TEXT,
    diff_url TEXT,
    screenshots JSONB,
    content_hash VARCHAR(64),
    audit_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for evidence_bundles
CREATE INDEX idx_evidence_change ON evidence_bundles(change_id);
CREATE INDEX idx_evidence_created ON evidence_bundles(created_at DESC);

-- Notifications table (audit trail)
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    change_id UUID REFERENCES changes(id) ON DELETE CASCADE,
    evidence_bundle_id UUID REFERENCES evidence_bundles(id),
    channel VARCHAR(50), -- linear, slack, email
    status VARCHAR(50), -- sent, failed, pending
    external_id VARCHAR(255),
    external_url TEXT,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    error_message TEXT
);

-- Indexes for notifications
CREATE INDEX idx_notifications_change ON notifications(change_id);
CREATE INDEX idx_notifications_status ON notifications(status);

-- Integrations table
CREATE TABLE integrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    service VARCHAR(50), -- linear, slack, jira
    config JSONB, -- encrypted API keys, team IDs, channels
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for integrations
CREATE INDEX idx_integrations_org ON integrations(organization_id);

-- Enable Row Level Security (RLS)
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE watches ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_bundles ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;

-- RLS Policies (users can only access data from their organization)
CREATE POLICY "Users can view their organization"
    ON organizations FOR SELECT
    USING (id IN (
        SELECT organization_id FROM users WHERE id = auth.uid()
    ));

CREATE POLICY "Users can view their organization's watches"
    ON watches FOR ALL
    USING (organization_id IN (
        SELECT organization_id FROM users WHERE id = auth.uid()
    ));

CREATE POLICY "Users can view their organization's runs"
    ON watch_runs FOR SELECT
    USING (watch_id IN (
        SELECT id FROM watches WHERE organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    ));

-- Similar policies for other tables...
CREATE POLICY "Users can view their organization's snapshots"
    ON snapshots FOR SELECT
    USING (watch_id IN (
        SELECT id FROM watches WHERE organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    ));

CREATE POLICY "Users can view their organization's changes"
    ON changes FOR SELECT
    USING (watch_id IN (
        SELECT id FROM watches WHERE organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    ));
```

**Migration: `supabase/migrations/20240101000001_realtime.sql`**

```sql
-- Enable Realtime for live updates
ALTER PUBLICATION supabase_realtime ADD TABLE watches;
ALTER PUBLICATION supabase_realtime ADD TABLE watch_runs;
ALTER PUBLICATION supabase_realtime ADD TABLE changes;

-- Create triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_watches_updated_at BEFORE UPDATE ON watches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_integrations_updated_at BEFORE UPDATE ON integrations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

**Seed Data: `supabase/seed.sql`**

```sql
-- Insert demo organization
INSERT INTO organizations (id, name, product_description)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Demo Company',
    'B2B SaaS platform that processes EU customer data and integrates with Stripe for payments'
);

-- Note: Users will be created via Supabase Auth signup flow
-- You can manually insert a user for testing:
-- INSERT INTO users (id, organization_id, email, name, role)
-- VALUES (
--     auth.uid(), -- Replace with actual user ID from auth.users
--     '00000000-0000-0000-0000-000000000001',
--     'demo@example.com',
--     'Demo User',
--     'admin'
-- );
```

### 3.3 Supabase Configuration

**File: `supabase/config.toml`**

```toml
# Supabase local development configuration

[api]
port = 54321
schemas = ["public", "storage"]
extra_search_path = ["public", "extensions"]
max_rows = 1000

[db]
port = 54322
shadow_port = 54320
major_version = 15

[studio]
port = 54323

[inbucket]
port = 54324

[storage]
file_size_limit = "50MiB"

[auth]
site_url = "http://localhost:3000"
additional_redirect_urls = ["http://localhost:3000/**"]
jwt_expiry = 3600
enable_signup = true

[auth.email]
enable_signup = true
double_confirm_changes = true
enable_confirmations = false # Set to true in production
```

### 3.4 Environment Variables for Backend

**File: `.env`**

```bash
# Supabase (get these from `supabase start` output)
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=your_anon_key_from_supabase_start
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_from_supabase_start
SUPABASE_DB_URL=postgresql://postgres:postgres@localhost:54322/postgres

# Browser-Use
BROWSER_USE_API_KEY=your_browser_use_api_key

# Anthropic (for orchestrator)
ANTHROPIC_API_KEY=your_anthropic_api_key

# Redis
REDIS_URL=redis://localhost:6379

# AWS S3 (or use Supabase Storage)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1
S3_EVIDENCE_BUCKET=compliance-radar-evidence

# OR use Supabase Storage
USE_SUPABASE_STORAGE=true

# Linear
LINEAR_API_KEY=lin_api_xxx

# Slack
SLACK_BOT_TOKEN=xoxb-xxx
SLACK_SIGNING_SECRET=xxx

# Evidence signing
EVIDENCE_SIGNING_KEY=your_secret_key_for_hmac

# Telemetry
ANONYMIZED_TELEMETRY=true
```

### 3.5 Python Supabase Client Setup

**Install dependencies:**

```bash
uv pip install supabase
uv pip install postgrest-py
```

**Database client wrapper: `backend/db/client.py`**

```python
from supabase import create_client, Client
from typing import Optional
import os

class SupabaseClient:
    """Wrapper for Supabase client"""

    _instance: Optional[Client] = None

    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client singleton"""
        if cls._instance is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Use service role for backend

            if not url or not key:
                raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

            cls._instance = create_client(url, key)

        return cls._instance

# Usage
supabase = SupabaseClient.get_client()

# Query examples
async def get_watch(watch_id: str):
    response = supabase.table('watches').select('*').eq('id', watch_id).execute()
    return response.data[0] if response.data else None

async def create_watch(data: dict):
    response = supabase.table('watches').insert(data).execute()
    return response.data[0]

async def get_watch_runs(watch_id: str, limit: int = 50):
    response = (
        supabase.table('watch_runs')
        .select('*')
        .eq('watch_id', watch_id)
        .order('started_at', desc=True)
        .limit(limit)
        .execute()
    )
    return response.data
```

### 3.6 Frontend Supabase Client Setup

**Install dependencies:**

```bash
npm install @supabase/supabase-js
```

**Client setup: `lib/supabase/client.ts`**

```typescript
import { createClient } from '@supabase/supabase-js'
import { Database } from './database.types'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient<Database>(supabaseUrl, supabaseAnonKey)

// Realtime subscription example
export function subscribeToWatchUpdates(
  watchId: string,
  callback: (payload: any) => void
) {
  return supabase
    .channel(`watch:${watchId}`)
    .on(
      'postgres_changes',
      {
        event: '*',
        schema: 'public',
        table: 'watch_runs',
        filter: `watch_id=eq.${watchId}`
      },
      callback
    )
    .subscribe()
}
```

**Generate TypeScript types:**

```bash
# Generate types from your Supabase schema
supabase gen types typescript --local > lib/supabase/database.types.ts
```

### 3.7 Supabase Storage (Alternative to AWS S3)

If using Supabase Storage instead of AWS S3:

**Create storage buckets:**

```sql
-- Run in Supabase Studio SQL Editor or migration file

-- Create evidence bucket
INSERT INTO storage.buckets (id, name, public)
VALUES ('evidence', 'evidence', false);

-- Create storage policy (RLS)
CREATE POLICY "Users can upload evidence"
ON storage.objects FOR INSERT
WITH CHECK (
    bucket_id = 'evidence' AND
    auth.role() = 'authenticated'
);

CREATE POLICY "Users can view their org's evidence"
ON storage.objects FOR SELECT
USING (
    bucket_id = 'evidence' AND
    auth.role() = 'authenticated'
);
```

**Python client for Supabase Storage:**

```python
from supabase import Client

async def upload_screenshot(client: Client, file_path: str, bundle_id: str) -> str:
    """Upload screenshot to Supabase Storage"""

    with open(file_path, 'rb') as f:
        file_data = f.read()

    storage_path = f"evidence/{bundle_id}/screenshot.png"

    response = client.storage.from_('evidence').upload(
        storage_path,
        file_data,
        file_options={"content-type": "image/png"}
    )

    # Get public URL (signed)
    url = client.storage.from_('evidence').create_signed_url(
        storage_path,
        expires_in=604800  # 7 days
    )

    return url['signedURL']
```

### 3.8 Running Migrations

```bash
# Create a new migration
supabase migration new add_new_feature

# Run all pending migrations
supabase db reset  # This also runs migrations

# Or just push migrations without reset
supabase db push

# Check migration status
supabase migration list
```

---

## 4. Frontend Pages

### 4.1 Dashboard

**Same as original design with beautiful UI components**

### 4.2 Watch Manager

**Same as original design with wizard flow**

### 4.3 Watch Detail Page

**Same as original design with tabs and analytics**

### 4.4 Evidence Viewer

**Same as original design with diff viewer and audit trail**

### 4.5 Settings Page

**Same as original design with integrations**

---

## 5. API Specifications

### 5.1 REST API Endpoints

```python
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional


app = FastAPI(title="Compliance Radar API")


class CreateWatchRequest(BaseModel):
    name: str
    description: Optional[str]
    type: str  # 'regulation', 'vendor', 'internal', 'custom'
    config: dict
    integrations: dict


class WatchResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    status: str
    next_run_at: Optional[int]
    total_runs: int
    total_changes: int


@app.post("/api/watches", response_model=WatchResponse)
async def create_watch(request: CreateWatchRequest):
    """Create a new compliance watch"""

    watch = await watch_service.create_watch(
        name=request.name,
        description=request.description,
        type=request.type,
        config=request.config,
        integrations=request.integrations
    )

    # Schedule watch
    await scheduler.schedule_watch(watch.id)

    return watch


@app.post("/api/watches/{watch_id}/run")
async def run_watch_now(watch_id: str, background_tasks: BackgroundTasks):
    """Trigger immediate watch execution"""

    watch = await watch_service.get_watch(watch_id)

    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")

    # Queue watch execution in background
    background_tasks.add_task(execute_watch_background, watch_id)

    return {
        "status": "queued",
        "watch_id": watch_id,
        "message": "Watch execution started"
    }


async def execute_watch_background(watch_id: str):
    """Background task to execute watch using browser-use"""

    orchestrator = OrchestratorEngine()
    result = await orchestrator.execute_watch(watch_id)

    # Send WebSocket update
    await websocket_manager.broadcast_watch_update(watch_id, result)


@app.get("/api/watches/{watch_id}/history")
async def get_watch_history(watch_id: str, limit: int = 50):
    """Get watch execution history"""

    runs = await db.get_watch_runs(watch_id, limit=limit)

    return {
        "watch_id": watch_id,
        "runs": runs,
        "total": len(runs)
    }


@app.get("/api/evidence/{bundle_id}")
async def get_evidence_bundle(bundle_id: str):
    """Get evidence bundle with presigned URLs"""

    bundle = await evidence_service.get_bundle(bundle_id)

    if not bundle:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")

    # Refresh presigned URLs if expired
    bundle = await evidence_service.refresh_urls(bundle)

    return bundle
```

### 5.2 WebSocket Events

```python
from fastapi import WebSocket
from typing import Dict


class WebSocketManager:
    """Manage WebSocket connections for real-time updates"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    async def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def broadcast_watch_update(self, watch_id: str, data: dict):
        """Broadcast watch status update to all connected clients"""

        message = {
            "type": "watch.update",
            "watch_id": watch_id,
            "data": data
        }

        for connection in self.active_connections.values():
            await connection.send_json(message)

    async def send_run_progress(self, run_id: str, progress: int, current_task: str):
        """Send run progress update"""

        message = {
            "type": "run.progress",
            "run_id": run_id,
            "progress": progress,
            "current_task": current_task
        }

        for connection in self.active_connections.values():
            await connection.send_json(message)


websocket_manager = WebSocketManager()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket_manager.connect(websocket, client_id)

    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()

            # Handle client messages if needed
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        await websocket_manager.disconnect(client_id)
```

---

## 6. Integration Details

### 6.1 Linear Integration

**Same as original design**

### 6.2 Slack Integration

**Same as original design**

---

## 7. Implementation Details

### 7.1 Complete Tech Stack

**Backend:**
```bash
# Python 3.11+ with uv package manager
uv venv --python 3.11
source .venv/bin/activate

# Core dependencies
uv pip install fastapi uvicorn
uv pip install browser-use  # AI browser automation
uv pip install anthropic    # Claude API
uv pip install sqlalchemy asyncpg  # PostgreSQL
uv pip install redis celery  # Job queue
uv pip install boto3  # AWS S3
uv pip install pydantic  # Type safety
uv pip install python-multipart  # File uploads
```

**Frontend:**
```bash
# Next.js 14 with TypeScript
npx create-next-app@latest compliance-radar --typescript --tailwind --app

# UI components
npm install @radix-ui/react-* # Primitives
npm install framer-motion  # Animations
npm install recharts  # Charts
npm install react-query  # Data fetching
npm install zustand  # State management
```

### 7.2 Environment Variables

```bash
# .env file

# Browser-Use (recommended for production)
BROWSER_USE_API_KEY=your_browser_use_api_key

# Anthropic (for orchestrator)
ANTHROPIC_API_KEY=your_anthropic_api_key

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/compliance_radar

# Redis
REDIS_URL=redis://localhost:6379

# AWS S3
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1
S3_EVIDENCE_BUCKET=compliance-radar-evidence

# Linear
LINEAR_API_KEY=lin_api_xxx

# Slack
SLACK_BOT_TOKEN=xoxb-xxx
SLACK_SIGNING_SECRET=xxx

# Evidence signing
EVIDENCE_SIGNING_KEY=your_secret_key_for_hmac

# Telemetry (optional)
ANONYMIZED_TELEMETRY=true
```

### 7.3 Deployment with Docker

```dockerfile
# Dockerfile

FROM python:3.11-slim

# Install uv
RUN pip install uv

# Install Chromium for browser-use
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependencies
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Install browser-use chromium
RUN uvx browser-use install

# Copy application
COPY . .

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml

version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/compliance_radar
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    volumes:
      - ./:/app

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: compliance_radar
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  worker:
    build: .
    command: celery -A tasks worker --loglevel=info
    depends_on:
      - redis
      - db
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/compliance_radar
      - REDIS_URL=redis://redis:6379

volumes:
  postgres_data:
```

### 7.4 Production Deployment with Browser-Use Cloud

```python
# production_deployment.py

from browser_use import sandbox, Browser, ChatBrowserUse
from browser_use.agent.service import Agent
import asyncio


# Step 1: Sync local cookies to cloud (one-time setup)
# Run: export BROWSER_USE_API_KEY=xxx && curl -fsSL https://browser-use.com/profile.sh | sh
# This gives you a cloud_profile_id


# Step 2: Deploy with @sandbox decorator
@sandbox(
    cloud_profile_id='your-profile-id-from-step-1',
    cloud_proxy_country_code='us',  # Route through US
    cloud_timeout=30  # 30 min session
)
async def execute_compliance_watch(browser: Browser, watch_config: dict):
    """
    Production-ready watch execution.

    Benefits:
    - Runs in Browser-Use Cloud (fast, scalable)
    - Pre-authenticated with synced cookies
    - Bypasses captchas/bot-detection
    - Low latency (agent runs next to browser)
    """

    tools = ComplianceTools()

    agent = Agent(
        task=build_watch_task(watch_config),
        browser=browser,
        llm=ChatBrowserUse(),  # Optimized for browser automation
        tools=tools,
        use_vision=True,
        max_steps=100
    )

    history = await agent.run()

    return {
        'success': history.is_successful(),
        'content': history.extracted_content(),
        'screenshots': history.screenshot_paths(),
        'duration': history.total_duration_seconds()
    }


# Step 3: Call from FastAPI
@app.post("/watches/{watch_id}/run")
async def run_watch_production(watch_id: str):
    watch_config = await db.get_watch(watch_id)

    # Automatically runs in Browser-Use Cloud
    result = await execute_compliance_watch(watch_config=watch_config)

    return result
```

### 7.5 Performance Optimizations

**Browser-Use Optimizations:**
```python
# Use flash_mode for faster execution (no thinking/evaluation)
agent = Agent(
    task="Quick compliance check",
    llm=ChatBrowserUse(),
    flash_mode=True,  # 30-50% faster
    max_steps=50
)

# Use smaller LLM for page extraction
agent = Agent(
    task="Extract regulation",
    llm=ChatBrowserUse(),
    page_extraction_llm=ChatBrowserUse(model='fast'),  # Smaller model for extraction
    use_vision='auto'  # Only use vision when requested
)

# Reuse browser instances
browser = Browser(use_cloud=True, keep_alive=True)

agents = [
    Agent(task=task1, browser=browser, llm=llm),
    Agent(task=task2, browser=browser, llm=llm),
]

for agent in agents:
    await agent.run()

await browser.close()
```

**Caching:**
- Redis cache for watch configs (TTL: 5 min)
- Redis cache for recent run results (TTL: 1 hour)
- S3 CloudFront distribution for evidence files
- Database connection pooling (SQLAlchemy async pool)

**Parallelization:**
- Execute independent watch tasks in parallel using asyncio.gather
- Use Celery for distributed task execution across workers
- Browser-Use Cloud auto-scales browser instances

### 7.6 Security Considerations

1. **API Keys**: All encrypted at rest using AWS KMS
2. **Evidence Integrity**: HMAC signatures for all evidence bundles
3. **Row-Level Security**: PostgreSQL RLS for multi-tenant isolation
4. **Rate Limiting**: Per-user and per-watch rate limits
5. **Browser Security**: Browser-Use handles sandboxing automatically
6. **Proxy Support**: Use cloud proxies to avoid IP blocking
7. **CORS**: Strict CORS policy for API endpoints

### 7.7 Monitoring & Logging

```python
import logging
from browser_use import Agent

# Enable browser-use logging
logging.basicConfig(level=logging.DEBUG)
os.environ['BROWSER_USE_LOGGING_LEVEL'] = 'debug'

# Track costs
agent = Agent(
    task="...",
    llm=ChatBrowserUse(),
    calculate_cost=True  # Track API costs
)

history = await agent.run()

# Get cost info
print(f"Total cost: ${history.total_cost()}")
```

**Telemetry:**
- Browser-Use has built-in PostHog telemetry (opt-out available)
- Custom metrics: watch execution time, success rate, changes detected
- CloudWatch dashboards for API performance
- Sentry for error tracking

---

## 8. Example: Complete Watch Execution Flow

```python
# complete_example.py

from browser_use import Agent, Browser, ChatBrowserUse, Tools, ActionResult
from browser_use.browser import BrowserSession
from anthropic import Anthropic
import asyncio


class ComplianceWatchExecutor:
    """Complete example of watch execution"""

    def __init__(self):
        self.anthropic_client = Anthropic()
        self.browser_use_llm = ChatBrowserUse()

    async def execute_gdpr_watch(self):
        """Example: Monitor GDPR Article 25 for changes"""

        # Step 1: Create custom tools
        tools = Tools()

        extracted_content = {}

        @tools.action('Save extracted GDPR article content')
        async def save_gdpr_content(
            article_number: str,
            article_text: str,
            effective_date: str,
            browser_session: BrowserSession
        ) -> ActionResult:
            extracted_content['article'] = article_number
            extracted_content['text'] = article_text
            extracted_content['date'] = effective_date
            extracted_content['url'] = await browser_session.get_current_url()

            return ActionResult(
                extracted_content=f"Saved GDPR Article {article_number}",
                success=True,
                is_done=True
            )

        # Step 2: Create browser-use agent
        browser = Browser(
            use_cloud=True,  # Use Browser-Use Cloud
            headless=True
        )

        task = """
        Monitor GDPR Article 25 (Data protection by design and by default).

        Steps:
        1. Search for "GDPR Article 25 official text" on Google
        2. Navigate to the official EUR-Lex page
        3. Extract the complete text of Article 25
        4. Note the effective date
        5. Use save_gdpr_content action to save the results
        6. Take a screenshot of the article
        """

        agent = Agent(
            task=task,
            llm=self.browser_use_llm,
            browser=browser,
            tools=tools,
            use_vision=True,
            max_steps=50
        )

        # Step 3: Execute agent
        history = await agent.run()

        # Step 4: Get results
        if history.is_successful():
            # Hash content
            content_hash = hashlib.sha256(
                extracted_content['text'].encode()
            ).hexdigest()

            # Save screenshot
            screenshots = history.screenshots()
            screenshot_path = await self.save_screenshot(
                screenshots[-1] if screenshots else None
            )

            # Create snapshot
            snapshot = {
                'target_name': 'GDPR Article 25',
                'content': extracted_content['text'],
                'content_hash': content_hash,
                'url': extracted_content['url'],
                'screenshot_path': screenshot_path,
                'timestamp': int(time.time()),
                'metadata': {
                    'article': extracted_content['article'],
                    'effective_date': extracted_content['date']
                }
            }

            # Step 5: Compare with previous snapshot
            previous = await self.get_previous_snapshot('GDPR Article 25')

            if previous:
                diff_engine = DiffEngine()
                change = await diff_engine.detect_changes(snapshot, previous)

                if change.has_changes:
                    # Step 6: Generate evidence
                    evidence_service = EvidenceService()
                    evidence = await evidence_service.generate_evidence_bundle(
                        change,
                        snapshot,
                        previous,
                        run_id='example-run-123'
                    )

                    # Step 7: Send notifications
                    await self.send_linear_ticket(evidence)
                    await self.send_slack_alert(evidence)

                    print(f"Change detected! Evidence bundle: {evidence.id}")
                else:
                    print("No changes detected")
            else:
                # First run - just save snapshot
                await self.save_snapshot(snapshot)
                print("First run - baseline snapshot saved")

        else:
            print(f"Agent failed: {history.errors()}")

        await browser.close()


# Run example
async def main():
    executor = ComplianceWatchExecutor()
    await executor.execute_gdpr_watch()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 9. Future Enhancements

### 9.1 Phase 2 Features

- **Multi-language Support**: Monitor regulations in multiple languages
- **AI Chat Interface**: Natural language queries about compliance changes
- **Compliance Knowledge Graph**: Visualize regulation relationships
- **Bulk Watch Creation**: CSV upload for creating multiple watches
- **Advanced Scheduling**: Time-aware (avoid weekends, holidays)
- **Webhook Support**: Custom webhooks for change notifications

### 9.2 Phase 3 Features

- **Automated Impact Scoring**: ML model to predict business impact
- **Change Simulation**: Preview what would be detected before creating watch
- **Collaborative Annotations**: Team notes on evidence bundles
- **Compliance Calendar**: Visualize upcoming effective dates
- **Public API**: Third-party integrations

---

## Appendix: Browser-Use Best Practices

### A.1 Prompting for Compliance Tasks

```python
# ✅ GOOD: Specific, actionable prompts
task = """
1. Navigate to https://eur-lex.europa.eu
2. Use search action to find "GDPR Article 25"
3. Click the first official result
4. Use extract action to get the article text
5. Use save_content to save the extracted text
6. Take a screenshot
"""

# ❌ BAD: Vague prompts
task = "Find GDPR stuff"
```

### A.2 Error Handling

```python
# Handle common browser-use errors
try:
    history = await agent.run()

    if not history.is_successful():
        errors = history.errors()

        # Check for specific errors
        if any('timeout' in str(e).lower() for e in errors if e):
            # Retry with longer timeout
            agent.step_timeout = 180
            history = await agent.run()

        elif any('captcha' in str(e).lower() for e in errors if e):
            # Use cloud proxy
            browser = Browser(
                use_cloud=True,
                cloud_proxy_country_code='us'
            )
            agent.browser = browser
            history = await agent.run()

except Exception as e:
    logger.error(f"Agent execution failed: {e}")
    # Fallback to manual investigation
```

### A.3 Performance Tips

1. **Use ChatBrowserUse**: 3-5x faster than other LLMs for browser automation
2. **Enable flash_mode**: 30-50% faster for simple tasks
3. **Use Browser-Use Cloud**: Lowest latency, handles captchas
4. **Reuse browser instances**: Don't create new browser for each task
5. **Limit max_steps**: Set reasonable limits (30-50 for most tasks)
6. **Use vision selectively**: `use_vision='auto'` instead of `True`

---

**End of Technical Design Document**

*This document provides a complete, production-ready architecture for building Compliance Change Radar using browser-use for AI-powered browser automation, Claude for orchestration, and modern web technologies for the frontend.*

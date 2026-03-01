"""Detects changes between snapshots: hash, text diff, Claude semantic diff.

Uses Anthropic Claude for semantic analysis (summary, impact level, sections affected,
key changes, recommended actions) for compliance-focused change detection.
"""
import json
import logging
import re
from difflib import unified_diff
from typing import Any, Dict, List, Optional

from app.config import get_config

logger = logging.getLogger(__name__)


class DiffEngine:
    """Engine for detecting and analyzing changes in compliance content."""

    def __init__(self):
        self._anthropic = None
        self._config = get_config()

    def _get_anthropic(self):
        if self._anthropic is None and self._config.get("anthropic_api_key"):
            from anthropic import Anthropic
            self._anthropic = Anthropic(api_key=self._config["anthropic_api_key"])
        return self._anthropic

    async def detect_changes(
        self,
        current_snapshot: Dict[str, Any],
        previous_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Detect changes between two snapshots. Returns dict with has_changes, text_diff, semantic_diff."""
        curr_hash = current_snapshot.get("content_hash")
        prev_hash = previous_snapshot.get("content_hash")
        if curr_hash and prev_hash and curr_hash == prev_hash:
            return {
                "has_changes": False,
                "text_diff": None,
                "semantic_diff": None,
            }

        old_content = previous_snapshot.get("content_text") or previous_snapshot.get("content", "") or ""
        new_content = current_snapshot.get("content_text") or current_snapshot.get("content", "") or ""

        text_diff = self._compute_text_diff(old_content, new_content)

        # Only run semantic diff if there are meaningful text changes
        semantic_diff = None
        if text_diff.get("total_changes", 0) > 0:
            semantic_diff = await self._compute_semantic_diff(
                old_content, new_content,
                current_snapshot.get("target_name", "Unknown"),
            )

        return {
            "has_changes": True,
            "text_diff": text_diff,
            "semantic_diff": semantic_diff,
        }

    def _compute_text_diff(self, old_content: str, new_content: str) -> Dict[str, Any]:
        old_lines = old_content.splitlines(keepends=True) or [""]
        new_lines = new_content.splitlines(keepends=True) or [""]
        diff = list(unified_diff(old_lines, new_lines, lineterm=""))
        additions = [line[1:].rstrip("\n") for line in diff if line.startswith("+") and not line.startswith("+++")]
        deletions = [line[1:].rstrip("\n") for line in diff if line.startswith("-") and not line.startswith("---")]
        return {
            "additions": additions,
            "deletions": deletions,
            "unchanged_lines": max(0, len(old_lines) - len(deletions)),
            "total_changes": len(additions) + len(deletions),
        }

    async def _compute_semantic_diff(
        self,
        old_content: str,
        new_content: str,
        target_name: str,
    ) -> Optional[Dict[str, Any]]:
        client = self._get_anthropic()
        if not client:
            raise RuntimeError("ANTHROPIC_API_KEY required for semantic diff")

        prompt = f"""Analyze these two versions of compliance document "{target_name}" and identify meaningful changes.

PREVIOUS VERSION:
{old_content[:6000]}

CURRENT VERSION:
{new_content[:6000]}

Return your analysis as JSON with this exact structure:
{{
  "summary": "2-3 sentence summary of what changed",
  "impact_level": "low|medium|high|critical",
  "sections_affected": ["list", "of", "sections"],
  "key_changes": [
    {{"description": "what changed", "significance": "why it matters"}}
  ],
  "recommended_actions": ["specific step 1", "specific step 2"]
}}

Impact levels:
- low: Minor clarifications, typos, formatting
- medium: Updated procedures, new examples, scope changes
- high: New requirements, deadline changes, significant policy shifts
- critical: Major legal changes, immediate compliance requirements

Return ONLY the JSON, no other text."""

        response = client.messages.create(
            model=self._config.get("claude_model", "claude-sonnet-4-20250514"),
            max_tokens=2048,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
            system="You are a compliance expert analyzing regulatory changes. Return only valid JSON.",
        )
        text = response.content[0].text if response.content else "{}"
        return self._parse_json_response(text)

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from Claude response, handling markdown fences."""
        text = text.strip()
        # Strip markdown code fences
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                text = match.group(1).strip()
        # Find JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(text[start:end + 1])
            return {
                "summary": data.get("summary", ""),
                "impact_level": data.get("impact_level", "medium"),
                "sections_affected": data.get("sections_affected", []),
                "key_changes": data.get("key_changes", []),
                "recommended_actions": data.get("recommended_actions", []),
            }
        return {}

    async def generate_compliance_summary(
        self,
        change_details: Dict[str, Any],
        regulation_title: str,
        research_findings: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generate AI summary of how to comply with the detected regulatory change.

        Args:
            change_details: The detected change (text_diff, semantic_diff)
            regulation_title: Title of the regulation
            research_findings: Optional research data from additional browser agents

        Returns:
            String summary of compliance actions to take
        """
        client = self._get_anthropic()
        if not client:
            raise RuntimeError("ANTHROPIC_API_KEY required for compliance summary")

        semantic_diff = change_details.get("semantic_diff") or {}
        research_context = ""
        if research_findings:
            research_context = "\n\nADDITIONAL RESEARCH FINDINGS:\n"
            for i, finding in enumerate(research_findings[:5], 1):
                research_context += f"\n{i}. {finding.get('summary', finding.get('content', '')[:500])}"

        prompt = f"""You are a compliance expert. A regulatory change has been detected in {regulation_title}.

CHANGE SUMMARY:
{semantic_diff.get('summary', 'Content has changed')}

IMPACT LEVEL: {semantic_diff.get('impact_level', 'medium')}

KEY CHANGES:
{json.dumps(semantic_diff.get('key_changes', []), indent=2)}

SECTIONS AFFECTED:
{', '.join(semantic_diff.get('sections_affected', []))}
{research_context}

Provide a clear, actionable summary of HOW TO COMPLY with this regulatory change.

Focus on:
1. Immediate actions required
2. Timeline for compliance
3. Resources needed
4. Risk mitigation steps
5. Who should be involved

Be specific and practical. Return 3-5 paragraphs of actionable guidance."""

        response = client.messages.create(
            model=self._config.get("claude_model", "claude-sonnet-4-20250514"),
            max_tokens=2048,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
            system="You are a compliance expert providing actionable guidance.",
        )
        text = response.content[0].text if response.content else ""
        return text.strip()

    async def generate_change_summary(
        self,
        old_content: str,
        new_content: str,
        regulation_title: str,
        research_findings: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generate AI summary of what changed in the regulation.

        Args:
            old_content: Previous regulation text
            new_content: Current regulation text
            regulation_title: Title of the regulation
            research_findings: Optional research data from additional browser agents

        Returns:
            String summary of the change
        """
        client = self._get_anthropic()
        if not client:
            raise RuntimeError("ANTHROPIC_API_KEY required for change summary")

        research_context = ""
        if research_findings:
            research_context = "\n\nADDITIONAL CONTEXT FROM RESEARCH:\n"
            for i, finding in enumerate(research_findings[:5], 1):
                research_context += f"\n{i}. {finding.get('summary', finding.get('content', '')[:500])}"

        prompt = f"""Summarize the regulatory change in {regulation_title}.

PREVIOUS VERSION (excerpt):
{old_content[:3000]}

CURRENT VERSION (excerpt):
{new_content[:3000]}
{research_context}

Provide a clear, detailed summary of WHAT CHANGED.

Include:
1. What was added, removed, or modified
2. Why the change likely occurred (context from news, guidance, etc.)
3. Scope and applicability of the change
4. Effective date if mentioned

Be clear and factual. Return 2-4 paragraphs."""

        response = client.messages.create(
            model=self._config.get("claude_model", "claude-sonnet-4-20250514"),
            max_tokens=2048,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
            system="You are a compliance expert explaining regulatory changes.",
        )
        text = response.content[0].text if response.content else ""
        return text.strip()

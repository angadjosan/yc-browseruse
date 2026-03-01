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
            client = self._get_anthropic()
            if client:
                semantic_diff = await self._compute_semantic_diff(
                    old_content, new_content,
                    current_snapshot.get("target_name", "Unknown"),
                )

        # If no semantic diff available, build a basic one
        if not semantic_diff and text_diff.get("total_changes", 0) > 0:
            semantic_diff = {
                "summary": f"{text_diff['total_changes']} line(s) changed ({len(text_diff.get('additions', []))} added, {len(text_diff.get('deletions', []))} removed).",
                "impact_level": "medium",
                "sections_affected": [],
                "key_changes": [],
                "recommended_actions": ["Review the changes manually."],
            }

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
            return None

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

        try:
            response = client.messages.create(
                model=self._config.get("claude_model", "claude-sonnet-4-20250514"),
                max_tokens=2048,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
                system="You are a compliance expert analyzing regulatory changes. Return only valid JSON.",
            )
            text = response.content[0].text if response.content else "{}"
            return self._parse_json_response(text)
        except Exception:
            logger.exception("Semantic diff failed")
            return {
                "summary": "Semantic analysis unavailable.",
                "impact_level": "medium",
                "sections_affected": [],
                "recommended_actions": [],
                "key_changes": [],
            }

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
            try:
                data = json.loads(text[start:end + 1])
                # Validate expected fields
                return {
                    "summary": data.get("summary", ""),
                    "impact_level": data.get("impact_level", "medium"),
                    "sections_affected": data.get("sections_affected", []),
                    "key_changes": data.get("key_changes", []),
                    "recommended_actions": data.get("recommended_actions", []),
                }
            except json.JSONDecodeError:
                pass
        # Fallback: try to parse the old way
        return self._parse_semantic_analysis_freetext(text)

    def _parse_semantic_analysis_freetext(self, text: str) -> Dict[str, Any]:
        """Fallback parser for free-text Claude responses."""
        lines = text.strip().split("\n")
        result = {
            "summary": "",
            "impact_level": "medium",
            "sections_affected": [],
            "recommended_actions": [],
            "key_changes": [],
        }
        current_section = None
        for line in lines:
            ls = line.strip()
            upper = ls.upper()
            if "SUMMARY" in upper:
                current_section = "summary"
            elif "IMPACT LEVEL" in upper:
                current_section = "impact"
            elif "SECTIONS AFFECTED" in upper:
                current_section = "sections"
            elif "KEY CHANGES" in upper:
                current_section = "changes"
            elif "RECOMMENDED ACTIONS" in upper:
                current_section = "actions"
            elif re.match(r"^[-•*\d.]\s*", ls):
                item = re.sub(r"^[-•*\d.]+\s*", "", ls).strip()
                if not item:
                    continue
                if current_section == "sections":
                    result["sections_affected"].append(item)
                elif current_section == "actions":
                    result["recommended_actions"].append(item)
                elif current_section == "changes":
                    result["key_changes"].append({"description": item})
            elif current_section == "summary" and ls:
                result["summary"] += ls + " "
            elif current_section == "impact" and ls:
                for level in ["critical", "high", "medium", "low"]:
                    if level.upper() in upper:
                        result["impact_level"] = level
                        break
        result["summary"] = result["summary"].strip()
        return result

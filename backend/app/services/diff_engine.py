"""Detects changes between snapshots: hash, text diff, optional Claude semantic diff."""
import re
from difflib import unified_diff
from typing import Any, Dict, List, Optional

from app.config import get_config


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
                "visual_diff": None,
            }

        old_content = previous_snapshot.get("content_text") or previous_snapshot.get("content", "") or ""
        new_content = current_snapshot.get("content_text") or current_snapshot.get("content", "") or ""

        text_diff = self._compute_text_diff(old_content, new_content)
        semantic_diff = None
        client = self._get_anthropic()
        if client:
            semantic_diff = await self._compute_semantic_diff(
                old_content, new_content,
                current_snapshot.get("target_name", "Unknown"),
            )

        return {
            "has_changes": True,
            "text_diff": text_diff,
            "semantic_diff": semantic_diff,
            "visual_diff": None,
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
        prompt = f"""
Analyze these two versions of compliance document "{target_name}" and identify meaningful changes.

PREVIOUS VERSION:
{old_content[:4000]}

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

4. KEY CHANGES: For each major change, explain what changed and why it matters for compliance.

5. RECOMMENDED ACTIONS: Specific steps the compliance team should take.

Be concise and actionable. Use clear section headers.
"""
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
                system="You are a compliance expert analyzing regulatory changes. Be precise and actionable.",
            )
            text = response.content[0].text if response.content else ""
            return self._parse_semantic_analysis(text)
        except Exception:
            return {
                "summary": "Semantic analysis unavailable.",
                "impact_level": "medium",
                "sections_affected": [],
                "recommended_actions": [],
                "key_changes": [],
            }

    def _parse_semantic_analysis(self, claude_response: str) -> Dict[str, Any]:
        lines = claude_response.strip().split("\n")
        result = {
            "summary": "",
            "impact_level": "medium",
            "sections_affected": [],
            "recommended_actions": [],
            "key_changes": [],
        }
        current_section = None
        for line in lines:
            line_stripped = line.strip()
            if "SUMMARY" in line_stripped.upper():
                current_section = "summary"
            elif "IMPACT LEVEL" in line_stripped.upper():
                current_section = "impact"
            elif "SECTIONS AFFECTED" in line_stripped.upper():
                current_section = "sections"
            elif "KEY CHANGES" in line_stripped.upper():
                current_section = "changes"
            elif "RECOMMENDED ACTIONS" in line_stripped.upper():
                current_section = "actions"
            elif line_stripped.startswith("-") or line_stripped.startswith("•"):
                item = re.sub(r"^[-•]\s*", "", line_stripped).strip()
                if current_section == "sections":
                    result["sections_affected"].append(item)
                elif current_section == "actions":
                    result["recommended_actions"].append(item)
                elif current_section == "changes":
                    result["key_changes"].append({"description": item})
            elif current_section == "summary" and line_stripped:
                result["summary"] += line_stripped + " "
            elif current_section == "impact" and line_stripped:
                for level in ["critical", "high", "medium", "low"]:
                    if level.upper() in line_stripped.upper():
                        result["impact_level"] = level
                        break
        result["summary"] = result["summary"].strip()
        return result

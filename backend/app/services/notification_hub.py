"""Linear integration for change notifications."""
import json
import logging
from typing import Any, Dict, Optional

import httpx

from app.config import get_config

logger = logging.getLogger(__name__)


class NotificationHub:
    def __init__(self):
        self._config = get_config()
        self._cached_linear_team_id: Optional[str] = None

    async def _get_first_linear_team_id(self) -> Optional[str]:
        """Fetch first available team from Linear (so user doesn't need to provide team ID)."""
        if self._cached_linear_team_id:
            return self._cached_linear_team_id
        api_key = self._config.get("linear_api_key")
        if not api_key:
            return None
        body = {
            "query": "query { teams(first: 1) { nodes { id } } }",
            "variables": {},
        }
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    "https://api.linear.app/graphql",
                    json=body,
                    headers={"Authorization": api_key, "Content-Type": "application/json"},
                    timeout=10.0,
                )
                data = r.json()
                nodes = (data.get("data") or {}).get("teams", {}).get("nodes") or []
                if nodes:
                    self._cached_linear_team_id = nodes[0].get("id")
                    return self._cached_linear_team_id
                logger.warning("Linear teams query returned no teams")
        except Exception as e:
            logger.warning("Linear teams fetch error: %s", e)
        return None

    async def create_linear_issue(
        self,
        team_id: str,
        title: str,
        description: str,
        evidence_url: Optional[str] = None,
        impact_level: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a Linear issue. team_id can come from watch integrations config."""
        api_key = self._config.get("linear_api_key")
        if not api_key:
            return None
        body = {
            "query": """
            mutation CreateIssue($teamId: String!, $title: String!, $description: String!) {
                issueCreate(input: { teamId: $teamId, title: $title, description: $description }) {
                    success
                    issue { id url identifier title }
                }
            }
            """,
            "variables": {
                "teamId": team_id,
                "title": title,
                "description": description + (f"\n\nEvidence: {evidence_url}" if evidence_url else "") + (f"\nImpact: {impact_level}" if impact_level else ""),
            },
        }
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    "https://api.linear.app/graphql",
                    json=body,
                    headers={
                        "Authorization": api_key,
                        "Content-Type": "application/json",
                    },
                    timeout=15.0,
                )
                data = r.json()
                if data.get("data", {}).get("issueCreate", {}).get("success"):
                    return data["data"]["issueCreate"]["issue"]
                errors = data.get("errors") or []
                logger.warning("Linear issueCreate failed: %s", errors)
        except Exception as e:
            logger.warning("Linear create_linear_issue error: %s", e)
        return None

    async def notify_change(
        self,
        watch_name: str,
        change_summary: str,
        impact_level: str,
        linear_team_id: Optional[str] = None,
        evidence_url: Optional[str] = None,
        evidence_bundle_id: Optional[str] = None,
        compliance_summary: Optional[str] = None,
        change_detail_summary: Optional[str] = None,
    ) -> Dict[str, str]:
        """Create Linear ticket for a detected change."""
        results = {"linear": "", "linear_title": ""}
        title = f"[Compliance] {watch_name}: change detected"

        # Build comprehensive description
        description = f"## Change Summary\n{change_summary}\n\n**Impact Level:** {impact_level}\n\n"

        if change_detail_summary:
            description += f"## What Changed\n{change_detail_summary}\n\n"

        if compliance_summary:
            description += f"## How to Comply\n{compliance_summary}\n\n"

        if evidence_url:
            description += f"\n[View Evidence]({evidence_url})"

        # Use watch's linear_team_id, then LINEAR_TEAM_ID from config, else fetch first team from Linear
        team_id = (linear_team_id or "").strip() or self._config.get("linear_team_id") or ""
        if not team_id and self._config.get("linear_api_key"):
            team_id = await self._get_first_linear_team_id() or ""
        if self._config.get("linear_api_key") and team_id:
            issue = await self.create_linear_issue(
                team_id=team_id,
                title=title,
                description=description,
                evidence_url=evidence_url,
                impact_level=impact_level,
            )
            if issue:
                results["linear"] = issue.get("url") or issue.get("id", "")
                results["linear_title"] = issue.get("title") or title
            elif self._config.get("linear_api_key"):
                logger.warning("Linear issue creation returned no issue (check team_id=%s)", team_id)

        return results

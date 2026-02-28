"""Linear and Slack integrations for change notifications."""
import json
from typing import Any, Dict, Optional

import httpx

from app.config import get_config


class NotificationHub:
    def __init__(self):
        self._config = get_config()

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
        except Exception:
            pass
        return None

    async def send_slack_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[list] = None,
    ) -> bool:
        """Send a Slack message. channel from watch integrations or default."""
        token = self._config.get("slack_bot_token")
        if not token:
            return False
        payload = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    timeout=10.0,
                )
                return r.json().get("ok") is True
        except Exception:
            return False

    async def notify_change(
        self,
        watch_name: str,
        change_summary: str,
        impact_level: str,
        linear_team_id: Optional[str] = None,
        slack_channel: Optional[str] = None,
        evidence_url: Optional[str] = None,
        evidence_bundle_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Create Linear ticket and/or Slack message for a detected change."""
        results = {"linear": "", "slack": ""}
        title = f"[Compliance] {watch_name}: change detected"
        description = f"Summary: {change_summary}\nImpact: {impact_level}"
        if evidence_url:
            description += f"\nEvidence: {evidence_url}"

        if linear_team_id:
            issue = await self.create_linear_issue(
                team_id=linear_team_id,
                title=title,
                description=description,
                evidence_url=evidence_url,
                impact_level=impact_level,
            )
            if issue:
                results["linear"] = issue.get("url") or issue.get("id", "")

        if slack_channel:
            text = f"Compliance change: *{watch_name}* — {change_summary}. Impact: {impact_level}."
            if results["linear"]:
                text += f" <{results['linear']}|View in Linear>"
            ok = await self.send_slack_message(slack_channel, text)
            if ok:
                results["slack"] = "sent"

        return results

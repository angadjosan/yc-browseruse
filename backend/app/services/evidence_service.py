"""Generates and stores audit-ready evidence bundles (impact memo, diff, screenshots).

AI usage locked to compliance.md / TECHNICAL_DESIGN.md: impact memos are generated
via Anthropic Claude with a fixed prompt structure (What Changed, Why It Matters,
Immediate Actions Required, Timeline) for judge-friendly, audit-ready output.
"""
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import get_config
from app.db import get_supabase


class EvidenceService:
    def __init__(self):
        self._db = None
        self._config = get_config()
        self._secret = (self._config.get("evidence_signing_key") or "dev-secret").encode()

    @property
    def db(self):
        if self._db is None:
            self._db = get_supabase()
        return self._db

    def _sign_evidence(self, content: str, metadata: dict) -> str:
        message = f"{content}|{json.dumps(metadata, sort_keys=True)}"
        return hmac.new(self._secret, message.encode(), hashlib.sha256).hexdigest()

    def generate_bundle_id(self) -> str:
        return f"ev-{uuid.uuid4().hex[:16]}"

    def _generate_audit_metadata(
        self,
        current_snapshot: Dict[str, Any],
        previous_snapshot: Dict[str, Any],
        run_id: str,
    ) -> Dict[str, Any]:
        return {
            "run_id": run_id,
            "current_snapshot_timestamp": current_snapshot.get("captured_at") or current_snapshot.get("timestamp"),
            "previous_snapshot_timestamp": previous_snapshot.get("captured_at") or previous_snapshot.get("timestamp"),
            "source_url": current_snapshot.get("url"),
            "target_name": current_snapshot.get("target_name"),
            "content_integrity": {
                "algorithm": "SHA-256",
                "current_hash": current_snapshot.get("content_hash"),
                "previous_hash": previous_snapshot.get("content_hash"),
            },
            "capture_method": "browser-use-agent",
            "timestamp_utc": datetime.utcnow().isoformat(),
        }

    async def generate_impact_memo(
        self,
        semantic_diff: Dict[str, Any],
        target_name: str,
    ) -> str:
        """Generate professional impact memo via Claude (TECHNICAL_DESIGN §2.5 / compliance.md §7)."""
        key = self._config.get("anthropic_api_key")
        if not key:
            return f"Change detected for {target_name}. Impact: {semantic_diff.get('impact_level', 'medium')}. Configure ANTHROPIC_API_KEY for full impact memos."
        from anthropic import Anthropic
        client = Anthropic(api_key=key)
        prompt = f"""
Generate a concise compliance impact memo for this detected change.

Target: {target_name}
Impact Level: {semantic_diff.get('impact_level', 'medium').upper()}

Change Summary:
{semantic_diff.get('summary', 'N/A')}

Key Changes:
{json.dumps(semantic_diff.get('key_changes', []), indent=2)}

Sections Affected:
{', '.join(semantic_diff.get('sections_affected', []))}

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
        response = client.messages.create(
            model=self._config.get("claude_model", "claude-sonnet-4-20250514"),
            max_tokens=1500,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
            system="You are a compliance officer writing impact memos for legal teams.",
        )
        return response.content[0].text if response.content else ""

    async def generate_evidence_bundle(
        self,
        change: Dict[str, Any],
        current_snapshot: Dict[str, Any],
        previous_snapshot: Dict[str, Any],
        run_id: str,
        change_id: str,
    ) -> Dict[str, Any]:
        """Create evidence bundle and persist to DB. Uses Supabase Storage for files if configured."""
        bundle_id = str(uuid.uuid4())
        semantic = (change.get("semantic_diff") or {})
        impact_memo = await self.generate_impact_memo(semantic, current_snapshot.get("target_name", "Unknown"))
        audit_metadata = self._generate_audit_metadata(current_snapshot, previous_snapshot, run_id)
        content = (current_snapshot.get("content_text") or current_snapshot.get("content") or "")
        audit_metadata["verification_signature"] = self._sign_evidence(content, audit_metadata)

        screenshots: List[Dict[str, Any]] = []
        diff_url = None
        if current_snapshot.get("screenshot_url"):
            screenshots.append({"type": "current", "url": current_snapshot["screenshot_url"]})
        if self._config.get("use_supabase_storage"):
            try:
                bucket = self.db.storage.from_("evidence")
                path_prefix = f"evidence/{bundle_id}"
                diff_content = {
                    "text_diff": change.get("text_diff"),
                    "semantic_diff": semantic,
                }
                diff_bytes = json.dumps(diff_content, indent=2).encode()
                diff_path = f"{path_prefix}/diff.json"
                bucket.upload(diff_path, diff_bytes, {"content-type": "application/json"})
                diff_url = bucket.get_public_url(diff_path)
            except Exception:
                diff_url = None

        row = {
            "id": bundle_id,
            "change_id": change_id,
            "run_id": run_id,
            "impact_memo": impact_memo,
            "diff_summary": semantic.get("summary"),
            "diff_url": diff_url,
            "screenshots": screenshots,
            "content_hash": current_snapshot.get("content_hash"),
            "audit_metadata": audit_metadata,
        }
        self.db.table("evidence_bundles").insert(row).execute()
        return {
            **row,
            "s3_urls": {"diff": diff_url} if diff_url else {},
        }

    async def get_bundle(self, bundle_id: str) -> Optional[Dict[str, Any]]:
        r = self.db.table("evidence_bundles").select("*").eq("id", bundle_id).execute()
        return r.data[0] if r.data else None

    async def refresh_urls(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Refresh presigned URLs if using Supabase Storage. For now return as-is."""
        return bundle

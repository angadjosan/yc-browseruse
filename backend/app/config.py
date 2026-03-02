"""Application configuration from environment."""
import os
from functools import lru_cache


@lru_cache
def get_config():
    return {
        "supabase_url": os.getenv("SUPABASE_URL", "http://localhost:54321"),
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
        "supabase_service_role_key": os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "claude_model": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        "browser_use_api_key": os.getenv("BROWSER_USE_API_KEY", ""),
        "linear_api_key": os.getenv("LINEAR_API_KEY", ""),
        "linear_team_id": os.getenv("LINEAR_TEAM_ID", ""),
        "evidence_signing_key": os.getenv("EVIDENCE_SIGNING_KEY", "dev-secret-change-in-production"),
        "use_supabase_storage": os.getenv("USE_SUPABASE_STORAGE", "true").lower() == "true",
        "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
    }

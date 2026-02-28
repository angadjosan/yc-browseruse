"""Application configuration from environment."""
import os
from functools import lru_cache


@lru_cache
def get_config():
    return {
        "supabase_url": os.getenv("SUPABASE_URL", "http://localhost:54321"),
        "supabase_service_role_key": os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "browser_use_api_key": os.getenv("BROWSER_USE_API_KEY", ""),
        "linear_api_key": os.getenv("LINEAR_API_KEY", ""),
        "slack_bot_token": os.getenv("SLACK_BOT_TOKEN", ""),
        "slack_signing_secret": os.getenv("SLACK_SIGNING_SECRET", ""),
        "evidence_signing_key": os.getenv("EVIDENCE_SIGNING_KEY", "dev-secret-change-in-production"),
        "use_supabase_storage": os.getenv("USE_SUPABASE_STORAGE", "true").lower() == "true",
        "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
    }

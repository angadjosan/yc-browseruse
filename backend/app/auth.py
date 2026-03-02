"""Authentication middleware for FastAPI using Supabase Auth.

Token validation uses Supabase's auth.get_user() — no JWT secret needed.
The backend uses the service_role key for DB access (bypasses RLS), so
tenant isolation is enforced in application code via org_id filtering.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request

from app.db import get_supabase

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthContext:
    """Authenticated user context injected into route handlers."""
    user_id: str
    organization_id: str
    email: str
    role: str  # owner, admin, analyst, viewer


async def get_current_user(request: Request) -> AuthContext:
    """FastAPI dependency: validate Supabase access token and return user context.

    Reads the Authorization header (Bearer <token>), validates against Supabase Auth,
    then looks up the user's org and role from our users table.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty access token")

    db = get_supabase()

    # Validate token against Supabase Auth
    try:
        auth_response = db.auth.get_user(token)
        if not auth_response or not auth_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        supabase_user = auth_response.user
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Supabase auth validation failed: %s", e)
        raise HTTPException(status_code=401, detail="Token validation failed")

    # Look up our user profile (created by handle_new_user trigger on signup)
    user_id = str(supabase_user.id)
    try:
        result = db.table("users").select("organization_id, email, role").eq("id", user_id).single().execute()
        user_row = result.data
    except Exception as e:
        logger.error("User profile lookup failed for %s: %s", user_id, e)
        raise HTTPException(status_code=403, detail="User profile not found. Please contact support.")

    if not user_row:
        raise HTTPException(status_code=403, detail="User profile not found")

    return AuthContext(
        user_id=user_id,
        organization_id=str(user_row["organization_id"]),
        email=user_row["email"],
        role=user_row["role"],
    )


def require_role(*allowed_roles: str):
    """Dependency factory: restrict endpoint to specific roles.

    Usage:
        @router.post("/watches", dependencies=[Depends(require_role("owner", "admin", "analyst"))])
        async def create_watch(auth: AuthContext = Depends(get_current_user)):
            ...
    """
    async def check_role(auth: AuthContext = Depends(get_current_user)):
        if auth.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {', '.join(allowed_roles)}",
            )
        return auth
    return check_role


# Optional auth — returns None for unauthenticated requests (useful for public endpoints)
async def get_optional_user(request: Request) -> Optional[AuthContext]:
    """Like get_current_user but returns None instead of 401 for unauthenticated requests."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        return await get_current_user(request)
    except HTTPException:
        return None

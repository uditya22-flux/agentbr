"""
gateway/security.py
B2B SaaS Multi-tenant Security:
- Validates JWT for dashboard users (/api/*)
- Validates API Keys for AI agents (/decide, /log)
- Enforces Rate Limiting per agent
- Injects org_id into the request state
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import time
import os
import hashlib
from collections import defaultdict
from database import supabase
from utils.auth_utils import decode_access_token, hash_api_key

# In-memory rate limiter per API key hash
_request_counts: dict = defaultdict(list)
DEFAULT_RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_DAY", "1000"))

def _is_rate_limited(api_key_hash: str) -> bool:
    """Enforce daily rate limits (MVP is simple, but real app should use Redis)."""
    now = time.time()
    day_ago = now - 86400
    # Clean old logs
    _request_counts[api_key_hash] = [t for t in _request_counts[api_key_hash] if t > day_ago]
    if len(_request_counts[api_key_hash]) >= DEFAULT_RATE_LIMIT:
        return True
    _request_counts[api_key_hash].append(now)
    return False

def _get_agent_by_api_key(api_key: str):
    """Retrieve agent and org info by hashed api_key."""
    key_hash = hash_api_key(api_key)
    try:
        result = supabase.table("agents")\
            .select("id, org_id, status")\
            .eq("api_key_hash", key_hash)\
            .eq("status", "active")\
            .limit(1)\
            .execute()
        
        if result.data:
            return result.data[0]
        return None
    except Exception:
        return None

async def auth_middleware(request: Request, call_next):
    """
    Applied to all routes except public paths.
    Routes starting with /api/ (Dashboard) expect Authorization: Bearer <JWT>
    Routes for logging (/decide, /manual_log) expect X-API-Key: <key>
    """
    path = request.url.path
    # Public routes
    if path in {"/", "/login.html", "/signup.html", "/health", "/favicon.ico", "/docs", "/openapi.json"} or path.startswith("/static/"):
        return await call_next(request)

    # 1. Dashboard API Auth (JWT)
    if path.startswith("/api/"):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Bearer token required"})
        
        token = auth_header.split(" ")[1]
        payload = decode_access_token(token)
        if not payload:
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired session"})
        
        # Inject context into request state
        request.state.user_id = payload.get("sub")
        request.state.org_id = payload.get("org_id")
        return await call_next(request)

    # 2. SDK / Agent Auth (API Key)
    # These routes are usually /decide, /log, etc.
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    
    if api_key:
        agent_info = _get_agent_by_api_key(api_key)
        if not agent_info:
            return JSONResponse(status_code=403, content={"detail": "Invalid or inactive API key"})
        
        key_hash = hash_api_key(api_key)
        if _is_rate_limited(key_hash):
            return JSONResponse(status_code=429, content={"detail": "Daily rate limit exceeded"})
        
        request.state.agent_id = agent_info["id"]
        request.state.org_id = agent_info["org_id"]
        return await call_next(request)

    # Fallback to 401 if no auth found
    return JSONResponse(status_code=401, content={"detail": "Authentication required"})

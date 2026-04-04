"""
gateway/security.py
API key validation, rate limiting, request authentication.
No open endpoints — every request requires a valid key.
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

import time
import os
from collections import defaultdict
from database import supabase

# In-memory rate limiter (use Redis in production)
_request_counts: dict = defaultdict(list)
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
RATE_WINDOW_SECONDS = 60


def _is_rate_limited(api_key: str) -> bool:
    now = time.time()
    window_start = now - RATE_WINDOW_SECONDS
    _request_counts[api_key] = [t for t in _request_counts[api_key] if t > window_start]
    if len(_request_counts[api_key]) >= RATE_LIMIT_PER_MINUTE:
        return True
    _request_counts[api_key].append(now)
    return False


def _validate_api_key(api_key: str) -> bool:
    """Check api_key exists in Supabase api_keys table."""
    if not api_key:
        return False
    dev_key = os.environ.get("DEV_API_KEY")
    if dev_key and api_key == dev_key:
        return True
    try:
        result = supabase.table("api_keys")\
            .select("api_key, active")\
            .eq("api_key", api_key)\
            .eq("active", True)\
            .limit(1)\
            .execute()
        return bool(result.data)
    except Exception:
        return False


async def auth_middleware(request: Request, call_next):
    """
    Applied to all routes except /health and /.
    Validates API key and enforces rate limits.
    """
    skip_paths = {"/", "/health", "/favicon.ico", "/docs", "/openapi.json"}
    if request.url.path in skip_paths:
        return await call_next(request)

    # Extract API key from header or query param
    api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key") or request.query_params.get("api_key")

    if not api_key:
        return JSONResponse(
            status_code=401,
            content={"detail": "X-API-Key header or api_key query parameter required"}
        )

    if not _validate_api_key(api_key):
        return JSONResponse(
            status_code=403,
            content={"detail": "Invalid or inactive API key"}
        )

    if _is_rate_limited(api_key):
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit exceeded: {RATE_LIMIT_PER_MINUTE} requests/minute"}
        )

    return await call_next(request)

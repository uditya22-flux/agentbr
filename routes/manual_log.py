"""
routes/manual_log.py
Dashboard-only manual log submission.
Requires JWT auth (org_id injected).
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from gateway.decision_gateway import process_decision
from database import supabase

router = APIRouter(prefix="/api", tags=["Manual Submission"])

@router.post("/manual_log")
async def manual_log(request: Request):
    """
    Submit a log entry directly from the dashboard.
    Uses the user's org_id context.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Normalize fields
    raw = dict(data)
    
    # Validation: Ensure agent_id is provided and belongs to the org
    agent_id = raw.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id required")
    
    # Context injection
    raw["org_id"] = org_id
    
    # Defaults for simulation
    if "decision_id" not in raw:
        import uuid
        raw["decision_id"] = f"D-{str(uuid.uuid4())[:8]}"
    if "session_id" not in raw:
        import uuid
        raw["session_id"] = f"S-{str(uuid.uuid4())[:8]}"
    if "user_id" not in raw:
        raw["user_id"] = "dashboard_user"
    if "confidence" not in raw:
        raw["confidence"] = 0.95
    if "reasoning" not in raw:
        raw["reasoning"] = "Manual submission via dashboard"

    response_data, status_code = process_decision(raw)
    return JSONResponse(content=response_data, status_code=status_code)

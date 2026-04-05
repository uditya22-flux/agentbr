"""
routes/gateway_routes.py
Multi-tenant SDK endpoints for AI agents.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from gateway.decision_gateway import process_decision
from database import supabase

router = APIRouter(tags=["SDK Gateway"])

@router.post("/decide")
async def decide(request: Request):
    """
    MAIN GATEWAY ENDPOINT for SDK.
    Requires X-API-Key. org_id and agent_id are injected by security middleware.
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Access context from middleware
    org_id = getattr(request.state, "org_id", None)
    agent_id = getattr(request.state, "agent_id", None)
    
    if not org_id or not agent_id:
        raise HTTPException(status_code=401, detail="Agent identification failed")

    # Add context to the record
    raw["org_id"] = org_id
    raw["agent_id"] = agent_id

    # Call the decision processor
    response_data, status_code = process_decision(raw)
    return JSONResponse(content=response_data, status_code=status_code)

@router.post("/log")
async def legacy_log(request: Request):
    """SDK log endpoint, redirected to gateway."""
    return await decide(request)

# Moves dashboard logs to /api/logs
@router.get("/api/logs")
async def get_dashboard_logs(request: Request, agent_id: str = None, limit: int = 50):
    """Dashboard endpoint to fetch logs for the logged-in company."""
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    query = supabase.table("audit_logs").select("*").eq("org_id", org_id)
    if agent_id and agent_id != "all":
        query = query.eq("agent_id", agent_id)
    
    res = query.order("created_at", desc=True).limit(limit).execute()
    return res.data

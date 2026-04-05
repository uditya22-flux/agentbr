"""
routes/intelligence.py
Multi-tenant Intelligence Hub:
- Scoped Analytics & Analytics Breakdown
- Natural Language Query (NLQ) over logs per organization
"""
from fastapi import APIRouter, HTTPException, Request
from database import supabase
from core_ai.nl_query import query_logs
from core_ai.behavioral_drift import detect_drift
from core_ai.structuring_detector import detect_structuring

router = APIRouter(prefix="/api/intelligence", tags=["Intelligence HUB"])

def _get_org_logs(org_id: str, limit: int = 500):
    """Fetch logs scoped by organization."""
    result = supabase.table("audit_logs")\
        .select("*")\
        .eq("org_id", org_id)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()
    return result.data

@router.post("/query")
async def natural_language_query(request: Request, data: dict):
    """Ask AgentBridge anything about your organizational compliance data."""
    org_id = getattr(request.state, "org_id", None)
    question = data.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="question required")
    
    logs = _get_org_logs(org_id)
    answer = query_logs(question, logs)
    return {
        "question": question, 
        "answer": answer, 
        "logs_analyzed": len(logs),
        "source_logs": logs[:5] # Return top 5 most relevant or recent
    }

@router.get("/drift")
async def behavioral_drift(request: Request):
    """Week-on-week behavioral comparison from audit_logs for organization."""
    org_id = getattr(request.state, "org_id", None)
    logs = _get_org_logs(org_id, limit=500)
    return detect_drift(logs)

@router.get("/structuring")
async def structuring_detection(request: Request):
    """Detect ₹50K threshold structuring patterns in organization's audit_logs."""
    org_id = getattr(request.state, "org_id", None)
    logs = _get_org_logs(org_id, limit=200)
    return detect_structuring(logs)

"""
Intelligence endpoints — all query audit_logs (v5 table).
POST /query   — plain English compliance question
GET  /drift   — behavioral drift this week vs last week
GET  /structuring — cross-session structuring pattern detection
"""
from fastapi import APIRouter, HTTPException
from database import supabase
from core_ai.nl_query import query_logs
from core_ai.behavioral_drift import detect_drift
from core_ai.structuring_detector import detect_structuring

router = APIRouter()

def _get_logs(api_key: str, limit: int = 200):
    """Always reads from audit_logs — the v5 immutable table."""
    result = supabase.table("audit_logs")\
        .select("*")\
        .eq("api_key", api_key)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()
    return result.data

@router.post("/query")
async def natural_language_query(data: dict):
    """
    Ask AgentBridge anything about your audit logs.
    Body: { "api_key": "...", "question": "Did my agent show bias this week?" }
    """
    api_key = data.get("api_key")
    question = data.get("question")
    if not api_key or not question:
        raise HTTPException(status_code=400, detail="api_key and question required")
    logs = _get_logs(api_key)
    answer = query_logs(question, logs)
    return {"question": question, "answer": answer, "logs_analyzed": len(logs)}

@router.get("/drift")
async def behavioral_drift(api_key: str):
    """Week-on-week behavioral comparison from audit_logs."""
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key required")
    logs = _get_logs(api_key, limit=500)
    return detect_drift(logs)

@router.get("/structuring")
async def structuring_detection(api_key: str):
    """Detect ₹50K threshold structuring patterns in audit_logs."""
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key required")
    logs = _get_logs(api_key, limit=200)
    result = detect_structuring(logs)
    if not result:
        return {"status": "clean", "message": "No structuring patterns detected."}
    return result

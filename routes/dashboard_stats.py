from fastapi import APIRouter, Request, HTTPException
from database import supabase
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard Statistics"])

@router.get("/stats")
async def get_dashboard_stats(request: Request, agent_id: str = None):
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # Scoped by org_id
        query = supabase.table("audit_logs").select("verdict, risk_level, flagged, latency_ms", count="exact").eq("org_id", org_id)
        if agent_id and agent_id != "all":
            query = query.eq("agent_id", agent_id)
        
        logs_res = query.execute()
        total_logs = logs_res.count if hasattr(logs_res, "count") else len(logs_res.data)
        
        # Calculate stats from data
        data = logs_res.data
        incidents = sum(1 for log in data if log["flagged"])
        high_risk = sum(1 for log in data if log["risk_level"] == "high")
        violations = sum(1 for log in data if log["verdict"] == "reject")
        avg_latency = (sum(log["latency_ms"] or 0 for log in data) / total_logs) if total_logs > 0 else 0
        
        return {
            "total_logs": total_logs,
            "incidents": incidents,
            "high_risk": high_risk,
            "violations": violations,
            "avg_latency": round(avg_latency, 2),
            "drift_status": "stable" # Placeholder for drift logic
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/incidents")
async def get_incidents(request: Request, limit: int = 20, offset: int = 0):
    org_id = getattr(request.state, "org_id", None)
    res = supabase.table("incidents")\
        .select("*, audit_logs(*), agents(name)")\
        .eq("org_id", org_id)\
        .order("created_at", desc=True)\
        .range(offset, offset + limit - 1)\
        .execute()
    return res.data

@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(request: Request, incident_id: str, note: str):
    org_id = getattr(request.state, "org_id", None)
    user_id = getattr(request.state, "user_id", None)
    
    supabase.table("incidents")\
        .update({
            "status": "resolved",
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolved_by": user_id,
            "resolution_note": note
        })\
        .eq("id", incident_id)\
        .eq("org_id", org_id)\
        .execute()
    
    return {"status": "resolved"}

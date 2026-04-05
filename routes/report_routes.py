from fastapi import APIRouter, Request, HTTPException
from database import supabase
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/api/reports", tags=["RBI Reports"])

CLAUSES = [
    {"id": "F.1", "name": "Fairness and Bias", "desc": "Ensuring no demographic disparity in decisions."},
    {"id": "R.1", "name": "Robustness and Integrity", "desc": "Error handling and system stability under stress."},
    {"id": "E.1", "name": "Explainability", "desc": "Clear reasoning provided for every decision."},
    {"id": "E.2", "name": "Excludability", "desc": "Ability to opt-out or override AI decisions."},
    {"id": "A.1", "name": "Accountability", "desc": "Clear ownership and audit trail for decisions."},
    {"id": "S.1", "name": "Safety and Security", "desc": "Protection against adversarial attacks and data leaks."},
    {"id": "P.1", "name": "Privacy", "desc": "Data protection and minimization."},
    {"id": "B.1", "name": "Behavioral Monitoring", "desc": "Continuous monitoring for model drift and anomalies."}
]

@router.get("/generate")
async def generate_org_report(request: Request, agent_id: str = None):
    org_id = getattr(request.state, "org_id", None)
    
    # 1. Fetch logs
    query = supabase.table("audit_logs").select("*").eq("org_id", org_id)
    if agent_id and agent_id != "all":
        query = query.eq("agent_id", agent_id)
    
    res = query.order("created_at", desc=True).limit(500).execute()
    logs = res.data
    
    if not logs:
        raise HTTPException(status_code=404, detail="No data found to generate report")

    # 2. Logic to determine pass/fail per clause (Mocked for now)
    total = len(logs)
    report_data = {
        "clauses": [],
        "overall_score": 0,
        "total_logs": total
    }
    
    passed_count = 0
    for clause in CLAUSES:
        # Simple heuristic: If no violations of this type, it passes
        # Real logic would check compliance_tags and compliance_violations
        status = "Passed" # Placeholder
        passed_count += 1
        report_data["clauses"].append({
            **clause,
            "status": status,
            "score": 100 # Mock
        })
    
    report_data["overall_score"] = int((passed_count / len(CLAUSES)) * 100)

    # 3. Save to History
    hist_res = supabase.table("compliance_reports").insert({
        "org_id": org_id,
        "agent_id": agent_id if agent_id != "all" else None,
        "score": report_data["overall_score"],
        "clauses_passed": passed_count,
        "clauses_failed": len(CLAUSES) - passed_count,
        "report_data": report_data
    }).execute()

    return report_data

@router.get("/history")
async def get_report_history(request: Request):
    org_id = getattr(request.state, "org_id", None)
    res = supabase.table("compliance_reports")\
        .select("id, created_at, score, clauses_passed, agents(name)")\
        .eq("org_id", org_id)\
        .order("created_at", desc=True)\
        .execute()
    return res.data

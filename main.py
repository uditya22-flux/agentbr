import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from database import save_log, get_all_logs, get_logs_by_session, get_high_critical_logs, verify_api_key, get_last_log_hash
from core_ai.monitor import AgentBridgeMonitor
import json
from typing import Optional
from datetime import datetime

app = FastAPI(title="AgentBridge Gateway v5")

# Add CORS Middleware for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/decide")
@app.post("/log")
@app.post("/api/log")
async def process_log(request: Request):
    """
    Gateway v5 Decision Receiver:
    - Verifies API Key (Supabase)
    - Fetches Previous Hash (Supabase)
    - Processes Log (Deterministic AI)
    - Records Immutable Record (Supabase)
    """
    try:
        # 1. Identity Verification
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if not verify_api_key(api_key):
             return JSONResponse(status_code=401, content={"error": "Invalid or inactive API Key (Require 'test123' for dev)"})
            
        # 2. Get Previous Hash for Chain integrity
        prev_hash = get_last_log_hash()
        
        # 3. Process Decision via Core AI
        raw_data = await request.json()
        raw_data["api_key"] = api_key # Track origin
        
        # Use hashing-aware monitor
        # We'll re-instantiate it to ensure state doesn't persist across requests
        monitor = AgentBridgeMonitor(previous_hash=prev_hash)
        processed_record = monitor.process_log(raw_data)
        
        # 4. Save to Immutable Audit Trail
        save_log(processed_record)
        
        return {
            "success": True,
            "decision_id": processed_record["decision_id"],
            "verdict": processed_record["verdict"],
            "risk_level": processed_record["risk_level"],
            "log_hash": processed_record["log_hash"],
            "compliance_violations": processed_record["compliance_violations"]
        }
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.post("/log-manual")
@app.post("/api/log-manual")
async def process_manual_log(request: Request):
    """
    Handles flat form data from the UI Dashboard and normalizes it
    for the compliance monitor.
    """
    try:
        form_data = await request.json()
        
        # Normalization
        normalized = {
            "agent_name": form_data.get("agent_name"),
            "action_type": form_data.get("action_type"),
            "input": {
                "amount": float(form_data.get("amount", 0)),
                "kyc_verified": form_data.get("kyc_verified") == "True" or form_data.get("kyc_verified") == True,
                "is_pep": form_data.get("is_pep") == "True" or form_data.get("is_pep") == True,
                "confidence": float(form_data.get("confidence", 0)),
            },
            "reasoning": form_data.get("reasoning", ""),
            "output": f"Manual Action: {form_data.get('action_type')}",
            "confidence": float(form_data.get("confidence", 0.5)),
            "session_id": "manual-session-" + str(datetime.utcnow().timestamp()),
            "api_key": "test123" # Mandatory key for local manual logs
        }
        
        # Reuse process_log logic internally
        prev_hash = get_last_log_hash()
        monitor = AgentBridgeMonitor(previous_hash=prev_hash)
        processed = monitor.process_log(normalized)
        save_log(processed)
        
        return {"success": True, "log_id": processed["decision_id"], "verdict": processed["verdict"]}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Manual Validation Failed: {str(e)}"})

@app.get("/logs")
@app.get("/api/logs")
def get_logs(
    request: Request,
    api_key: Optional[str] = None,
    agent_id: Optional[str] = None,
    action_type: Optional[str] = None,
    compliance_status: Optional[str] = None,
    limit: int = 10
):
    # Require api_key
    provided_key = api_key or request.headers.get("X-API-Key")
    if not verify_api_key(provided_key):
        return JSONResponse(status_code=401, content={"error": "Valid API Key required"})

    all_logs = get_all_logs()
    
    # Filtering
    if agent_id and agent_id != 'all':
        all_logs = [l for l in all_logs if l.get('agent_id') == agent_id]
    if action_type:
        all_logs = [l for l in all_logs if l.get('action_type') == action_type]
    if compliance_status:
        is_fail = compliance_status.lower() == "fail"
        all_logs = [l for l in all_logs if l.get('flagged') == is_fail]

    # Map to UI expected format (preserving backward shim for dashboard.js where needed)
    for l in all_logs:
        l["log_id"] = l.get("decision_id") # shim
        l["compliance_status"] = "fail" if l.get("flagged") else "pass"
        l["violated_clauses"] = l.get("compliance_tags", [])
        
    return all_logs[:limit]

from core_ai.nl_query import query_logs
from core_ai.behavioral_drift import detect_behavioral_drift
from core_ai.structuring_detector import detect_structuring_patterns
from core_ai.report_generator import generate_rbi_report
from core_ai.structural_anomalies import detect_structural_gaps

@app.get("/report")
@app.get("/api/intelligence/report")
def endpoint_report():
    logs = get_all_logs()
    return generate_rbi_report(logs)

@app.post("/query")
@app.post("/api/intelligence/query")
async def natural_language_query(request: Request):
    try:
        data = await request.json()
        question = data.get("question")
        logs = get_all_logs()
        answer = query_logs(question, logs[:30])
        return {"question": question, "answer": answer}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/drift")
@app.get("/api/intelligence/drift")
def endpoint_drift():
    logs = get_all_logs()
    return detect_behavioral_drift(logs)

@app.get("/structuring")
@app.get("/api/intelligence/structuring")
def endpoint_structuring():
    logs = get_all_logs()
    return detect_structuring_patterns(logs)

@app.get("/structural-anomalies")
@app.get("/api/intelligence/structural-anomalies")
def endpoint_structural_anomalies():
    logs = get_all_logs()
    return detect_structural_gaps(logs)

@app.get("/api/settings/profile")
def get_profile():
    return {"name": "Audit Corp", "industry": "Banking"}

@app.get("/api/agents/")
def get_agents():
    return [
        {"id": "fraud-bot-v5", "name": "Institutional Fraud Bot", "agent_type": "fraud-detection"},
        {"id": "loan-bot-v5", "name": "Regulatory Loan Bot", "agent_type": "loan-approval"}
    ]

@app.get("/api/dashboard/stats")
def get_dashboard_stats(agent_id: str = None):
    all_logs = get_all_logs()
    if agent_id and agent_id != 'all':
        all_logs = [l for l in all_logs if l.get('agent_id') == agent_id]
        
    hc_logs = [l for l in all_logs if l.get('risk_level') in ['high', 'critical']]
    
    return {
        "total_logs": len(all_logs),
        "incidents": len(hc_logs),
        "high_risk": len([l for l in hc_logs if l.get('risk_level') == 'high']),
        "violations": sum(len(l.get('compliance_violations', [])) for l in all_logs),
        "avg_latency": 15,
        "drift_status": "stable"
    }

@app.get("/", include_in_schema=False)
def serve_dashboard():
    return FileResponse("dashboard.html")

@app.get("/{filename}", include_in_schema=False)
def serve_static(filename: str):
    if os.path.exists(filename):
        return FileResponse(filename)
    return JSONResponse(status_code=404, content={"error": "File not found"})

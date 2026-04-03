"""
POST /log-manual
Allows a user to submit a log directly from the UI.
Runs through the full gateway pipeline and returns the compliance verdict.
Designed for demo and testing — no SDK required.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from gateway.decision_gateway import process_decision

router = APIRouter()

@router.post("/log-manual")
async def manual_log(data: dict):
    """
    Submit a log entry from the UI.
    Accepts flexible input — maps common field names to gateway schema.
    Returns full compliance verdict with AI analysis.
    """
    if not data.get("api_key"):
        raise HTTPException(status_code=400, detail="api_key required")

    # Normalize field names from UI form to gateway schema
    raw = dict(data)

    # Map agent_name → agent_id
    if "agent_name" in raw and "agent_id" not in raw:
        raw["agent_id"] = raw.pop("agent_name")

    # Map action → action_type
    if "action" in raw and "action_type" not in raw:
        raw["action_type"] = raw.pop("action")

    # Map inputs → input
    if "inputs" in raw and "input" not in raw:
        v = raw.pop("inputs")
        raw["input"] = v if isinstance(v, dict) else {}

    # Ensure input is dict
    if "input" not in raw or not isinstance(raw.get("input"), dict):
        raw["input"] = {}

    # Default required fields for UI submission
    if not raw.get("session_id"):
        import uuid
        raw["session_id"] = f"ui-session-{str(uuid.uuid4())[:8]}"
    if not raw.get("user_id"):
        raw["user_id"] = "ui_user"
    if "confidence" not in raw:
        raw["confidence"] = 0.85
    if not raw.get("reasoning"):
        raw["reasoning"] = "Submitted via AgentBridge UI"

    response_data, status_code = process_decision(raw)
    return JSONResponse(content=response_data, status_code=status_code)

from core_ai.dao import DAO
from typing import Any, Dict
import uuid
from datetime import datetime


# RBI Clause 5.2 — valid classified verbs (production set)
KNOWN_ACTION_TYPES = frozenset(
    {"loan", "transfer", "approve", "reject", "verify", "query", "flag"}
)


def parse_to_dao(raw_log: Dict[str, Any]) -> DAO:
    """Normalize worker JSON or gateway payload into DAO."""

    decision_id = (
        str(raw_log.get("id"))
        or str(raw_log.get("decision_id"))
        or str(uuid.uuid4())
    )

    session_id_raw = (
        raw_log.get("session_id")
        or raw_log.get("run_id")
        or raw_log.get("trace_id")
    )
    session_id = str(session_id_raw) if session_id_raw not in (None, "") else ""

    timestamp = (
        raw_log.get("timestamp")
        or raw_log.get("ts")
        or raw_log.get("created_at")
        or datetime.utcnow().isoformat()
    )

    input_data = (
        raw_log.get("input")
        or raw_log.get("input_data")
        or raw_log.get("context")
        or raw_log.get("inputs")
        or {}
    )
    if not isinstance(input_data, dict):
        input_data = {"raw_input": str(input_data)}

    output_data = (
        raw_log.get("output")
        or raw_log.get("result")
        or raw_log.get("response")
        or {}
    )
    if not isinstance(output_data, dict):
        output_data = {"raw_output": str(output_data)}

    # Flat worker fields → merge into input/output
    for key in ("amount", "kyc_verified", "kyc"):
        if key in raw_log and raw_log[key] is not None:
            nk = "kyc_verified" if key == "kyc" else key
            if nk not in input_data:
                input_data[nk] = raw_log[key]

    if raw_log.get("decision") is not None and "decision" not in output_data:
        output_data["decision"] = raw_log["decision"]

    if raw_log.get("confidence") is not None:
        try:
            c = float(raw_log["confidence"])
            if "confidence" not in output_data:
                output_data["confidence"] = c
        except (TypeError, ValueError):
            pass

    reasoning = (
        raw_log.get("reasoning")
        or raw_log.get("thought")
        or raw_log.get("explanation")
        or raw_log.get("rationale")
        or None
    )

    action_type = (
        raw_log.get("action_type")
        or raw_log.get("action")
        or output_data.get("action_type")
        or output_data.get("action")
        or "unknown"
    )
    if isinstance(action_type, str):
        action_type = action_type.strip().lower()
    if action_type not in KNOWN_ACTION_TYPES:
        action_type = "unknown"

    agent_name = (
        raw_log.get("agent_name")
        or raw_log.get("agent_id")
        or raw_log.get("agent")
        or raw_log.get("model")
        or "unnamed_agent"
    )

    return DAO(
        decision_id=decision_id,
        session_id=session_id,
        timestamp=timestamp,
        input=input_data,
        reasoning=reasoning,
        output=output_data,
        risk_level="low",
        flag_reason=None,
        compliance_tags=[],
        agent_name=str(agent_name),
        action_type=action_type,
    )

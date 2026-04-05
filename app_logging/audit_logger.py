"""
logging/audit_logger.py
Immutable hash-chained audit log for B2B SaaS.
Every log entry contains SHA256 of (current_record + previous_hash) scoped by org_id.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Optional
from database import supabase

def _get_last_hash(org_id: str) -> str:
    """Fetch the most recent log_hash for this organization to continue the chain."""
    try:
        result = supabase.table("audit_logs")\
            .select("log_hash")\
            .eq("org_id", org_id)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        if result.data:
            return result.data[0]["log_hash"]
    except Exception:
        pass
    return "GENESIS"

def _compute_hash(record: dict, previous_hash: str) -> str:
    """SHA256(canonical_json(record) + previous_hash)"""
    canonical = json.dumps(record, sort_keys=True, default=str)
    raw = canonical + (previous_hash or "GENESIS")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def write(
    org_id: str,
    agent_id: str,
    decision_id: str,
    session_id: str,
    user_id: str,
    action_type: str,
    verdict: str,
    risk_score: float,
    risk_level: str,
    policy_violations: list,
    compliance_violations: list,
    input_data: dict,
    output_data: dict,
    reasoning: str,
    confidence: float,
    ai_explanation: Optional[str],
    ai_recommended_action: Optional[str],
    ai_escalate_to_human: bool,
    ai_regulatory_refs: list,
    ai_compliance_status: Optional[str],
    ai_action_summary: Optional[str] = None,
) -> str:
    """
    Writes one immutable log entry. Returns the log_hash.
    Also creates an entry in the 'incidents' table if flagged.
    """
    previous_hash = _get_last_hash(org_id)

    record = {
        "org_id": org_id,
        "agent_id": agent_id,
        "decision_id": decision_id,
        "session_id": session_id,
        "user_id": user_id,
        "action_type": action_type,
        "verdict": verdict,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "policy_violations": policy_violations,
        "compliance_violations": compliance_violations,
        "reasoning": reasoning,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    log_hash = _compute_hash(record, previous_hash)

    entry = {
        **record,
        "inputs": input_data, # JSONB in SQL
        "output": json.dumps(output_data),
        "ai_explanation": ai_explanation,
        "ai_recommended_action": ai_recommended_action,
        "ai_escalate_to_human": ai_escalate_to_human,
        "ai_regulatory_refs": ai_regulatory_refs,
        "ai_compliance_status": ai_compliance_status,
        "ai_action_summary": ai_action_summary,
        "previous_hash": previous_hash,
        "log_hash": log_hash,
        "flagged": verdict in ("reject", "review") or ai_escalate_to_human,
    }

    try:
        res = supabase.table("audit_logs").insert(entry).execute()
        
        # Increment agent total_logs
        supabase.rpc("increment_agent_logs", {"agent_id": agent_id}).execute()

        # Create incident if flagged
        if entry["flagged"]:
            log_id = res.data[0]["id"]
            severity = "high" if verdict == "reject" else "medium"
            rule_triggered = (policy_violations[0] if policy_violations else 
                             (compliance_violations[0] if compliance_violations else "Anomaly detected"))
            
            supabase.table("incidents").insert({
                "org_id": org_id,
                "agent_id": agent_id,
                "log_id": log_id,
                "severity": severity,
                "rule_triggered": rule_triggered,
                "status": "open"
            }).execute()

    except Exception as e:
        print(f"[audit_logger] CRITICAL: Failed to write audit log: {e}")

    return log_hash

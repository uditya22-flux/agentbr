"""
Cross-session structuring detection.
Catches agents repeatedly approving amounts just below ₹50,000 threshold
— a classic money laundering pattern RBI specifically watches for.
"""
from typing import List, Dict, Any


def detect_structuring(recent_logs: List[Dict[str, Any]]) -> dict:
    """
    Takes last N logs for an api_key and detects structuring patterns.
    Returns a finding dict if suspicious, empty dict if clean.
    """
    # Filter approve actions with amount data
    approvals = []
    for log in recent_logs:
        try:
            inputs = log.get("inputs", "{}")
            if isinstance(inputs, str):
                import ast
                inputs = ast.literal_eval(inputs)
            amount = inputs.get("amount", 0) if isinstance(inputs, dict) else 0
            if log.get("action_type", log.get("action")) == "approve" and amount:
                approvals.append({"amount": amount, "session_id": log.get("session_id"), "decision_id": log.get("decision_id"), "created_at": log.get("created_at")})
        except Exception:
            continue

    # Pattern 1: Multiple approvals between ₹40,000–₹49,999 (just under RBI threshold)
    near_threshold = [a for a in approvals if 40000 <= a["amount"] < 50000]
    if len(near_threshold) >= 3:
        total = sum(a["amount"] for a in near_threshold)
        return {
            "pattern": "structuring",
            "severity": "high",
            "description": f"{len(near_threshold)} approvals between ₹40,000–₹49,999 detected across sessions. Total: ₹{total}. Possible threshold structuring.",
            "rbi_reference": "RBI Master Direction on KYC — suspicious transaction reporting obligation",
            "flagged_decisions": [a["decision_id"] for a in near_threshold],
        }

    # Pattern 2: Same amount approved 5+ times
    from collections import Counter
    amount_counts = Counter(a["amount"] for a in approvals)
    for amount, count in amount_counts.items():
        if count >= 5:
            return {
                "pattern": "repeated_identical_amount",
                "severity": "medium",
                "description": f"Exact amount ₹{amount} approved {count} times. Possible automated structuring.",
                "rbi_reference": "RBI FREE-AI Clause — unusual pattern detection",
                "flagged_decisions": [a["decision_id"] for a in approvals if a["amount"] == amount],
            }

    return {}

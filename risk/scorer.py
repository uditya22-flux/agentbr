"""
risk/scorer.py
Deterministic risk scoring for gateway (numeric score).
Stateful session multiplier uses Supabase when configured.
"""
from models.schemas import DecisionRequest
from database import supabase


W_NO_KYC           = 0.35
W_HIGH_VALUE       = 0.20
W_CRITICAL_VALUE   = 0.35
W_LOW_CONFIDENCE   = 0.15
W_CRIT_CONFIDENCE  = 0.30
W_PEP              = 0.25
W_SESSION_HISTORY  = 0.15
W_UNKNOWN_ACTION   = 0.10

ALLOW_THRESHOLD  = 0.35
REVIEW_THRESHOLD = 0.65


def _session_risk_multiplier(session_id: str) -> float:
    try:
        result = supabase.table("audit_logs")\
            .select("risk_level")\
            .eq("session_id", session_id)\
            .in_("risk_level", ["high", "critical"])\
            .limit(10)\
            .execute()
        count = len(result.data or [])
        return min(count * 0.03, W_SESSION_HISTORY)
    except Exception:
        return 0.0


def score(req: DecisionRequest) -> tuple[float, str, str]:
    amount = req.input.get("amount", 0) or 0
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = 0.0

    kyc_verified = req.input.get("kyc_verified") or req.input.get("kyc", False)
    risk_score = 0.0
    factors = []

    if req.action_type in ("approve", "loan", "transfer") and not kyc_verified:
        risk_score += W_NO_KYC
        factors.append(f"+{W_NO_KYC} no KYC")

    if amount >= 200000:
        risk_score += W_CRITICAL_VALUE
        factors.append(f"+{W_CRITICAL_VALUE} critical value ₹{amount}")
    elif amount >= 50000:
        risk_score += W_HIGH_VALUE
        factors.append(f"+{W_HIGH_VALUE} high value ₹{amount}")

    if req.confidence < 0.50:
        risk_score += W_CRIT_CONFIDENCE
        factors.append(f"+{W_CRIT_CONFIDENCE} critical confidence {req.confidence}")
    elif req.confidence < 0.75:
        risk_score += W_LOW_CONFIDENCE
        factors.append(f"+{W_LOW_CONFIDENCE} low confidence {req.confidence}")

    if req.action_type == "unknown":
        risk_score += W_UNKNOWN_ACTION
        factors.append(f"+{W_UNKNOWN_ACTION} unknown action")

    if req.input.get("is_pep") or req.input.get("politically_exposed"):
        risk_score += W_PEP
        factors.append(f"+{W_PEP} PEP detected")

    session_add = _session_risk_multiplier(req.session_id)
    if session_add > 0:
        risk_score += session_add
        factors.append(f"+{session_add:.2f} session history")

    risk_score = round(min(risk_score, 1.0), 3)

    if risk_score >= REVIEW_THRESHOLD:
        risk_level = "critical" if risk_score >= 0.85 else "high"
    elif risk_score >= ALLOW_THRESHOLD:
        risk_level = "medium"
    else:
        risk_level = "low"

    explanation = (
        f"Risk score {risk_score}: " + ", ".join(factors)
        if factors else f"Risk score {risk_score}: no numeric risk factors"
    )

    return risk_score, risk_level, explanation

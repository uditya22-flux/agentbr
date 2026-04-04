"""
Deterministic anomaly detection — AgentBridge Monitor (not an LLM).
"""
from core_ai.dao import DAO


def _amount(dao: DAO) -> float:
    try:
        v = dao.input.get("amount") or dao.output.get("amount") or 0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _kyc(dao: DAO) -> bool:
    v = dao.input.get("kyc_verified")
    if v is None:
        v = dao.input.get("kyc")
    return bool(v)


def _confidence(dao: DAO) -> float:
    try:
        c = dao.output.get("confidence")
        if c is None:
            c = dao.input.get("confidence")
        return float(c) if c is not None else 1.0
    except (TypeError, ValueError):
        return 1.0


def check_anomalies(dao: DAO) -> DAO:
    """
    Rules (product spec):
    - amount > 50,000 AND NOT kyc_verified → anomaly
    - missing reasoning → anomaly
    - confidence < 0.75 → anomaly
    - missing session_id → anomaly
    """
    dao.anomalies = []

    if not dao.session_id or dao.session_id.strip() == "":
        dao.anomalies.append("missing_session_id")

    if dao.reasoning is None or not str(dao.reasoning).strip():
        dao.anomalies.append("missing_reasoning")

    amt = _amount(dao)
    kyc = _kyc(dao)
    if amt > 50000 and not kyc:
        dao.anomalies.append("high_value_without_kyc")

    conf = _confidence(dao)
    if conf < 0.75:
        dao.anomalies.append("low_confidence")

    # Legacy flag_reason hints for downstream audit strings
    parts = []
    if "missing_reasoning" in dao.anomalies:
        parts.append("No reasoning logged")
    if "missing_session_id" in dao.anomalies:
        parts.append("Session ID missing — traceability gap")
    if "high_value_without_kyc" in dao.anomalies:
        parts.append(f"Amount ₹{amt:,.0f} without KYC verification")
    if "low_confidence" in dao.anomalies:
        parts.append(f"Confidence {conf} below 0.75 threshold")
    if parts:
        dao.flag_reason = " | ".join(parts)

    return dao

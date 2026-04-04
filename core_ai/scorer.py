"""
Deterministic risk tier for AgentBridge Monitor (after anomalies + compliance).
HIGH — multiple violations, high amount + no KYC, or critical anomalies.
MEDIUM — some issues.
LOW — clean.
"""
from core_ai.dao import DAO


def finalize_monitor_risk(dao: DAO) -> DAO:
    n_v = len(dao.compliance_violations)
    n_a = len(dao.anomalies)

    critical = (
        "missing_reasoning" in dao.anomalies
        or "high_value_without_kyc" in dao.anomalies
        or n_v >= 2
    )

    if critical:
        dao.risk_level = "high"
        return dao

    if n_v >= 1 or n_a >= 1:
        dao.risk_level = "medium"
        return dao

    dao.risk_level = "low"
    return dao


def build_dao_record(dao: DAO) -> DAO:
    """Decision → Action → Outcome (product DAO block)."""
    decision = (
        dao.output.get("decision")
        or dao.output.get("outcome")
        or dao.reasoning
        or ""
    )
    action = dao.action_type or "unknown"
    if dao.risk_level == "high":
        outcome = "BLOCKED"
    elif dao.risk_level == "medium":
        outcome = "FLAGGED"
    else:
        outcome = "APPROVED"

    dao.dao_record = {
        "decision": str(decision)[:2000],
        "action": action,
        "outcome": outcome,
    }
    dao.ai_explanation = (
        f"Deterministic monitor: risk={dao.risk_level}, "
        f"anomalies={len(dao.anomalies)}, violations={len(dao.compliance_violations)}, "
        f"compliance={dao.compliance_percent}%"
    )
    dao.ai_compliance_status = "violation" if dao.compliance_violations else "ok"
    dao.ai_risk_level = dao.risk_level
    dao.ai_escalate_to_human = dao.risk_level == "high"
    return dao

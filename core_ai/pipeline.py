from typing import Any, Dict, Optional

from core_ai.dao import DAO
from core_ai.parser import parse_to_dao
from core_ai.anomaly import check_anomalies
from core_ai.compliance import map_compliance
from core_ai.scorer import finalize_monitor_risk, build_dao_record


def process(raw_log: Dict[str, Any]) -> DAO:
    """
    AgentBridge Monitor — fully deterministic (no second LLM).
    Parse → anomalies → RBI compliance → risk tier → DAO record.
    """
    dao = parse_to_dao(raw_log)
    dao = check_anomalies(dao)
    dao = map_compliance(dao)
    dao = finalize_monitor_risk(dao)
    dao = build_dao_record(dao)

    dao.ai_recommended_action = None
    if dao.risk_level == "high":
        dao.ai_recommended_action = "Block or escalate to compliance officer"
    elif dao.risk_level == "medium":
        dao.ai_recommended_action = "Human review recommended"

    return dao


def dao_to_unified_dict(dao: DAO, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Unified structure for storage + downloads (mandatory schema)."""
    inp = dao.input or {}
    out = dao.output or {}
    amount = inp.get("amount")
    kyc = inp.get("kyc_verified")
    if kyc is None:
        kyc = inp.get("kyc")
    conf = out.get("confidence")
    if conf is None:
        try:
            conf = float(inp.get("confidence", 0))
        except (TypeError, ValueError):
            conf = 0.0

    base = {
        "agent_name": dao.agent_name,
        "decision": str(out.get("decision", "")),
        "action_type": dao.action_type,
        "amount": amount,
        "reasoning": dao.reasoning or "",
        "confidence": conf,
        "kyc_verified": bool(kyc) if kyc is not None else False,
        "session_id": dao.session_id or "",
        "timestamp": dao.timestamp,
        "anomalies": list(dao.anomalies),
        "violations": list(dao.compliance_violations),
        "compliance_percent": int(dao.compliance_percent),
        "risk_level": dao.risk_level,
        "dao": dict(dao.dao_record),
        "clause_status": dict(dao.clause_status),
    }
    if extra:
        base.update(extra)
    return base

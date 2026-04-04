"""
gateway/decision_gateway.py
Flow: validate → numeric risk score → policy → deterministic monitor (core_ai) → file storage → audit log.
"""
from datetime import datetime, timezone

from models.schemas import DecisionRequest, DecisionResponse, RejectedDecision
from validation.validator import validate
from policy.engine import evaluate
from risk.scorer import score, ALLOW_THRESHOLD
from app_logging.audit_logger import write as audit_write
from core_ai.pipeline import process as ai_process, dao_to_unified_dict
from utils.file_manager import append_session_log, write_incident, write_session_report


def _req_dump(req: DecisionRequest) -> dict:
    try:
        return req.model_dump()
    except AttributeError:
        return req.dict()


def _serialize(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _persist_monitor_artifacts(req: DecisionRequest, dao):
    unified = dao_to_unified_dict(dao, {"decision_id": req.decision_id, "api_key": req.api_key})
    try:
        append_session_log(req.session_id, unified)
        if dao.risk_level == "high":
            write_incident(req.session_id, unified)
        write_session_report(
            req.session_id,
            {
                "session_id": req.session_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "record": unified,
            },
        )
    except Exception:
        pass
    return unified


def process_decision(raw: dict) -> tuple[dict, int]:
    is_valid, req, error = validate(raw)
    if not is_valid:
        log_hash = audit_write(
            api_key=raw.get("api_key", "unknown"),
            decision_id=raw.get("decision_id", "unknown"),
            session_id=raw.get("session_id", "unknown"),
            agent_id=raw.get("agent_id", "unknown"),
            user_id=raw.get("user_id", "unknown"),
            action_type=raw.get("action_type", "unknown"),
            verdict="reject",
            risk_score=1.0,
            risk_level="critical",
            policy_violations=[f"VALIDATION_FAILED: {error}"],
            compliance_violations=[],
            input_data=raw.get("input", {}),
            output_data=raw.get("output", {}),
            reasoning=raw.get("reasoning", "") or "",
            confidence=0.0,
            ai_explanation=None,
            ai_recommended_action=None,
            ai_escalate_to_human=True,
            ai_regulatory_refs=[],
            ai_compliance_status="violation",
        )
        return _serialize(RejectedDecision(
            decision_id=raw.get("decision_id", "unknown"),
            blocked_at="validation",
            reason=error,
            policy_rule=None,
            risk_score=None,
            log_hash=log_hash,
        )), 422

    risk_score, risk_level, risk_explanation = score(req)
    policy_verdict, policy_violations = evaluate(req)
    blocking_violations = [v for v in policy_violations if v.block]

    if blocking_violations:
        blocker = blocking_violations[0]
        log_hash = audit_write(
            api_key=req.api_key,
            decision_id=req.decision_id,
            session_id=req.session_id,
            agent_id=req.agent_id,
            user_id=req.user_id,
            action_type=req.action_type,
            verdict="reject",
            risk_score=risk_score,
            risk_level=risk_level,
            policy_violations=[v.reason for v in policy_violations],
            compliance_violations=[],
            input_data=req.input,
            output_data=req.output,
            reasoning=req.reasoning,
            confidence=req.confidence,
            ai_explanation=None,
            ai_recommended_action=f"Human review required: {blocker.rule}",
            ai_escalate_to_human=True,
            ai_regulatory_refs=[],
            ai_compliance_status="violation",
        )
        return _serialize(RejectedDecision(
            decision_id=req.decision_id,
            blocked_at="policy",
            reason=blocker.reason,
            policy_rule=blocker.rule,
            risk_score=risk_score,
            log_hash=log_hash,
        )), 403

    monitor_raw = _req_dump(req)
    monitor_raw["output"] = {**monitor_raw.get("output", {}), "confidence": req.confidence}
    dao = ai_process(monitor_raw)
    unified = _persist_monitor_artifacts(req, dao)

    final_verdict = policy_verdict
    if risk_score >= ALLOW_THRESHOLD and final_verdict == "allow":
        final_verdict = "review"
    if dao.risk_level == "high" and final_verdict == "allow":
        final_verdict = "review"

    log_hash = audit_write(
        api_key=req.api_key,
        decision_id=req.decision_id,
        session_id=req.session_id,
        agent_id=req.agent_id,
        user_id=req.user_id,
        action_type=req.action_type,
        verdict=final_verdict,
        risk_score=risk_score,
        risk_level=risk_level,
        policy_violations=[v.reason for v in policy_violations],
        compliance_violations=dao.compliance_violations,
        input_data=req.input,
        output_data=req.output,
        reasoning=req.reasoning,
        confidence=req.confidence,
        ai_explanation=dao.ai_explanation,
        ai_recommended_action=dao.ai_recommended_action,
        ai_escalate_to_human=dao.ai_escalate_to_human,
        ai_regulatory_refs=dao.ai_regulatory_refs,
        ai_compliance_status=dao.ai_compliance_status,
    )

    http_code = 200 if final_verdict == "allow" else 202
    return _serialize(DecisionResponse(
        decision_id=req.decision_id,
        verdict=final_verdict,
        risk_score=risk_score,
        risk_level=risk_level,
        policy_violations=[v.reason for v in policy_violations],
        compliance_violations=dao.compliance_violations,
        ai_explanation=dao.ai_explanation or risk_explanation,
        ai_recommended_action=dao.ai_recommended_action,
        escalate_to_human=dao.ai_escalate_to_human,
        log_hash=log_hash,
        message=f"Decision {final_verdict.upper()} — logged and audited",
        monitor=unified,
    )), http_code

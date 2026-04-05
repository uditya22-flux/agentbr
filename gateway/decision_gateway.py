"""
gateway/decision_gateway.py
Flow: Multi-tenant validation → risk scoring → policy evaluation → AI monitoring → audit logging.
"""
from datetime import datetime, timezone
from models.schemas import DecisionRequest, DecisionResponse, RejectedDecision
from validation.validator import validate
from policy.engine import evaluate
from risk.scorer import score, ALLOW_THRESHOLD
from app_logging.audit_logger import write as audit_write
from core_ai.pipeline import process as ai_process, dao_to_unified_dict

def _req_dump(req: DecisionRequest) -> dict:
    try:
        return req.model_dump()
    except AttributeError:
        return req.dict()

def _serialize(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()

def process_decision(raw: dict) -> tuple[dict, int]:
    # raw contains org_id and agent_id from the security middleware
    org_id = raw.get("org_id")
    agent_id = raw.get("agent_id")

    is_valid, req, error = validate(raw)
    if not is_valid:
        log_hash = audit_write(
            org_id=org_id,
            agent_id=agent_id,
            decision_id=raw.get("decision_id", "unknown"),
            session_id=raw.get("session_id", "unknown"),
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
            ai_action_summary="Policy enforcement: rejection"
        )
        return _serialize(RejectedDecision(
            decision_id=raw.get("decision_id", "unknown"),
            blocked_at="validation",
            reason=error,
            log_hash=log_hash,
        )), 422

    risk_score, risk_level, risk_explanation = score(req)
    policy_verdict, policy_violations = evaluate(req)
    blocking_violations = [v for v in policy_violations if v.block]

    if blocking_violations:
        blocker = blocking_violations[0]
        log_hash = audit_write(
            org_id=org_id,
            agent_id=agent_id,
            decision_id=req.decision_id,
            session_id=req.session_id,
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
            ai_action_summary=f"Policy rejection: {blocker.rule}"
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
    # The monitor pipeline might not know about org_id, let's inject it if needed
    dao = ai_process(monitor_raw)

    final_verdict = policy_verdict
    if risk_score >= ALLOW_THRESHOLD and final_verdict == "allow":
        final_verdict = "review"
    if dao.risk_level == "high" and final_verdict == "allow":
        final_verdict = "review"

    log_hash = audit_write(
        org_id=org_id,
        agent_id=agent_id,
        decision_id=req.decision_id,
        session_id=req.session_id,
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
        ai_action_summary=dao.ai_action_summary
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
    )), http_code

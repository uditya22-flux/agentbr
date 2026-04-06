"""
Strict Pydantic schemas — nothing enters the system without passing these.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
import uuid

KNOWN_GATEWAY_ACTIONS = frozenset(
    {"loan", "transfer", "approve", "reject", "verify", "query", "flag"}
)


class DecisionRequest(BaseModel):
    """Incoming request to the decision gateway."""
    model_config = ConfigDict(extra="ignore")

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(..., min_length=1)
    agent_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    action_type: str = Field(..., min_length=1)
    input: Dict[str, Any] = Field(...)
    reasoning: str = Field(default="")
    confidence: float = Field(..., ge=0.0, le=1.0)
    output: Dict[str, Any] = Field(default_factory=dict)
    domain: str = Field(default="fintech")
    api_key: str = Field(..., min_length=1)


class DecisionResponse(BaseModel):
    decision_id: str
    verdict: str
    risk_score: float
    risk_level: str
    policy_violations: List[str]
    compliance_violations: List[str]
    ai_explanation: Optional[str]
    ai_recommended_action: Optional[str]
    escalate_to_human: bool
    log_hash: str
    message: str
    monitor: Optional[Dict[str, Any]] = None


class RejectedDecision(BaseModel):
    decision_id: str
    verdict: str = "reject"
    blocked_at: str
    reason: str
    policy_rule: Optional[str]
    risk_score: Optional[float]
    log_hash: str
    message: str = "Decision blocked by AgentBridge compliance gateway"

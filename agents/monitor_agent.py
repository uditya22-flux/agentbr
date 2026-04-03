"""
AgentBridge — Monitor Agent (Groq Edition)
========================================
Intercepts the worker agent's execution trace.
Audits against RBI FREE-AI Framework + anomaly rules.
Powered by Groq's Llama 3 model.
"""

import httpx
import json
import uuid
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass
from agents.worker_agent import WorkerResult

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

@dataclass
class Violation:
    type: str        # RBI_CLAUSE / ANOMALY / FINANCIAL_CRIME / DATA_BREACH
    clause: str      # e.g. "Clause 3.1" or "Anomaly Rule 3"
    description: str
    severity: str    # low / medium / high / critical


@dataclass
class RBIFlag:
    clause: str      # e.g. "Clause 6.1"
    name: str        # e.g. "KYC for approvals"
    reason: str      # why this specific action violates it


@dataclass
class Anomaly:
    rule: str        # e.g. "Rule 3"
    description: str
    evidence: str    # exact field/value that triggered it


@dataclass
class MonitorVerdict:
    """Full output from the AgentBridge monitor agent."""
    verdict: str                  # APPROVE / FLAG / BLOCK
    risk_level: str               # low / medium / high / critical
    violations: list[Violation]
    rbi_flags: list[RBIFlag]
    anomalies: list[Anomaly]
    compliance_report: str        # plain English for compliance officer
    reason: str                   # one-line verdict explanation
    dao_id: str                   # e.g. DAG-A3F9B2
    evidence_hash: str            # SHA256 tamper-proof seal
    human_review_required: bool
    timestamp: str


MONITOR_SYSTEM_PROMPT = """You are AgentBridge — an elite AI compliance monitor for fintech companies in India.

Your job: receive a worker agent's full execution trace and produce a forensic compliance audit.

RBI FREE-AI FRAMEWORK — 8 CLAUSES YOU ENFORCE:
Clause 1.3 — Agent identification: VIOLATION if agent_name missing
Clause 2.1 — Input data logging: VIOLATION if data_accessed is empty
Clause 3.1 — Reasoning required: VIOLATION if reasoning is empty or under 10 chars
Clause 4.2 — Timestamps: VIOLATION if no timestamp on the decision
Clause 4.4 — Session grouping: VIOLATION if session_id is missing or empty
Clause 5.0 — Output recorded: VIOLATION if outcome is empty
Clause 5.2 — Action classification: VIOLATION if action_type not in known list
Clause 6.1 — KYC for approvals: VIOLATION if action_type=approve AND kyc_verified=false

6 ANOMALY RULES:
Rule 1: amount > 50000 AND approve AND no risk flag → HIGH
Rule 2: reasoning empty or vague → MEDIUM
Rule 3: approve AND kyc_verified=false → HIGH
Rule 4: unknown action_type → MEDIUM
Rule 5: approve AND confidence < 0.75 → MEDIUM
Rule 6: bias pattern — repeated rejections on same user → MEDIUM

VERDICT:
APPROVE = no violations, low risk
FLAG = 1-2 medium issues, needs review
BLOCK = any high/critical violation, halt immediately

Return ONLY raw JSON, no markdown, no backticks:
{
  "verdict": "APPROVE or FLAG or BLOCK",
  "risk_level": "low or medium or high or critical",
  "violations": [{"type":"RBI_CLAUSE or ANOMALY","clause":"Clause 3.1","description":"...","severity":"high"}],
  "rbi_flags": [{"clause":"Clause 6.1","name":"KYC for approvals","reason":"..."}],
  "anomalies": [{"rule":"Rule 3","description":"...","evidence":"kyc_verified: false"}],
  "compliance_report": "2-3 sentence summary for compliance officer",
  "reason": "one sentence verdict explanation",
  "human_review_required": true,
  "dao_id": "DAG-XXXXXX"
}"""


class MonitorAgent:
    """
    The AgentBridge monitor agent powered by Groq.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model

    def _make_evidence_hash(self, task: str, worker: WorkerResult) -> str:
        payload = json.dumps({
            "task":       task,
            "decision":   worker.decision,
            "reasoning":  worker.reasoning,
            "actions":    worker.actions,
            "outcome":    worker.outcome,
            "confidence": worker.confidence,
            "session_id": worker.session_id,
            "timestamp":  datetime.now(timezone.utc).isoformat()
        }, sort_keys=True)
        return "SHA256:" + hashlib.sha256(payload.encode()).hexdigest()[:24]

    def intercept(self, task: str, worker: WorkerResult) -> MonitorVerdict:
        """
        Intercept a worker agent's execution trace and audit it.
        """
        evidence_hash = self._make_evidence_hash(task, worker)

        prompt = f"""INTERCEPT — Full RBI compliance audit required.

ORIGINAL TASK:
{task}

WORKER AGENT EXECUTION TRACE:
Decision     : {worker.decision}
Reasoning    : {worker.reasoning}
Actions taken: {json.dumps(worker.actions)}
Data accessed: {json.dumps(worker.data_accessed)}
Outcome      : {worker.outcome}
Confidence   : {worker.confidence}
Action type  : {worker.action_type}
KYC verified : {worker.kyc_verified}
Amount (INR) : {worker.amount}
Session ID   : {worker.session_id}
Evidence hash: {evidence_hash}

Audit every RBI clause and every anomaly rule. Return ONLY the JSON verdict."""

        try:
            with httpx.Client(timeout=30) as client:
                res = client.post(
                    GROQ_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": MONITOR_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"}
                    }
                )
                res.raise_for_status()
                data = res.json()["choices"][0]["message"]["content"]
                if isinstance(data, str):
                    data = json.loads(data)
        except Exception as e:
            data = {
                "verdict": "FLAG",
                "risk_level": "high",
                "violations": [],
                "rbi_flags": [],
                "anomalies": [],
                "compliance_report": f"Monitor error: {str(e)}",
                "reason": "Could not complete audit. Treat as high risk.",
                "human_review_required": True,
                "dao_id": "DAG-ERR"
            }

        return MonitorVerdict(
            verdict=data.get("verdict", "FLAG"),
            risk_level=data.get("risk_level", "high"),
            violations=[Violation(**v) for v in data.get("violations", [])
                        if all(k in v for k in ["type","clause","description","severity"])],
            rbi_flags=[RBIFlag(**f) for f in data.get("rbi_flags", [])
                       if all(k in f for k in ["clause","name","reason"])],
            anomalies=[Anomaly(**a) for a in data.get("anomalies", [])
                       if all(k in a for k in ["rule","description","evidence"])],
            compliance_report=data.get("compliance_report", ""),
            reason=data.get("reason", ""),
            dao_id=data.get("dao_id", "DAG-" + str(uuid.uuid4())[:6].upper()),
            evidence_hash=evidence_hash,
            human_review_required=data.get("human_review_required", False),
            timestamp=datetime.now(timezone.utc).isoformat()
        )

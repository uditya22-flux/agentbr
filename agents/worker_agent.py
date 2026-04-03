"""
AgentBridge — Worker Agent (Groq Edition)
========================================
The fintech AI agent that does the actual work.
Powered by Groq's high-speed inference engine.
"""

import httpx
import json
import uuid
from dataclasses import dataclass, field

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

@dataclass
class WorkerResult:
    """Structured output from the worker agent — fed directly into the monitor."""
    task: str
    decision: str
    reasoning: str
    actions: list[str]
    data_accessed: list[str]
    outcome: str
    confidence: float
    action_type: str        # approve / reject / flag / verify / query / transfer
    kyc_verified: bool
    amount: float
    session_id: str


WORKER_SYSTEM_PROMPT = """You are a fintech AI agent working for a bank in India.
You autonomously process financial tasks: loan approvals, fraud detection, 
KYC verification, wire transfers, and payment processing.

When you receive a task:
1. Think carefully about what the task requires
2. Decide what data you need to access
3. List the actions you take step by step
4. Make a clear decision with reasoning
5. State the final outcome

IMPORTANT: Respond ONLY in raw JSON. No markdown. No backticks. No explanation outside JSON.

Return exactly this structure:
{
  "decision": "short one-line decision made",
  "reasoning": "2-3 sentences explaining why you made this decision",
  "actions": [
    "action 1 you took",
    "action 2 you took",
    "action 3 you took",
    "action 4 you took"
  ],
  "data_accessed": ["credit_score", "kyc_status", "account_balance"],
  "outcome": "what happened as a result — the final state",
  "confidence": 0.92,
  "action_type": "approve",
  "kyc_verified": true,
  "amount": 5000,
  "session_id": "sess_XXXX"
}

Rules:
- confidence must be 0.0 to 1.0
- action_type must be one of: approve, reject, flag, verify, query, transfer
- kyc_verified: true only if KYC was actually checked and passed
- amount: the transaction amount in INR (0 if not applicable)
- Be realistic — if a task is risky or missing KYC, reflect that
"""


class WorkerAgent:
    """
    The fintech worker agent powered by Groq.

    Usage:
        agent = WorkerAgent(api_key="gsk_...")
        result = agent.run("Approve a ₹5,000 wire transfer to vendor account #9023")
        print(result.decision)
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model
        self.session_id = "sess_" + str(uuid.uuid4())[:8].upper()

    def run(self, task: str) -> WorkerResult:
        """
        Run the worker agent on a task.
        """
        prompt = f"""Task: {task}
Your session ID for this run: {self.session_id}

Process this task and return your structured JSON response."""

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
                            {"role": "system", "content": WORKER_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"}
                    }
                )
                res.raise_for_status()
                data = res.json()["choices"][0]["message"]["content"]
                if isinstance(data, str):
                    data = json.loads(data)
        except Exception as e:
            # Safe fallback if API call fails
            data = {
                "decision": f"Error: {str(e)}",
                "reasoning": "Agent encountered an API error. Manual review required.",
                "actions": ["Connection attempt", "API failure"],
                "data_accessed": ["network_logs"],
                "outcome": "Task failed due to technical error",
                "confidence": 0.0,
                "action_type": "flag",
                "kyc_verified": False,
                "amount": 0,
                "session_id": self.session_id
            }

        return WorkerResult(
            task=task,
            decision=data.get("decision", ""),
            reasoning=data.get("reasoning", ""),
            actions=data.get("actions", []),
            data_accessed=data.get("data_accessed", []),
            outcome=data.get("outcome", ""),
            confidence=float(data.get("confidence", 0.0)),
            action_type=data.get("action_type", "query"),
            kyc_verified=bool(data.get("kyc_verified", False)),
            amount=float(data.get("amount", 0)),
            session_id=str(data.get("session_id", self.session_id))
        )

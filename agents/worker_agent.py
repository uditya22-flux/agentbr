"""
AgentBridge — Worker Agent (Google Gemini)
Single LLM in the product: produces structured JSON decisions.
Monitor is deterministic (core_ai), not a second model.
"""
import json
import os
import uuid
from dataclasses import dataclass
from typing import Optional, List, Any

import google.generativeai as genai

DEFAULT_MODEL = "gemini-1.5-flash"


@dataclass
class WorkerResult:
    task: str
    decision: str
    reasoning: str
    actions: List[Any]
    data_accessed: List[Any]
    outcome: str
    confidence: float
    action_type: str
    kyc_verified: bool
    amount: float
    session_id: str


WORKER_SYSTEM_PROMPT = """You are a fintech AI agent for an Indian bank.
Process tasks: loans, transfers, fraud checks, KYC, payments.

Respond ONLY with raw JSON. No markdown. No code fences.

Schema:
{
  "decision": "one-line decision",
  "reasoning": "2-3 sentences",
  "actions": ["step1", "step2"],
  "data_accessed": ["field names checked"],
  "outcome": "final state",
  "confidence": 0.92,
  "action_type": "approve",
  "kyc_verified": true,
  "amount": 5000,
  "session_id": "sess_XXXX"
}

Rules:
- confidence: 0.0–1.0
- action_type must be one of: loan, transfer, approve, reject, verify, query, flag
- kyc_verified: true only if KYC was verified
- amount: INR (0 if N/A)
- session_id: reuse the session id given in the user message if provided
"""


class WorkerAgent:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise ValueError("GEMINI_API_KEY is required for WorkerAgent")
        genai.configure(api_key=key)
        try:
            self._model = genai.GenerativeModel(
                model,
                system_instruction=WORKER_SYSTEM_PROMPT,
            )
            self._inline_system = False
        except TypeError:
            self._model = genai.GenerativeModel(model)
            self._inline_system = True
        self.model = model
        self.session_id = "sess_" + str(uuid.uuid4())[:8].upper()

    def run(self, task: str) -> WorkerResult:
        prompt = f"""Task: {task}
Session ID for this run: {self.session_id}
Return JSON only."""

        user_content = (
            WORKER_SYSTEM_PROMPT + "\n\n" + prompt if getattr(self, "_inline_system", True) else prompt
        )
        try:
            try:
                res = self._model.generate_content(
                    user_content,
                    generation_config=genai.GenerationConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )
            except Exception:
                res = self._model.generate_content(
                    user_content,
                    generation_config=genai.GenerationConfig(temperature=0.2),
                )
            text = (res.text or "").strip()
            if text.startswith("```"):
                text = text.split("```", 2)[-1]
                if text.startswith("json"):
                    text = text[4:].lstrip()
            data = json.loads(text)
        except Exception as e:
            data = {
                "decision": f"Error: {str(e)}",
                "reasoning": "Worker agent failed — manual review required.",
                "actions": ["error"],
                "data_accessed": [],
                "outcome": "failed",
                "confidence": 0.0,
                "action_type": "flag",
                "kyc_verified": False,
                "amount": 0,
                "session_id": self.session_id,
            }

        return WorkerResult(
            task=task,
            decision=str(data.get("decision", "")),
            reasoning=str(data.get("reasoning", "")),
            actions=list(data.get("actions") or []),
            data_accessed=list(data.get("data_accessed") or []),
            outcome=str(data.get("outcome", "")),
            confidence=float(data.get("confidence", 0.0)),
            action_type=str(data.get("action_type", "query")).lower().strip(),
            kyc_verified=bool(data.get("kyc_verified", False)),
            amount=float(data.get("amount", 0) or 0),
            session_id=str(data.get("session_id", self.session_id)),
        )

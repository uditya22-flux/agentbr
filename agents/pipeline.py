"""
agents/pipeline.py
Worker (Gemini) → AgentBridge Monitor (core_ai, deterministic) → file storage → optional backend.
"""
from __future__ import annotations

import json
import time
import uuid
import httpx
from datetime import datetime, timezone
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from agents.worker_agent import WorkerAgent, WorkerResult
from core_ai.pipeline import process as monitor_process, dao_to_unified_dict
from core_ai.report_cleaner import clean_report
from utils.file_manager import append_session_log, write_incident, write_session_report


class BackendLogger:
    def __init__(self, backend_url: str, api_key: str):
        self.url = backend_url.rstrip("/")
        self.api_key = api_key

    def send_decision(self, payload: dict) -> dict:
        try:
            with httpx.Client(timeout=45) as client:
                res = client.post(
                    f"{self.url}/decide",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": self.api_key,
                    },
                )
                try:
                    return res.json()
                except Exception:
                    return {"status_code": res.status_code, "text": res.text[:500]}
        except httpx.TimeoutException:
            return {"error": "timeout"}
        except Exception as e:
            return {"error": str(e)}


def _worker_to_gateway_payload(worker: WorkerResult, task: str, api_key: str) -> dict:
    return {
        "api_key": api_key,
        "session_id": worker.session_id,
        "agent_id": "fintech_agent_v1",
        "user_id": "pipeline_user",
        "action_type": worker.action_type if worker.action_type in {
            "loan", "transfer", "approve", "reject", "verify", "query", "flag"
        } else "query",
        "input": {
            "amount": worker.amount,
            "kyc_verified": worker.kyc_verified,
            "task": task,
        },
        "reasoning": worker.reasoning or "",
        "confidence": worker.confidence,
        "output": {
            "decision": worker.decision,
            "outcome": worker.outcome,
            "confidence": worker.confidence,
        },
    }


def _build_mini_report_from_dao(task: str, worker: WorkerResult, unified: dict) -> dict:
    risk_level = unified.get("risk_level", "low")
    flagged = risk_level in ("high", "medium")
    total = 1
    n_flagged = 1 if flagged else 0
    verdict_str = (
        f"NON-COMPLIANT — {n_flagged} of {total} decisions flagged."
        if n_flagged else
        "COMPLIANT — All decisions passed monitor checks."
    )
    return {
        "report_id": f"RPT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:6].upper()}",
        "session_id": worker.session_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent_name": "fintech_agent_v1",
        "session_summary": {
            "total_decisions": total,
            "flagged": n_flagged,
            "clean": total - n_flagged,
            "risk_breakdown": {
                "high": 1 if risk_level == "high" else 0,
                "medium": 1 if risk_level == "medium" else 0,
                "low": 1 if risk_level == "low" else 0,
            },
        },
        "flagged_decisions": [
            {
                "decision_id": unified.get("decision_id", str(uuid.uuid4())),
                "timestamp": unified.get("timestamp", ""),
                "action_type": worker.action_type,
                "risk_level": risk_level,
                "flag_reason": " | ".join(unified.get("violations", []) + unified.get("anomalies", [])),
                "input": {"amount": worker.amount, "kyc_verified": worker.kyc_verified},
                "reasoning": worker.reasoning,
                "output": {"confidence": worker.confidence},
            }
        ] if flagged else [],
        "compliance_coverage": {},
        "violation_summary": {v: 1 for v in unified.get("violations", [])},
        "verdict": verdict_str,
        "rbi_response_block": {
            "prepared_by": "AgentBridge Audit System",
            "framework": "RBI FREE-AI-aligned deterministic monitor",
            "session_covered": worker.session_id,
            "total_agent_decisions_audited": total,
            "high_risk_decisions": 1 if risk_level == "high" else 0,
            "compliance_verdict": verdict_str,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "note": task[:500],
        },
    }


class AgentBridgePipeline:
    def __init__(
        self,
        gemini_key: Optional[str] = None,
        ab_key: str = "test123",
        backend_url: str = "http://localhost:8000",
    ):
        self.worker = WorkerAgent(api_key=gemini_key)
        self.logger = BackendLogger(backend_url=backend_url, api_key=ab_key)
        self.ab_key = ab_key

    def run(self, task: str, log_to_backend: bool = True) -> dict:
        start = time.time()
        worker_result = self.worker.run(task)
        _known_at = {"loan", "transfer", "approve", "reject", "verify", "query", "flag"}
        _at = (worker_result.action_type or "query").lower().strip()
        if _at not in _known_at:
            _at = "query"
        worker_result = WorkerResult(
            task=worker_result.task,
            decision=worker_result.decision,
            reasoning=worker_result.reasoning,
            actions=worker_result.actions,
            data_accessed=worker_result.data_accessed,
            outcome=worker_result.outcome,
            confidence=worker_result.confidence,
            action_type=_at,
            kyc_verified=worker_result.kyc_verified,
            amount=worker_result.amount,
            session_id=worker_result.session_id,
        )

        raw_monitor = {
            "decision_id": str(uuid.uuid4()),
            "session_id": worker_result.session_id,
            "agent_name": "fintech_agent_v1",
            "action_type": worker_result.action_type,
            "reasoning": worker_result.reasoning,
            "decision": worker_result.decision,
            "amount": worker_result.amount,
            "kyc_verified": worker_result.kyc_verified,
            "confidence": worker_result.confidence,
            "input": {
                "amount": worker_result.amount,
                "kyc_verified": worker_result.kyc_verified,
                "task": task,
            },
            "output": {
                "decision": worker_result.decision,
                "outcome": worker_result.outcome,
                "confidence": worker_result.confidence,
            },
        }

        dao = monitor_process(raw_monitor)
        unified = dao_to_unified_dict(dao, {"decision_id": raw_monitor["decision_id"]})

        append_session_log(worker_result.session_id, unified)
        if dao.risk_level == "high":
            write_incident(worker_result.session_id, unified)
        write_session_report(
            worker_result.session_id,
            {
                "session_id": worker_result.session_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "record": unified,
            },
        )

        backend_response = {}
        if log_to_backend:
            payload = _worker_to_gateway_payload(worker_result, task, self.ab_key)
            backend_response = self.logger.send_decision(payload)

        raw_report = _build_mini_report_from_dao(task, worker_result, unified)
        cleaned = clean_report(raw_report)

        latency = int((time.time() - start) * 1000)

        return {
            "task": task,
            "worker": asdict(worker_result),
            "monitor": unified,
            "dao_risk_level": dao.risk_level,
            "backend_response": backend_response,
            "cleaned_report": cleaned,
            "latency_ms": latency,
        }

    def run_batch(self, scenarios: List[dict], log_to_backend: bool = True) -> dict:
        results = []
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n{'═'*60}\n  [{i}/{len(scenarios)}] {scenario['name']}\n{'═'*60}")
            result = self.run(scenario["task"], log_to_backend=log_to_backend)
            print(f"  Worker: {result['worker']['decision'][:70]}")
            print(f"  Monitor risk: {result['dao_risk_level']} | compliance {result['monitor'].get('compliance_percent')}%")
            results.append({"scenario": scenario["name"], **result})
            time.sleep(0.4)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_runs": len(results),
            "results": results,
        }

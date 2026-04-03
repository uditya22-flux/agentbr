"""
agents/pipeline.py
==================
AgentBridge unified pipeline.

Orchestrates the full flow:
  1. WorkerAgent  → receives task, reasons, acts (Groq LLM)
  2. MonitorAgent → intercepts trace, audits against RBI FREE-AI + anomaly rules
  3. BackendLogger → POST /log → gateway → Supabase audit log
  4. ReportCleaner → normalizes raw report output into clean structured JSON

Usage:
    from agents.pipeline import AgentBridgePipeline
    pipeline = AgentBridgePipeline(groq_key="gsk_...", ab_key="test123", backend_url="https://...")
    result = pipeline.run("Approve a ₹5,000 wire transfer to vendor #9023")
    print(result["verdict"]["verdict"])   # APPROVE / FLAG / BLOCK
"""

import json
import time
import httpx
import uuid
from datetime import datetime, timezone
from dataclasses import asdict

from agents.worker_agent import WorkerAgent, WorkerResult
from agents.monitor_agent import MonitorAgent, MonitorVerdict
from core_ai.report_cleaner import clean_report


# ══════════════════════════════════════════════════════
#  BACKEND LOGGER
# ══════════════════════════════════════════════════════

class BackendLogger:
    """
    Sends the full audit result to the AgentBridge backend.
    POST /log → gateway → core_ai pipeline → Supabase
    """

    def __init__(self, backend_url: str, api_key: str):
        self.url     = backend_url.rstrip("/")
        self.api_key = api_key

    def send(self, task: str, worker: WorkerResult, verdict: MonitorVerdict) -> dict:
        payload = {
            "api_key":     self.api_key,
            "agent_name":  "agentbridge-worker-v1",
            "action":      worker.decision,
            "action_type": worker.action_type,
            "reasoning":   worker.reasoning,
            "session_id":  worker.session_id,
            "decision_id": verdict.dao_id,
            "domain":      "fintech",
            "inputs": {
                "task":          task,
                "amount":        worker.amount,
                "kyc_verified":  worker.kyc_verified,
                "data_accessed": worker.data_accessed,
            },
            "output": {
                "decision":   worker.decision,
                "outcome":    worker.outcome,
                "confidence": worker.confidence,
                "verdict":    verdict.verdict,
                "risk_level": verdict.risk_level,
            },
            "flag_reason": verdict.reason if verdict.verdict != "APPROVE" else "",
        }

        try:
            with httpx.Client(timeout=30) as client:
                res = client.post(
                    f"{self.url}/log",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                return res.json()
        except httpx.TimeoutException:
            return {"error": "timeout", "note": "Backend may be sleeping — wait 60s and retry"}
        except Exception as e:
            return {"error": str(e)}


# ══════════════════════════════════════════════════════
#  PIPELINE
# ══════════════════════════════════════════════════════

class AgentBridgePipeline:
    """
    Full AgentBridge pipeline.
    Two agents, one watching the other:
      - WorkerAgent  → does the fintech task
      - MonitorAgent → audits every action in real-time
    """

    def __init__(
        self,
        groq_key: str,
        ab_key: str   = "test123",
        backend_url: str = "https://agent-bridge-lh2w.onrender.com",
    ):
        self.worker  = WorkerAgent(api_key=groq_key)
        self.monitor = MonitorAgent(api_key=groq_key)
        self.logger  = BackendLogger(backend_url=backend_url, api_key=ab_key)

    def run(self, task: str, log_to_backend: bool = True) -> dict:
        """
        Run a single task through the full pipeline.

        Returns dict with keys:
            task, worker, verdict, backend_response,
            cleaned_report, latency_ms
        """
        start = time.time()

        # Step 1 — Worker Agent
        worker_result = self.worker.run(task)

        # Step 2 — Monitor Agent
        verdict = self.monitor.intercept(task, worker_result)

        # Step 3 — Log to backend
        backend_response = {}
        if log_to_backend:
            backend_response = self.logger.send(task, worker_result, verdict)

        latency = int((time.time() - start) * 1000)

        # Step 4 — Build + clean a mini-report for this decision
        raw_report = _build_mini_report(task, worker_result, verdict)
        cleaned    = clean_report(raw_report)

        return {
            "task":             task,
            "worker":           asdict(worker_result),
            "verdict":          asdict(verdict),
            "backend_response": backend_response,
            "cleaned_report":   cleaned,
            "latency_ms":       latency,
        }

    def run_batch(self, scenarios: list[dict], log_to_backend: bool = True) -> dict:
        """
        Run multiple scenarios. Each item must have 'name' and 'task' keys.
        Returns full audit trail dict (matches audit_trail.json format).
        """
        results  = []
        verdicts = []

        for i, scenario in enumerate(scenarios, 1):
            _print_scenario_header(i, len(scenarios), scenario["name"])
            result = self.run(scenario["task"], log_to_backend=log_to_backend)
            _print_result(result)
            results.append({"scenario": scenario["name"], **result})
            verdicts.append(result["verdict"]["verdict"])
            time.sleep(0.5)

        audit_trail = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_runs":   len(results),
            "summary": {
                "APPROVE": verdicts.count("APPROVE"),
                "FLAG":    verdicts.count("FLAG"),
                "BLOCK":   verdicts.count("BLOCK"),
            },
            "results": results,
        }
        return audit_trail


# ══════════════════════════════════════════════════════
#  MINI REPORT BUILDER
# (Converts a single pipeline result into a report_generator-compatible dict
#  so clean_report() can normalize it — same schema as multi-decision reports)
# ══════════════════════════════════════════════════════

def _build_mini_report(task: str, worker: WorkerResult, verdict: MonitorVerdict) -> dict:
    risk_level = verdict.risk_level if verdict.risk_level in ("high","medium","low") else "high"
    flagged    = verdict.verdict != "APPROVE"

    flag_parts = []
    if verdict.violations:
        flag_parts += [f"{v.clause} — {v.description}" for v in verdict.violations]
    if verdict.anomalies:
        flag_parts += [f"{a.rule} — {a.description}" for a in verdict.anomalies]

    violation_summary = {}
    for v in verdict.violations:
        key = f"VIOLATION — {v.clause}: {v.description}"
        violation_summary[key] = violation_summary.get(key, 0) + 1

    compliance_coverage = {}
    for f in verdict.rbi_flags:
        clause_key = f"{f.clause} — {f.name}"
        compliance_coverage[clause_key] = "1/1 decisions"

    total   = 1
    n_flagged = 1 if flagged else 0
    verdict_str = (
        f"NON-COMPLIANT — {n_flagged} of {total} decisions flagged. Immediate remediation required."
        if n_flagged else
        "COMPLIANT — All decisions passed anomaly checks and RBI clause requirements."
    )

    return {
        "report_id":    f"RPT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:6].upper()}",
        "session_id":   worker.session_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent_name":   "agentbridge-worker-v1",
        "session_summary": {
            "total_decisions": total,
            "flagged":         n_flagged,
            "clean":           total - n_flagged,
            "risk_breakdown":  {
                "high":   1 if risk_level == "high" else 0,
                "medium": 1 if risk_level == "medium" else 0,
                "low":    1 if risk_level == "low" else 0,
            },
        },
        "flagged_decisions": [
            {
                "decision_id": verdict.dao_id,
                "timestamp":   verdict.timestamp,
                "action_type": worker.action_type,
                "risk_level":  risk_level,
                "flag_reason": " | ".join(flag_parts) if flag_parts else verdict.reason,
                "input":       {"amount": worker.amount, "kyc_verified": worker.kyc_verified},
                "reasoning":   worker.reasoning or None,
                "output":      {"confidence": worker.confidence},
            }
        ] if flagged else [],
        "compliance_coverage": compliance_coverage,
        "violation_summary":   violation_summary,
        "verdict":             verdict_str,
        "rbi_response_block": {
            "prepared_by":                "AgentBridge Audit System",
            "framework":                  "RBI FREE-AI Framework (August 2025)",
            "session_covered":            worker.session_id,
            "total_agent_decisions_audited": total,
            "high_risk_decisions":        1 if risk_level == "high" else 0,
            "compliance_verdict":         verdict_str,
            "generated_at":               datetime.now(timezone.utc).isoformat(),
            "note":                       verdict.compliance_report,
        },
    }


# ══════════════════════════════════════════════════════
#  PRINT HELPERS
# ══════════════════════════════════════════════════════

def _print_scenario_header(i: int, total: int, name: str):
    print(f"\n{'═'*60}")
    print(f"  [{i}/{total}] {name}")
    print(f"{'═'*60}")

def _print_result(result: dict):
    w = result["worker"]
    v = result["verdict"]
    icon = {"APPROVE": "✓", "FLAG": "⚑", "BLOCK": "✕"}.get(v["verdict"], "?")

    print(f"  Worker   : {w['decision'][:70]}")
    print(f"  Action   : {w['action_type']}  |  KYC: {w['kyc_verified']}  |  ₹{w['amount']:,.0f}  |  conf: {w['confidence']}")
    print(f"  Verdict  : {icon} {v['verdict']}  |  Risk: {v['risk_level'].upper()}")

    if v["violations"]:
        print(f"  Violations ({len(v['violations'])}):")
        for viol in v["violations"]:
            print(f"    [{viol['severity'].upper()}] {viol['clause']} — {viol['description']}")

    be = result.get("backend_response", {})
    if "error" in be:
        print(f"  Backend  : ⚠ {be['error']}")
    elif be:
        print(f"  Backend  : ✓ logged")

    cr = result.get("cleaned_report", {})
    verdict_status = cr.get("verdict", {}).get("status", "")
    print(f"  Report   : {verdict_status}  |  {result['latency_ms']}ms")

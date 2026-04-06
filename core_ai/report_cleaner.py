import json
import ast
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _parse_raw_field(raw: Any) -> dict:
    """Parse Python-style dict strings like {'amount': 75000, 'kyc_verified': False}"""
    if isinstance(raw, dict):
        return raw
    if not raw or not isinstance(raw, str):
        return {}
    try:
        return ast.literal_eval(raw)
    except Exception:
        try:
            normalized = (
                raw.replace("'", '"')
                   .replace("True", "true")
                   .replace("False", "false")
                   .replace("None", "null")
            )
            return json.loads(normalized)
        except Exception:
            return {"_raw_unparsed": raw}


def _gen_decision_id(index: int) -> str:
    short = str(uuid.uuid4())[:8].upper()
    return f"DEC-{short}-{str(index + 1).zfill(3)}"


def _fmt_ts(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(str(ts))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


def _compliance_pct(val: str) -> int:
    """'3/3 decisions' → 100"""
    try:
        parts = str(val).replace(" decisions", "").split("/")
        return round(int(parts[0]) / int(parts[1]) * 100)
    except Exception:
        return 0


# ─────────────────────────────────────────
# DECISION CLEANER
# ─────────────────────────────────────────

def _clean_decision(raw_dec: dict, index: int) -> dict:
    dec_id = raw_dec.get("decision_id")
    if not dec_id or str(dec_id) in ("None", "null", ""):
        dec_id = _gen_decision_id(index)
        id_source = "auto_generated"
    else:
        id_source = "original"

    # Extract raw input/output if they are in the expected nested format or just handle them if already dicts
    inp = raw_dec.get("input")
    if isinstance(inp, dict) and "raw" in inp:
        input_data = _parse_raw_field(inp["raw"])
    else:
        input_data = _parse_raw_field(inp)

    out = raw_dec.get("output")
    if isinstance(out, dict) and "raw" in out:
        output_data = _parse_raw_field(out["raw"])
    else:
        output_data = _parse_raw_field(out)

    reasoning = raw_dec.get("reasoning")
    if not reasoning:
        reasoning       = "MISSING — VIOLATION"
        reasoning_valid = False
    else:
        reasoning_valid = True

    amount     = input_data.get("amount")
    kyc        = input_data.get("kyc_verified", None)
    confidence = output_data.get("confidence")
    action     = raw_dec.get("action_type", "unknown")
    risk       = raw_dec.get("risk_level", "unknown")

    flags = []
    if risk == "high" and kyc is False:
        flags.append("high_risk_without_kyc")
    if action == "approve" and confidence is not None and confidence < 0.75:
        flags.append("low_confidence_approval")
    if not reasoning_valid:
        flags.append("missing_reasoning")
    if amount and amount >= 50000:
        flags.append("high_value_transaction")

    flag_reasons = [
        f.strip()
        for f in str(raw_dec.get("flag_reason", "")).split("|")
        if f.strip()
    ]

    return {
        "decision_id":     dec_id,
        "decision_id_source": id_source,
        "session_id":      raw_dec.get("session_id", None),
        "timestamp":       _fmt_ts(raw_dec.get("timestamp", "")),
        "timestamp_raw":   raw_dec.get("timestamp", ""),
        "action_type":     action,
        "risk_level":      risk,
        "reasoning":       reasoning,
        "reasoning_valid": reasoning_valid,
        "input": {
            "amount":       amount,
            "kyc_verified": kyc,
            "raw_parsed":   input_data,
        },
        "output": {
            "confidence":   confidence,
            "raw_parsed":   output_data,
        },
        "computed_flags":  flags,
        "flag_reasons":    flag_reasons,
    }


# ─────────────────────────────────────────
# COMPLIANCE CLEANER
# ─────────────────────────────────────────

def _clean_coverage(raw_coverage: dict) -> list:
    result = []
    for clause, val in (raw_coverage or {}).items():
        pct = _compliance_pct(val)
        result.append({
            "clause":   clause,
            "coverage": val,
            "percent":  pct,
            "status":   "PASS" if pct == 100 else ("PARTIAL" if pct > 0 else "FAIL"),
        })
    return result


def _clean_violations(raw_violations: dict) -> list:
    result = []
    for description, count in (raw_violations or {}).items():
        result.append({
            "violation": description,
            "occurrences": count,
            "severity": "HIGH" if count >= 3 else ("MEDIUM" if count >= 2 else "LOW"),
        })
    return sorted(result, key=lambda x: -x["occurrences"])


# ─────────────────────────────────────────
# MAIN TRANSFORMER
# ─────────────────────────────────────────

def clean_report(raw: dict) -> dict:
    ss  = raw.get("session_summary", {})
    rb  = ss.get("risk_breakdown", {})
    rbi = raw.get("rbi_response_block", {})

    total    = ss.get("total_decisions", 0)
    flagged  = ss.get("flagged", 0)
    clean_ct = ss.get("clean", 0)
    score    = round(((total - flagged) / max(total, 1)) * 100)

    raw_decisions  = raw.get("flagged_decisions", [])
    clean_decisions = [_clean_decision(d, i) for i, d in enumerate(raw_decisions)]

    verdict_text = raw.get("verdict", "")
    verdict_status = (
        "NON_COMPLIANT" if "NON-COMPLIANT" in verdict_text
        else "PARTIAL" if "PARTIAL" in verdict_text
        else "MOSTLY_COMPLIANT" if "MOSTLY" in verdict_text
        else "COMPLIANT"
    )

    return {
        "_meta": {
            "cleaned_by":  "AgentBridge Report Cleaner v1.0",
            "cleaned_at":  datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "source_report_id": raw.get("report_id", ""),
        },
        "report": {
            "report_id":    raw.get("report_id", ""),
            "generated_at": _fmt_ts(raw.get("generated_at", "")),
            "agent_name":   raw.get("agent_name", "unknown"),
            "session_id":   raw.get("session_id", "session_fallback"),
        },
        "summary": {
            "total_decisions":   total,
            "flagged_decisions": flagged,
            "clean_decisions":   clean_ct,
            "compliance_score":  f"{score}%",
            "risk_breakdown": {
                "high":   rb.get("high", 0),
                "medium": rb.get("medium", 0),
                "low":    rb.get("low", 0),
            },
        },
        "verdict": {
            "status":  verdict_status,
            "message": verdict_text,
            "action_required": verdict_status in ("NON_COMPLIANT", "PARTIAL"),
        },
        "decisions": clean_decisions,
        "compliance": {
            "coverage":   _clean_coverage(raw.get("compliance_coverage", {})),
            "violations": _clean_violations(raw.get("violation_summary", {})),
        },
        "rbi_response_block": {
            "prepared_by":    rbi.get("prepared_by", "AgentBridge Audit System"),
            "framework":      rbi.get("framework", ""),
            "session_covered": rbi.get("session_covered", ""),
            "total_decisions_audited": rbi.get("total_agent_decisions_audited", total),
            "high_risk_decisions":    rbi.get("high_risk_decisions", rb.get("high", 0)),
            "compliance_verdict":     rbi.get("compliance_verdict", verdict_text),
            "generated_at":   _fmt_ts(rbi.get("generated_at", "")),
            "note":           rbi.get("note", ""),
        },
    }


def consolidate_batch_report(batch_results: List[dict]) -> dict:
    """
    Consolidates multiple pipeline results into a single Master Cleaned Report.
    Each result from batch_results is expected to contain a 'monitor' and 'worker' key.
    """
    all_decisions = []
    total_high = 0
    total_medium = 0
    total_low = 0
    
    # Aggregated coverage and violations
    agg_coverage = {}
    agg_violations = {}

    for res in batch_results:
        mon = res.get("monitor", {})
        # Flattened decision for the list
        all_decisions.append(mon)
        
        rl = mon.get("risk_level", "low")
        if rl == "high": total_high += 1
        elif rl == "medium": total_medium += 1
        else: total_low += 1

        # Sum up coverage counts if available
        # (Assuming mon has clause_status or similar, but cleaner expects a specific input)
        # We'll build a dummy 'raw' report object that clean_report can process
        pass

    # Build a raw structure that clean_report expects
    # Note: For a consolidated report, we skip some of the inner cleaning logic 
    # and build the final fields directly if we already have them.
    
    total = len(batch_results)
    flagged = total_high + total_medium
    score = round(((total - flagged) / max(total, 1)) * 100)
    
    verdict_status = "NON_COMPLIANT" if flagged > 0 else "COMPLIANT"
    verdict_msg = f"{verdict_status} — {flagged} of {total} decisions flagged."

    # Clean all decisions using our helper
    cleaned_decisions = [_clean_decision(d, i) for i, d in enumerate(all_decisions)]

    return {
        "_meta": {
            "cleaned_by":  "AgentBridge Report Cleaner v1.0",
            "cleaned_at":  datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "source_report_id": f"BATCH-{str(uuid.uuid4())[:8].upper()}",
        },
        "report": {
            "report_id":    f"BATCH-{str(uuid.uuid4())[:8].upper()}",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "agent_name":   "fintech_agent_v1",
            "session_id":   batch_results[0].get("monitor", {}).get("session_id", "batch_session") if batch_results else "none",
        },
        "summary": {
            "total_decisions":   total,
            "flagged_decisions": flagged,
            "clean_decisions":   total - flagged,
            "compliance_score":  f"{score}%",
            "risk_breakdown": {
                "high":   total_high,
                "medium": total_medium,
                "low":    total_low,
            },
        },
        "verdict": {
            "status":  verdict_status,
            "message": verdict_msg,
            "action_required": flagged > 0,
        },
        "decisions": cleaned_decisions,
        "compliance": {
            "coverage":   [], # Placeholder for batch
            "violations": [], # Placeholder for batch
        },
        "rbi_response_block": {
            "prepared_by":    "AgentBridge Audit System",
            "framework":      "RBI FREE-AI-aligned deterministic monitor",
            "session_covered": "batch_session",
            "total_decisions_audited": total,
            "high_risk_decisions":    total_high,
            "compliance_verdict":     verdict_msg,
            "generated_at":   datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "note":           f"Consolidated report of {total} scenarios.",
        },
    }

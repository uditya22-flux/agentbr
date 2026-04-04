"""
core_ai/report_cleaner.py

Transforms a raw AgentBridge report dict (as produced by generate_report)
into a normalized, cleaned, frontend-ready structure.

Changes applied:
  - decision_id: None / "None"  → auto-generated unique ID
  - reasoning: null             → "MISSING — VIOLATION" + reasoning_valid: false
  - input.raw / output.raw      → parsed from Python-style strings into real dicts
  - Extracts:  amount, kyc_verified, confidence as top-level fields per decision
  - Adds computed flags per decision:
        high_risk_without_kyc, low_confidence_approval,
        missing_reasoning, high_value_transaction
  - flag_reason pipe-string     → proper list
  - compliance_coverage entries → add percent + status (PASS/PARTIAL/FAIL)
  - violation_summary entries   → add severity (HIGH/MEDIUM/LOW)
  - verdict string              → add status enum + action_required bool
  - All timestamps              → normalized to "YYYY-MM-DD HH:MM:SS UTC"
  - Wraps output in _meta block (cleaned_at, source_report_id)
"""

import ast
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────
# LOW-LEVEL HELPERS
# ─────────────────────────────────────────────────────

def _parse_raw(value: Any) -> dict:
    """
    Parse Python-style dict strings like {'amount': 75000, 'kyc_verified': False}
    Also handles already-parsed dicts transparently.
    """
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        return ast.literal_eval(value)
    except Exception:
        return {"_unparsed": value}


def _parse_raw_field(container: Any) -> dict:
    """
    Given something like {"raw": "{'amount': 75000}"} or already a dict,
    return the parsed inner dict.
    """
    if isinstance(container, dict):
        raw = container.get("raw")
        if raw is not None:
            return _parse_raw(raw)
        return container
    return _parse_raw(container)


def _normalize_ts(ts: str) -> str:
    """ISO timestamp → 'YYYY-MM-DD HH:MM:SS UTC'"""
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(str(ts))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


def _gen_decision_id(index: int) -> str:
    short = str(uuid.uuid4())[:8].upper()
    return f"DEC-{short}-{str(index + 1).zfill(3)}"


def _compliance_pct(fraction_str: str) -> int:
    """'3/3 decisions' → 100"""
    try:
        parts = fraction_str.replace(" decisions", "").split("/")
        return round(int(parts[0]) / int(parts[1]) * 100)
    except Exception:
        return 0


def _verdict_status(verdict_text: str) -> str:
    t = verdict_text.upper()
    if "NON-COMPLIANT" in t:
        return "NON_COMPLIANT"
    if "PARTIAL" in t:
        return "PARTIAL"
    if "MOSTLY" in t:
        return "MOSTLY_COMPLIANT"
    return "COMPLIANT"


# ─────────────────────────────────────────────────────
# DECISION CLEANER
# ─────────────────────────────────────────────────────

def _clean_decision(raw: dict, index: int) -> dict:
    dec_id = raw.get("decision_id")
    if not dec_id or str(dec_id) in ("None", "null", ""):
        dec_id = _gen_decision_id(index)
        id_source = "auto_generated"
    else:
        id_source = "original"

    input_data  = _parse_raw_field(raw.get("input",  {}))
    output_data = _parse_raw_field(raw.get("output", {}))

    reasoning = raw.get("reasoning")
    if not reasoning:
        reasoning_clean = "MISSING — VIOLATION"
        reasoning_valid = False
    else:
        reasoning_clean = reasoning
        reasoning_valid = True

    amount     = input_data.get("amount")
    kyc        = input_data.get("kyc_verified")
    confidence = output_data.get("confidence")
    action     = raw.get("action_type", "unknown")
    risk       = raw.get("risk_level", "unknown")

    computed_flags: List[str] = []
    if risk == "high" and kyc is False:
        computed_flags.append("high_risk_without_kyc")
    if action == "approve" and confidence is not None and confidence < 0.75:
        computed_flags.append("low_confidence_approval")
    if not reasoning_valid:
        computed_flags.append("missing_reasoning")
    if amount is not None and amount >= 50000:
        computed_flags.append("high_value_transaction")

    raw_flag = raw.get("flag_reason") or ""
    flag_reasons = [f.strip() for f in raw_flag.split("|") if f.strip()]

    return {
        "decision_id":          dec_id,
        "decision_id_source":   id_source,
        "session_id":           raw.get("session_id") or None,
        "timestamp":            _normalize_ts(raw.get("timestamp", "")),
        "timestamp_raw":        raw.get("timestamp", ""),
        "action_type":          action,
        "risk_level":           risk,
        "reasoning":            reasoning_clean,
        "reasoning_valid":      reasoning_valid,
        "input": {
            "amount":       amount,
            "kyc_verified": kyc,
            "raw_parsed":   input_data,
        },
        "output": {
            "confidence":   confidence,
            "raw_parsed":   output_data,
        },
        "computed_flags":       computed_flags,
        "flag_reasons":         flag_reasons,
    }


# ─────────────────────────────────────────────────────
# COMPLIANCE CLEANER
# ─────────────────────────────────────────────────────

def _clean_coverage(raw_coverage: Dict[str, str]) -> List[dict]:
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


def _clean_violations(raw_violations: Dict[str, int]) -> List[dict]:
    result = []
    for description, count in (raw_violations or {}).items():
        result.append({
            "violation":   description,
            "occurrences": count,
            "severity":    "HIGH" if count >= 3 else ("MEDIUM" if count >= 2 else "LOW"),
        })
    return sorted(result, key=lambda x: -x["occurrences"])


# ─────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────

def clean_report(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts the raw dict returned by generate_report() and returns
    a cleaned, normalized version ready for frontend / download.

    Usage:
        from core_ai.report_cleaner import clean_report
        cleaned = clean_report(raw_report_dict)
    """
    ss  = raw.get("session_summary", {})
    rb  = ss.get("risk_breakdown", {})
    rbi = raw.get("rbi_response_block", {})

    total    = ss.get("total_decisions", 0)
    flagged  = ss.get("flagged", 0)
    clean_ct = ss.get("clean", 0)
    score    = round(((total - flagged) / max(total, 1)) * 100)

    verdict_text   = raw.get("verdict", "")
    verdict_status = _verdict_status(verdict_text)

    raw_decisions   = raw.get("flagged_decisions", [])
    clean_decisions = [_clean_decision(d, i) for i, d in enumerate(raw_decisions)]

    return {
        "compliance_percent": score,
        "overall_status": verdict_status,
        "_meta": {
            "cleaned_by":        "AgentBridge Report Cleaner v1.0",
            "cleaned_at":        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "source_report_id":  raw.get("report_id", ""),
        },
        "report": {
            "report_id":    raw.get("report_id", ""),
            "generated_at": _normalize_ts(raw.get("generated_at", "")),
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
            "status":          verdict_status,
            "message":         verdict_text,
            "action_required": verdict_status in ("NON_COMPLIANT", "PARTIAL"),
        },
        "decisions": clean_decisions,
        "compliance": {
            "coverage":   _clean_coverage(raw.get("compliance_coverage", {})),
            "violations": _clean_violations(raw.get("violation_summary", {})),
        },
        "rbi_response_block": {
            "prepared_by":               rbi.get("prepared_by", "AgentBridge Audit System"),
            "framework":                 rbi.get("framework", ""),
            "session_covered":           rbi.get("session_covered", ""),
            "total_decisions_audited":   rbi.get("total_agent_decisions_audited", total),
            "high_risk_decisions":       rbi.get("high_risk_decisions", rb.get("high", 0)),
            "compliance_verdict":        rbi.get("compliance_verdict", verdict_text),
            "generated_at":              _normalize_ts(rbi.get("generated_at", "")),
            "note":                      rbi.get("note", ""),
        },
    }

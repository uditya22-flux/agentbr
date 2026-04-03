"""
Behavioral drift detection.
Compares agent behavior this week vs last week.
No ML needed — pure statistics on your existing logs.
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta


def detect_drift(logs: List[Dict[str, Any]]) -> dict:
    """
    Splits logs into this week vs last week.
    Flags significant shifts in approval rate, flag rate, avg latency.
    """
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    this_week, last_week = [], []
    for log in logs:
        try:
            ts = log.get("created_at", "")
            dt = datetime.fromisoformat(str(ts).replace("Z", ""))
            if dt >= week_ago:
                this_week.append(log)
            elif dt >= two_weeks_ago:
                last_week.append(log)
        except Exception:
            continue

    if len(this_week) < 5 or len(last_week) < 5:
        return {"status": "insufficient_data", "message": "Need at least 5 logs per week to detect drift."}

    def stats(logs):
        total = len(logs)
        approved = sum(1 for l in logs if l.get("action_type", l.get("action")) == "approve")
        flagged = sum(1 for l in logs if l.get("flagged"))
        avg_latency = sum(l.get("latency_ms") or 0 for l in logs) / total
        return {
            "total": total,
            "approval_rate": round(approved / total * 100, 1),
            "flag_rate": round(flagged / total * 100, 1),
            "avg_latency_ms": round(avg_latency),
        }

    tw = stats(this_week)
    lw = stats(last_week)

    findings = []

    # Approval rate shift > 20%
    approval_delta = tw["approval_rate"] - lw["approval_rate"]
    if abs(approval_delta) > 20:
        direction = "increased" if approval_delta > 0 else "decreased"
        findings.append(f"Approval rate {direction} by {abs(approval_delta)}% (was {lw['approval_rate']}%, now {tw['approval_rate']}%).")

    # Flag rate spike > 15%
    flag_delta = tw["flag_rate"] - lw["flag_rate"]
    if flag_delta > 15:
        findings.append(f"Incident rate spiked by {flag_delta}% this week (was {lw['flag_rate']}%, now {tw['flag_rate']}%).")

    # Latency spike > 2x
    if lw["avg_latency_ms"] > 0 and tw["avg_latency_ms"] > lw["avg_latency_ms"] * 2:
        findings.append(f"Average latency doubled (was {lw['avg_latency_ms']}ms, now {tw['avg_latency_ms']}ms). Possible external dependency issue.")

    return {
        "status": "drift_detected" if findings else "stable",
        "this_week": tw,
        "last_week": lw,
        "findings": findings,
        "severity": "high" if len(findings) >= 2 else "medium" if findings else "low",
    }

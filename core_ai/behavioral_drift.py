from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import Counter

def detect_behavioral_drift(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    AI Feature 5 — Drift Analysis Engine
    Compares metrics between Week A (last 7 days) and Week B (7-14 days ago).
    Thresholds: Approval (0.20), Confidence (0.15), Violation (0.10).
    """
    if not logs or len(logs) < 10:
        return {"error": "Insufficient data"}

    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    week_a = []
    week_b = []

    for l in logs:
        try:
            ts = l.get("created_at", "")
            dt = datetime.fromisoformat(ts[:19].replace("Z", ""))
            if dt >= week_ago:
                week_a.append(l)
            elif dt >= two_weeks_ago:
                week_b.append(l)
        except: continue

    if not week_a or not week_b:
        return {"error": f"Insufficient week-over-week data (A: {len(week_a)}, B: {len(week_b)})"}

    def compute_metrics(logs_list):
        total = len(logs_list)
        app_count = sum(1 for l in logs_list if l.get("action_type") == "approve")
        conf_mean = sum(float(l.get("confidence", 0.0)) for l in logs_list) / total if total > 0 else 0
        violation_count = sum(1 for l in logs_list if l.get("flagged") == True)
        
        dist = Counter(l.get("action_type") for l in logs_list)
        return {
            "approval_rate": (app_count / total) if total > 0 else 0,
            "avg_confidence": conf_mean,
            "violation_rate": (violation_count / total) if total > 0 else 0,
            "distribution": {k: (v / total) for k, v in dist.items()}
        }

    stats_a = compute_metrics(week_a)
    stats_b = compute_metrics(week_b)

    drift_flags = []
    
    # Check threshold 0.20: Approval Rate
    if abs(stats_a["approval_rate"] - stats_b["approval_rate"]) > 0.20:
        drift_flags.append(f"Approval rate drifted by {round((stats_a['approval_rate'] - stats_b['approval_rate'])*100, 1)}%")

    # Check threshold 0.15: Average Confidence
    if abs(stats_a["avg_confidence"] - stats_b["avg_confidence"]) > 0.15:
        drift_flags.append(f"Confidence drifted by {round(stats_a['avg_confidence'] - stats_b['avg_confidence'], 2)}")

    # Check threshold 0.10: Violation Rate
    if abs(stats_a["violation_rate"] - stats_b["violation_rate"]) > 0.10:
        drift_flags.append(f"Violation frequency drifted by {round((stats_a['violation_rate'] - stats_b['violation_rate'])*100, 1)}%")

    return {
        "drifted": len(drift_flags) > 0,
        "drift_flags": drift_flags,
        "metrics_week_a": {
            "approval_rate": round(stats_a["approval_rate"], 2),
            "avg_confidence": round(stats_a["avg_confidence"], 2),
            "violation_rate": round(stats_a["violation_rate"], 2),
            "total_logs": len(week_a)
        },
        "metrics_week_b": {
            "approval_rate": round(stats_b["approval_rate"], 2),
            "avg_confidence": round(stats_b["avg_confidence"], 2),
            "violation_rate": round(stats_b["violation_rate"], 2),
            "total_logs": len(week_b)
        }
    }

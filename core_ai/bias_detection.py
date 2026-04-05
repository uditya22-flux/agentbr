import json
from typing import List, Dict, Any
from datetime import datetime, timedelta

def detect_bias_patterns(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    AI Feature 3 — Bias Detection (Consecutive Rejection Rule)
    Identifies 3+ consecutive rejects targeting the same entity within a 7-day window.
    """
    if not logs:
        return []

    # Sort logs chronologically to check consecutive pattern
    sorted_logs = sorted(logs, key=lambda x: x.get("created_at", ""))
    
    # Group by user_id
    user_history = {}
    for l in sorted_logs:
        uid = l.get("user_id", "unknown")
        if uid == "unknown": continue
        if uid not in user_history: user_history[uid] = []
        user_history[uid].append(l)

    bias_incidents = []
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    for uid, u_logs in user_history.items():
        # Check within a rolling 7-day window
        recent_logs = []
        for l in u_logs:
            try:
                dt = datetime.fromisoformat(l["created_at"].replace("Z", ""))
                if dt >= seven_days_ago:
                    recent_logs.append(l)
            except: continue
            
        consecutive_rejects = []
        for l in recent_logs:
            if l.get("action_type") == "reject":
                consecutive_rejects.append(l)
            else:
                # Chain broken by a non-reject action
                if len(consecutive_rejects) >= 3:
                     # Add to incidents
                     bias_incidents.append({
                         "entity": uid,
                         "count": len(consecutive_rejects),
                         "severity": "medium",
                         "description": f"Agent rejected {uid} {len(consecutive_rejects)} times — possible discriminatory pattern under RBI fairness guidelines",
                         "log_ids": [l["decision_id"] for l in consecutive_rejects]
                     })
                consecutive_rejects = []
        
        # Check if the last sequence in the window is >= 3
        if len(consecutive_rejects) >= 3:
             bias_incidents.append({
                 "entity": uid,
                 "count": len(consecutive_rejects),
                 "severity": "medium",
                 "description": f"Agent rejected {uid} {len(consecutive_rejects)} times — possible discriminatory pattern under RBI fairness guidelines",
                 "log_ids": [l["decision_id"] for l in consecutive_rejects]
             })

    return bias_incidents

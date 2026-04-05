from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import Counter

def detect_structuring_patterns(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    AI Feature 4 — Structuring Pattern AI
    For each session_id or agent_name, identify approve-action logs within 24h 
    where amount is between 40000 and 49999.
    Flag if 2 or more logs exist.
    """
    if not logs:
        return {"error": "No logs recorded"}

    # 1. Filter relevant logs (Approve actions + 40k-50k threshold)
    target_logs = []
    for l in logs:
        if l.get("action_type") == "approve":
            inputs = l.get("inputs", l.get("input", {}))
            amount = 0
            if isinstance(inputs, dict):
                amount = inputs.get("amount", inputs.get("loan_amount", 0))
            elif isinstance(inputs, str):
                try:
                    import json
                    parsed = json.loads(inputs)
                    amount = parsed.get("amount", parsed.get("loan_amount", 0))
                except: continue
                
            if 40000 <= amount <= 49999:
                target_logs.append(l)

    if not target_logs:
        return {"structuring_detected": False, "patterns": []}

    # 2. Group by session_id and agent_id
    session_groups = {}
    for l in target_logs:
        s_id = l.get("session_id", l.get("agent_id", "unknown"))
        if s_id not in session_groups: session_groups[s_id] = []
        session_groups[s_id].append(l)

    flags = []
    for s_id, s_logs in session_groups.items():
        # Check window: 24 hours
        # For each log, we see if it has a peer within 24h
        flagged_logs = []
        for l1 in s_logs:
            try:
                dt1 = datetime.fromisoformat(l1["created_at"].replace("Z", ""))
                peer_count = 0
                total_sum = 0
                for l2 in s_logs:
                    dt2 = datetime.fromisoformat(l2["created_at"].replace("Z", ""))
                    if abs((dt1 - dt2).total_seconds()) <= 86400: # 24h window
                        peer_count += 1
                        total_sum += 0 # We'll sum later
                
                if peer_count >= 2:
                    # Collect all in this 24h window for this specific flag
                    window_logs = [lx for lx in s_logs if abs((dt1 - datetime.fromisoformat(lx["created_at"].replace("Z", ""))).total_seconds()) <= 86400]
                    total_amount = sum(float(lx.get("inputs", lx.get("input", {})).get("amount", lx.get("inputs", lx.get("input", {})).get("loan_amount", 0))) for lx in window_logs if isinstance(lx.get("inputs", lx.get("input", {})), dict))
                    
                    flags.append({
                        "id": s_id,
                        "count": len(window_logs),
                        "total": total_amount,
                        "description": f"Possible ₹50K threshold structuring — {len(window_logs)} transactions totalling ₹{total_amount} detected within 24hrs",
                        "severity": "high"
                    })
                    break # We found a violation for this session
            except: continue

    return {
        "structuring_detected": len(flags) > 0,
        "patterns": flags
    }

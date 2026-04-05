from typing import List, Dict, Any
from collections import Counter

def detect_structural_gaps(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Scan all logs for systemic structural problems:
    Missing reasoning, identical outputs (copy-paste), action_type not in taxonomy, missing session_id.
    """
    if not logs:
        return {"error": "No logs available to scan"}

    anomalies = []
    
    # 1. Entire sessions with no reasoning fields
    no_reasoning = [l for l in logs if not l.get("reasoning") or l.get("reasoning") == ""]
    if no_reasoning:
        anomalies.append({
            "type": "Missing Reasoning",
            "count": len(no_reasoning),
            "affected_logs": [l.get("log_id") for l in no_reasoning[:10]],
            "severity": "high"
        })

    # 2. Batches of logs with identical outputs (copy-paste decisions)
    output_counts = Counter()
    for l in logs:
        output_counts[l.get("output", "")] += 1
        
    identical = [o for o, count in output_counts.items() if count > 5 and o != ""]
    if identical:
        anomalies.append({
            "type": "Copy-Paste Decisions",
            "count": sum(output_counts[o] for o in identical),
            "affected_logs": [l.get("log_id") for l in logs if l.get("output") in identical][:10],
            "severity": "medium"
        })

    # 3. Logs with empty or null input fields
    empty_input = [l for l in logs if not l.get("input") or l.get("input") == {}]
    if empty_input:
        anomalies.append({
            "type": "Empty Input",
            "count": len(empty_input),
            "affected_logs": [l.get("log_id") for l in empty_input][:10],
            "severity": "low"
        })

    # 4. Action type taxonomy check
    approved_taxonomy = ["approve", "reject", "flag", "escalate", "query", "review"]
    invalid_actions = [l for l in logs if l.get("action_type") not in approved_taxonomy]
    if invalid_actions:
        anomalies.append({
            "type": "Invalid Action Type",
            "count": len(invalid_actions),
            "affected_logs": [l.get("log_id") for l in invalid_actions][:10],
            "severity": "medium"
        })

    # 5. Missing session_id
    missing_session = [l for l in logs if not l.get("session_id")]
    if missing_session:
        anomalies.append({
            "type": "Missing Session ID",
            "count": len(missing_session),
            "affected_logs": [l.get("log_id") for l in missing_session][:10],
            "severity": "low"
        })

    return {
        "anomalies_found": len(anomalies),
        "anomaly_list": anomalies
    }

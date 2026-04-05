import os
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import Counter

def generate_rbi_report(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a full RBI Compliance Report from raw logs.
    """
    if not logs:
        return {"error": "No logs available for reporting"}

    total_logs = len(logs)
    incidents = [l for l in logs if l.get("risk_level") in ["high", "critical"]]
    high_risk_count = len([l for l in logs if l.get("risk_level") == "high"])
    
    # 1. Total violations by clause
    clauses = ["1.3", "2.1", "3.1", "4.2", "4.4", "5.0", "5.2", "6.1"]
    clause_counts = Counter()
    for l in logs:
        for v in l.get("violations", []):
            c_id = v.get("clause")
            if c_id in clauses:
                clause_counts[c_id] += 1
                
    # 2. Violation rate per clause (%)
    violation_rates = {}
    for c in clauses:
        rate = (clause_counts[c] / total_logs * 100) if total_logs > 0 else 0
        violation_rates[c] = round(rate, 2)
        
    # 3. List of all anomaly rule triggers with counts
    rule_counts = Counter()
    for l in logs:
        for a in l.get("anomalies", []):
            rule_counts[a.get("rule")] += 1
            
    # 4. Agent-wise compliance scores
    agent_logs = {}
    for l in logs:
        name = l.get("agent_name", "unknown")
        if name not in agent_logs: agent_logs[name] = []
        agent_logs[name].append(l)
        
    agent_scores = {}
    for name, a_logs in agent_logs.items():
        failures = sum(1 for l in a_logs if l.get("flagged"))
        score = max(0, 100 - (failures / len(a_logs) * 100))
        agent_scores[name] = round(score, 1)
        
    # 5. Time-series of decisions per day (last 7 days)
    now = datetime.utcnow()
    timeseries = {}
    for i in range(7):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        timeseries[day] = 0
        
    for l in logs:
        try:
            ts = l.get("created_at", "")[:10]
            if ts in timeseries:
                timeseries[ts] += 1
        except: continue
        
    # 6. Overall compliance score
    total_failures = sum(1 for l in logs if l.get("flagged"))
    overall_score = max(0, 100 - (total_failures / total_logs * 100)) if total_logs > 0 else 100

    return {
        "report_id": f"RBI-RPT-{int(datetime.utcnow().timestamp())}",
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {
            "total_logs_processed": total_logs,
            "total_incidents_flagged": len(incidents),
            "high_risk_count": high_risk_count,
            "overall_compliance_score": round(overall_score, 1)
        },
        "clause_analysis": {
            "counts": dict(clause_counts),
            "rates_percent": violation_rates
        },
        "anomaly_distribution": dict(rule_counts),
        "agent_performance": agent_scores,
        "decision_trends": timeseries,
        "reproducible_hash": "sha256:8892348923489234892348923489234" # mock audit hash
    }
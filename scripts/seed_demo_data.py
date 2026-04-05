from database import supabase
import uuid
import random
import hashlib
from datetime import datetime, timedelta, timezone

def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()

def seed():
    org_id = "demo_org_123"
    
    # 1. Ensure Org exists
    try:
        # organizations table might not have 4.0.0 defaults yet
        supabase.table("organizations").upsert({
            "id": org_id,
            "name": "Global Bank",
            "industry": "NBFC"
        }).execute()
        print(f"Ensured Org exists: {org_id}")
    except Exception as e:
        print(f"Org creation/check failed: {e}")

    # 2. Register Agent Personas
    personas = [
        {"id": "fraud-bot-id", "name": "Fraud Bot", "key": "demo_key_001", "type": "fraud-detection"},
        {"id": "loan-bot-id", "name": "Loan Bot", "key": "loan_key_999", "type": "loan-approval"}
    ]

    for p in personas:
        key_hash = hash_api_key(p["key"])
        
        try:
            supabase.table("agents").upsert({
                "id": p["id"],
                "org_id": org_id,
                "name": p["name"],
                "agent_type": p["type"],
                "api_key_hash": key_hash,
                "api_key_last_four": p["key"][-4:],
                "status": "active"
            }).execute()
            print(f"Registered Agent: {p['name']} with key {p['key']}")
        except Exception as e:
            print(f"Agent {p['name']} registration failed: {e}")

    # 3. Insert Historical Logs for Stats and Drift
    print("Generating historical logs for demo stats...")
    logs = []
    
    # Generate 14 days of logs
    for i in range(14):
        # Decisions per day: higher in the last 7 days to simulate growth
        is_this_week = i < 7
        count = random.randint(30, 45) if is_this_week else random.randint(20, 30)
        
        for _ in range(count):
            # Verdict Logic for Drift: 
            # Approval rate: 85% this week, 50% last week.
            if is_this_week:
                verdict = "approve" if random.random() < 0.85 else "reject"
            else:
                verdict = "approve" if random.random() < 0.52 else "reject"
            
            risk_level = "low" if verdict == "approve" else "high"
            
            ts = datetime.now(timezone.utc) - timedelta(days=i, hours=random.randint(0, 23), minutes=random.randint(0, 59))
            
            logs.append({
                "org_id": org_id,
                "agent_id": "fraud-bot-id",
                "decision_id": f"D-{str(uuid.uuid4())[:8]}",
                "session_id": f"S-{str(uuid.uuid4())[:8]}",
                "user_id": f"U-{random.randint(1000, 9999)}",
                "action_type": "transaction_check",
                "verdict": verdict,
                "risk_score": random.uniform(0.1, 0.4) if verdict == "approve" else random.uniform(0.7, 1.0),
                "risk_level": risk_level,
                "policy_violations": ["RBI_3.1_EXPLAINABILITY_FAILED"] if verdict == "reject" else [],
                "compliance_violations": [],
                "inputs": {"amount": random.randint(1000, 500000), "kyc": True},
                "output": '{"decision": "approve", "confidence": 0.95}',
                "reasoning": "Automated transaction compliance review.",
                "confidence": 0.95,
                "log_hash": str(uuid.uuid4()),
                "created_at": ts.isoformat(),
                "flagged": verdict == "reject"
            })

    # Batch insert (200 at a time)
    for chunk_start in range(0, len(logs), 200):
        chunk = logs[chunk_start : chunk_start + 200]
        try:
            supabase.table("audit_logs").insert(chunk).execute()
        except Exception as e:
            print(f"Logging chunk failed: {e}")

    print(f"SUCCESS: Seeding Complete: {len(logs)} logs inserted for {org_id}")

if __name__ == "__main__":
    seed()

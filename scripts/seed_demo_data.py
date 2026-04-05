from database import supabase
from utils.auth_utils import hash_api_key
import uuid

def seed():
    org_id = "demo_org_123"
    
    # Check if Org exists or Create
    try:
        supabase.table("organizations").insert({
            "id": org_id,
            "name": "Demo Corporation",
            "industry": "FinTech"
        }).execute()
        print(f"Created Org: {org_id}")
    except Exception as e:
        print(f"Org might exist: {e}")

    # Agent Personas
    personas = [
        {"id": "fraud-bot-id", "name": "Fraud Bot", "key": "demo_key_001", "type": "fraud-detection"},
        {"id": "loan-bot-id", "name": "Loan Bot", "key": "loan_key_999", "type": "loan-approval"}
    ]

    for p in personas:
        key_hash = hash_api_key(p["key"])
        
        try:
            supabase.table("agents").insert({
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

if __name__ == "__main__":
    seed()

"""
AgentBridge v5 — Loan Approval Agent
This agent evaluates loan applications and sends decisions to the AgentBridge Gateway.
"""
import httpx
import argparse
import uuid
import time
import random

parser = argparse.ArgumentParser()
parser.add_argument("--api_key", default="loan_key_999")
parser.add_argument("--backend", default="http://127.0.0.1:8000") # Use your remote URL if hosted
args = parser.parse_args()

HEADERS = {"X-API-Key": args.api_key, "Content-Type": "application/json"}
SESSION_ID = str(uuid.uuid4())

def decide_loan(amount, credit_score, income, reasoning, expected_fraud=False):
    # The AI computes confidence based on criteria
    confidence = 0.95 if credit_score > 700 else 0.60
    
    # We construct the payload exactly how AgentBridge expects it
    payload = {
        "session_id": SESSION_ID,
        "agent_id": "loan-approval-bot", # <--- Notice this is a new agent!
        "user_id": f"applicant_{uuid.uuid4().hex[:8]}",
        "action_type": "loan",
        "input": {
            "loan_amount": amount,
            "credit_score": credit_score,
            "annual_income": income,
            "kyc_verified": True
        },
        "reasoning": reasoning,
        "confidence": confidence,
        "domain": "lending",
    }
    
    print(f"\n📝 Analyzing Loan for applicant ({amount} INR)...")
    
    # The Agent must ask AgentBridge for permission before giving the loan!
    try:
        r = httpx.post(f"{args.backend}/decide", json=payload, headers=HEADERS, timeout=15)
        data = r.json()
        print(f"  → AgentBridge Verdict: {data.get('verdict')}")
        if data.get('policy_violations'):
            print(f"  → Violation: {data['policy_violations'][0]}")
    except Exception as e:
        print(f"  → Server Error: {e}")
        
    time.sleep(1)

print(f"\n🏦 Starting Loan Approval Agent")
print(f"   API Key: {args.api_key}")
print(f"   Session: {SESSION_ID}\n")

# Provide a great, low risk loan scenario
decide_loan(
    amount=50000, 
    credit_score=780, 
    income=1200000, 
    reasoning="Applicant has excellent credit history and high income. Approving loan securely."
)

# Provide a highly risky loan scenario
decide_loan(
    amount=900000, 
    credit_score=520, 
    income=200000, 
    reasoning="Applicant has very low credit but we are approving the loan anyway because of a special override.",
    expected_fraud=True
)

# Provide a loan with terrible reasoning (AgentBridge will catch this!)
decide_loan(
    amount=10000, 
    credit_score=600, 
    income=50000, 
    reasoning="idk giving them money"
)

print("\n✅ Loan Agent finished. Check the dashboard to see logs from 'loan-approval-bot'!")

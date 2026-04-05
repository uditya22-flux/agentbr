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

# --- Scenarios based on random generation ---
applicants = [
    {"name": "Alice Shah", "amount": 45000, "score": 750, "income": 1500000, "reason": "Stable employment, high credit score."},
    {"name": "Bob Gupta", "amount": 800000, "score": 580, "income": 400000, "reason": "High debt-to-income ratio, low credit score."},
    {"name": "Charlie Rai", "amount": 12000, "score": 680, "income": 300000, "reason": "Small loan, moderate credit."},
    {"name": "Deepa Singh", "amount": 950000, "score": 820, "income": 2500000, "reason": "Premium customer, high value approval."},
    {"name": "Esha Verma", "amount": 50000, "score": 450, "income": 250000, "reason": "Multiple recent defaults, credit score bottomed out."}
]

for app in applicants:
    # Add some randomness to make it look like a live stream
    time.sleep(random.uniform(0.5, 1.5))
    
    # Introduce variability in reasoning and confidence
    conf = 0.9 if app['score'] > 700 else 0.4
    if "Small loan" in app['reason']:
        conf = 0.82
        
    decide_loan(
        amount=app['amount'],
        credit_score=app['score'],
        income=app['income'],
        reasoning=app['reason']
    )

print("\n🚀 Batch generation complete. Generating one 'Bad Reasoning' log to test compliance...")
decide_loan(15000, 600, 50000, "no reason really just feel like it")

print("\n✅ Loan Agent finished. Check the dashboard to see logs from 'loan-approval-bot'!")

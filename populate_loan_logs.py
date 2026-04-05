import requests
import json
import time

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--backend", default="http://127.0.0.1:10000")
parser.add_argument("--api_key", default="loan_key_999")
args = parser.parse_args()

# SETTINGS
BACKEND_URL = args.backend
LOAN_KEY = args.api_key

# TEST CASES: Diverse loan applications
test_cases = [
    {
        "name": "Excellent Credit Approval",
        "data": {
            "api_key": LOAN_KEY,
            "agent_id": "loanbot",
            "agent_name": "loanbot",
            "action_type": "loan",
            "reasoning": "Applicant has an exceptional credit score of 820. Stable employment history (8 years) and low DTI ratio of 0.15. Meets all Tier-1 approval criteria.",
            "confidence": 0.98,
            "input": {
                "amount": 750000,
                "credit_score": 820,
                "annual_income": 1800000,
                "dti_ratio": 0.15,
                "employment_years": 8,
                "kyc_verified": True,
                "loan_type": "home"
            },
            "user_id": "user_pro_001",
            "session_id": "sess_888"
        }
    },
    {
        "name": "Sub-Prime Rejection",
        "data": {
            "api_key": LOAN_KEY,
            "agent_id": "loanbot",
            "agent_name": "loanbot",
            "action_type": "reject",
            "reasoning": "Application rejected due to sub-prime credit score (450). Fails the minimum bank threshold of 650 for automotive financing.",
            "confidence": 0.92,
            "input": {
                "amount": 350000,
                "credit_score": 450,
                "annual_income": 500000,
                "dti_ratio": 0.35,
                "employment_years": 1,
                "kyc_verified": True,
                "loan_type": "auto"
            },
            "user_id": "user_low_002",
            "session_id": "sess_444"
        }
    },
    {
        "name": "High DTI Risk Flag",
        "data": {
            "api_key": LOAN_KEY,
            "agent_id": "loanbot",
            "agent_name": "loanbot",
            "action_type": "reject",
            "reasoning": "Debt-to-Income ratio (0.58) exceeds the regulated limit of 0.40. Suggesting manual review or co-applicant requirement.",
            "confidence": 0.88,
            "input": {
                "amount": 1000000,
                "credit_score": 710,
                "annual_income": 800000,
                "dti_ratio": 0.58,
                "employment_years": 4,
                "kyc_verified": True,
                "loan_type": "business"
            },
            "user_id": "user_risk_003",
            "session_id": "sess_111"
        }
    },
    {
        "name": "KYC Violation - High Value",
        "data": {
            "api_key": LOAN_KEY,
            "agent_id": "loanbot",
            "agent_name": "loanbot",
            "action_type": "flag",
            "reasoning": "Request for high-value personal loan (₹1.2M) without valid KYC verification. Mandatory FLAG raised per RBI Clause 3.1.",
            "confidence": 0.85,
            "input": {
                "amount": 1200000,
                "credit_score": 750,
                "annual_income": 2500000,
                "dti_ratio": 0.22,
                "employment_years": 12,
                "kyc_verified": False,
                "loan_type": "personal"
            },
            "user_id": "user_unv_004",
            "session_id": "sess_999"
        }
    },
    {
        "name": "New Professional - Standard Approval",
        "data": {
            "api_key": LOAN_KEY,
            "agent_id": "loanbot",
            "agent_name": "loanbot",
            "action_type": "loan",
            "reasoning": "New professional with good initial credit (680). DTI is highly favorable (0.12). Approved with standard interest rates.",
            "confidence": 0.94,
            "input": {
                "amount": 150000,
                "credit_score": 680,
                "annual_income": 900000,
                "dti_ratio": 0.12,
                "employment_years": 2,
                "kyc_verified": True,
                "loan_type": "personal"
            },
            "user_id": "user_new_005",
            "session_id": "sess_222"
        }
  }
]

print(f"🚀 Injecting {len(test_cases)} varied loan logs into {BACKEND_URL}...")

for tc in test_cases:
    try:
        print(f"Sending: {tc['name']}...", end=" ", flush=True)
        resp = requests.post(
            f"{BACKEND_URL}/decide", 
            json=tc['data'],
            headers={"X-API-Key": LOAN_KEY}
        )
        if resp.status_code == 200:
            print("DONE ✓")
        else:
            print(f"FAILED (Status {resp.status_code})")
        time.sleep(0.5) # Prevent hammering
    except Exception as e:
        print(f"ERROR: {e}")

print("\n✨ Finished! Refresh your dashboard with the 'loan_key_999' key to see the logs.")

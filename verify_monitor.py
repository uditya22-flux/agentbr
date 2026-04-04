"""Deterministic monitor tests (no API keys). Run: python verify_monitor.py"""
from core_ai.pipeline import process


def _base(**kwargs):
    d = {
        "decision_id": "d1",
        "session_id": "sess_test",
        "agent_name": "test_agent",
        "action_type": "loan",
        "reasoning": "Qualified borrower; documentation complete.",
        "input": {"amount": 120000, "kyc_verified": True},
        "output": {"decision": "approve loan", "confidence": 0.91},
    }
    d.update(kwargs)
    return d


def main():
    # 1 — Clean loan ₹1.2L + KYC
    dao = process(_base())
    assert dao.risk_level == "low", f"expected low, got {dao.risk_level}"
    assert dao.compliance_percent == 100
    print("PASS: clean loan -> LOW")

    # 2 — ₹85k transfer, no KYC
    dao2 = process(
        _base(
            action_type="transfer",
            reasoning="Urgent payout",
            input={"amount": 85000, "kyc_verified": False},
            output={"decision": "transfer", "confidence": 0.88},
        )
    )
    assert dao2.risk_level == "high", f"expected high, got {dao2.risk_level}"
    print("PASS: 85k transfer no KYC -> HIGH")

    # 3 — Missing reasoning
    dao3 = process(
        _base(
            reasoning="",
            input={"amount": 1000, "kyc_verified": True},
        )
    )
    assert dao3.risk_level == "high", f"expected high, got {dao3.risk_level}"
    print("PASS: missing reasoning -> HIGH")

    print("\nAll monitor tests passed.")


if __name__ == "__main__":
    main()

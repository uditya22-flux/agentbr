from core_ai.dao import DAO
from typing import List

# Clause keys for clause_status map (stable IDs)
CLAUSE_IDS = {
    "3.1": "Clause 3.1 — Explainability (reasoning required)",
    "4.4": "Clause 4.4 — Session traceability",
    "5.2": "Clause 5.2 — Valid action_type",
    "6.1": "Clause 6.1 — KYC required",
}

CLAUSES = {
    "has_reasoning":   CLAUSE_IDS["3.1"],
    "has_session_id":  CLAUSE_IDS["4.4"],
    "has_action_type": CLAUSE_IDS["5.2"],
    "has_kyc":         CLAUSE_IDS["6.1"],
}

VIOLATIONS = {
    "missing_reasoning":   "VIOLATION — Clause 3.1: No reasoning logged.",
    "missing_session_id":  "VIOLATION — Clause 4.4: No session ID.",
    "unknown_action_type": "VIOLATION — Clause 5.2: action_type not in allowed set.",
    "missing_kyc":         "VIOLATION — Clause 6.1: KYC required for this action.",
}


def _needs_kyc(dao: DAO) -> bool:
    return dao.action_type in ("approve", "loan", "transfer")


def map_compliance(dao: DAO) -> DAO:
    tags: List[str] = []
    violations: List[str] = []
    clause_status = {}

    # 3.1
    if dao.reasoning and str(dao.reasoning).strip():
        tags.append(CLAUSES["has_reasoning"])
        clause_status[CLAUSE_IDS["3.1"]] = "PASS"
    else:
        violations.append(VIOLATIONS["missing_reasoning"])
        clause_status[CLAUSE_IDS["3.1"]] = "FAIL"

    # 4.4
    if dao.session_id and str(dao.session_id).strip():
        tags.append(CLAUSES["has_session_id"])
        clause_status[CLAUSE_IDS["4.4"]] = "PASS"
    else:
        violations.append(VIOLATIONS["missing_session_id"])
        clause_status[CLAUSE_IDS["4.4"]] = "FAIL"

    # 5.2
    if dao.action_type and dao.action_type != "unknown":
        tags.append(CLAUSES["has_action_type"])
        clause_status[CLAUSE_IDS["5.2"]] = "PASS"
    else:
        violations.append(VIOLATIONS["unknown_action_type"])
        clause_status[CLAUSE_IDS["5.2"]] = "FAIL"

    # 6.1 — KYC for approve / loan / transfer
    if _needs_kyc(dao):
        kyc = dao.input.get("kyc_verified") or dao.input.get("kyc")
        if kyc:
            tags.append(CLAUSES["has_kyc"])
            clause_status[CLAUSE_IDS["6.1"]] = "PASS"
        else:
            violations.append(VIOLATIONS["missing_kyc"])
            clause_status[CLAUSE_IDS["6.1"]] = "FAIL"
    else:
        clause_status[CLAUSE_IDS["6.1"]] = "N/A"

    dao.compliance_tags = tags
    dao.compliance_violations = violations
    dao.clause_status = clause_status

    checked = len([k for k, v in clause_status.items() if v != "N/A"])
    passed = sum(1 for v in clause_status.values() if v == "PASS")
    dao.compliance_percent = int(round(100 * passed / checked)) if checked > 0 else 100

    return dao

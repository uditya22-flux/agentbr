"""
validation/validator.py
Empty reasoning is allowed — deterministic monitor flags Clause 3.1.
"""
from typing import Tuple, Optional
from models.schemas import DecisionRequest, KNOWN_GATEWAY_ACTIONS

_STR_REQUIRED = ("session_id", "agent_id", "user_id", "action_type", "api_key")


def validate(raw: dict) -> Tuple[bool, Optional[DecisionRequest], Optional[str]]:
    missing = []
    for f in _STR_REQUIRED:
        v = raw.get(f)
        if v is None or (isinstance(v, str) and not v.strip()):
            missing.append(f)
    if "input" not in raw or raw.get("input") is None:
        missing.append("input")
    if "confidence" not in raw or raw.get("confidence") is None:
        missing.append("confidence")

    if missing:
        return False, None, f"Missing required fields: {missing}"

    if raw.get("action_type") not in KNOWN_GATEWAY_ACTIONS:
        return False, None, f"Unknown action_type '{raw.get('action_type')}'. Must be one of {sorted(KNOWN_GATEWAY_ACTIONS)}"

    try:
        confidence = float(raw.get("confidence"))
        if not (0.0 <= confidence <= 1.0):
            raise ValueError
    except (TypeError, ValueError):
        return False, None, "confidence must be a float between 0.0 and 1.0"

    if not isinstance(raw.get("input"), dict):
        return False, None, "input must be a JSON object"

    data = dict(raw)
    if "reasoning" not in data or data.get("reasoning") is None:
        data["reasoning"] = ""

    try:
        request = DecisionRequest(**data)
        return True, request, None
    except Exception as e:
        return False, None, str(e)

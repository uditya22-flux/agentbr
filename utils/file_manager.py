"""
Local JSON audit storage: logs, incidents, reports.
Complements Supabase — required for regulator-grade file exports.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

_STORAGE = Path(__file__).resolve().parent.parent / "storage"
_LOGS = _STORAGE / "logs"
_INCIDENTS = _STORAGE / "incidents"
_REPORTS = _STORAGE / "reports"


def _safe_session_id(session_id: str) -> str:
    s = (session_id or "unknown").strip()
    if not re.match(r"^[a-zA-Z0-9_.-]+$", s):
        s = re.sub(r"[^a-zA-Z0-9_.-]", "_", s)[:120] or "unknown"
    return s


def ensure_dirs() -> None:
    _LOGS.mkdir(parents=True, exist_ok=True)
    _INCIDENTS.mkdir(parents=True, exist_ok=True)
    _REPORTS.mkdir(parents=True, exist_ok=True)


def append_session_log(session_id: str, record: Dict[str, Any]) -> Path:
    """Append one unified audit record to storage/logs/{session_id}.json"""
    ensure_dirs()
    sid = _safe_session_id(session_id)
    path = _LOGS / f"{sid}.json"
    data: Dict[str, Any] = {"session_id": sid, "events": []}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if "events" not in data:
                data["events"] = []
        except Exception:
            data = {"session_id": sid, "events": []}
    data["events"].append(record)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def write_incident(session_id: str, record: Dict[str, Any]) -> Path:
    """HIGH risk → storage/incidents/{session_id}.json"""
    ensure_dirs()
    sid = _safe_session_id(session_id)
    path = _INCIDENTS / f"{sid}.json"
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return path


def write_session_report(session_id: str, report: Dict[str, Any]) -> Path:
    """storage/reports/{session_id}_report.json"""
    ensure_dirs()
    sid = _safe_session_id(session_id)
    path = _REPORTS / f"{sid}_report.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return path


def read_session_log(session_id: str) -> Dict[str, Any] | None:
    sid = _safe_session_id(session_id)
    path = _LOGS / f"{sid}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_session_report(session_id: str) -> Dict[str, Any] | None:
    sid = _safe_session_id(session_id)
    path = _REPORTS / f"{sid}_report.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

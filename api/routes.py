"""
Disk-backed audit downloads (complements Supabase).
Requires same API key auth as other routes (middleware).
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from utils.file_manager import read_session_log, read_session_report

router = APIRouter()


@router.get("/download/{session_id}")
async def download_session_audit(session_id: str, api_key: str):
    """Full session log JSON from storage/logs/{session_id}.json"""
    data = read_session_log(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"detail": "Session log not found"})
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": f'attachment; filename="agentbridge-audit-{session_id}.json"',
        },
    )


@router.get("/download/report/{session_id}")
async def download_session_report_file(session_id: str, api_key: str):
    """Report JSON from storage/reports/{session_id}_report.json"""
    data = read_session_report(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"detail": "Report not found"})
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": f'attachment; filename="agentbridge-report-{session_id}.json"',
        },
    )

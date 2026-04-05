from fastapi import APIRouter, Request, HTTPException
from database import supabase
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/settings", tags=["Organization Settings"])

class CompanyUpdate(BaseModel):
    name: str
    industry: str
    admin_email: Optional[str] = None

@router.get("/profile")
async def get_profile(request: Request):
    org_id = getattr(request.state, "org_id", None)
    res = supabase.table("organizations").select("*").eq("id", org_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    return res.data[0]

@router.post("/profile")
async def update_profile(request: Request, req: CompanyUpdate):
    org_id = getattr(request.state, "org_id", None)
    supabase.table("organizations")\
        .update({"name": req.name, "industry": req.industry})\
        .eq("id", org_id)\
        .execute()
    return {"status": "updated"}

@router.get("/team")
async def get_team_members(request: Request):
    org_id = getattr(request.state, "org_id", None)
    res = supabase.table("users").select("id, email, role, created_at").eq("org_id", org_id).execute()
    return res.data

@router.get("/billing")
async def get_billing_status(request: Request):
    org_id = getattr(request.state, "org_id", None)
    res = supabase.table("organizations").select("plan, api_limit").eq("id", org_id).execute()
    # Placeholder usage calculation
    usage_res = supabase.table("audit_logs").select("*", count="exact").eq("org_id", org_id).execute()
    usage_count = usage_res.count if hasattr(usage_res, "count") else len(usage_res.data)
    
    return {
        "current_plan": res.data[0]["plan"],
        "api_limit": res.data[0]["api_limit"],
        "usage_this_month": usage_count
    }

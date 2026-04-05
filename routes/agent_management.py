from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from database import supabase
from utils.auth_utils import generate_api_key, hash_api_key
from typing import Optional

router = APIRouter(prefix="/api/agents", tags=["Agent Management"])

class AgentCreateRequest(BaseModel):
    name: str
    agent_type: str # fraud-detection | loan-approval | KYC | other
    description: Optional[str] = None

@router.get("/")
async def list_agents(request: Request):
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    res = supabase.table("agents")\
        .select("id, created_at, name, agent_type, description, status, total_logs")\
        .eq("org_id", org_id)\
        .execute()
    
    return res.data

@router.post("/register")
async def register_agent(request: Request, req: AgentCreateRequest):
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 1. Generate API Key
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)

    # 2. Insert into DB
    res = supabase.table("agents")\
        .insert({
            "org_id": org_id,
            "name": req.name,
            "agent_type": req.agent_type,
            "description": req.description,
            "api_key_hash": key_hash,
            "status": "active"
        })\
        .execute()
    
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to register agent")
    
    # 3. Return raw key ONCE
    return {
        "status": "success",
        "agent_id": res.data[0]["id"],
        "api_key": raw_key # RAW KEY ONLY SHOWN ONCE
    }

@router.post("/{agent_id}/regenerate-key")
async def regenerate_key(request: Request, agent_id: str):
    org_id = getattr(request.state, "org_id", None)
    
    # Verify ownership
    agent_res = supabase.table("agents")\
        .select("id")\
        .eq("id", agent_id)\
        .eq("org_id", org_id)\
        .execute()
    
    if not agent_res.data:
        raise HTTPException(status_code=404, detail="Agent not found")

    new_raw_key = generate_api_key()
    new_hash = hash_api_key(new_raw_key)

    supabase.table("agents")\
        .update({"api_key_hash": new_hash})\
        .eq("id", agent_id)\
        .execute()
    
    return {"api_key": new_raw_key}

@router.post("/{agent_id}/deactivate")
async def deactivate_agent(request: Request, agent_id: str):
    org_id = getattr(request.state, "org_id", None)
    supabase.table("agents")\
        .update({"status": "inactive"})\
        .eq("id", agent_id)\
        .eq("org_id", org_id)\
        .execute()
    return {"status": "deactivated"}

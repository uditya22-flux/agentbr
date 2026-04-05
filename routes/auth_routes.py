from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from database import supabase
from utils.auth_utils import get_password_hash, verify_password, create_access_token
from typing import Optional

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class SignupRequest(BaseModel):
    company_name: str
    admin_email: EmailStr
    password: str
    industry: str # fintech | bank | NBFC | other

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/signup")
async def signup(req: SignupRequest):
    # 1. Create Organization
    org_res = supabase.table("organizations")\
        .insert({
            "name": req.company_name,
            "industry": req.industry
        })\
        .execute()
    
    if not org_res.data:
        raise HTTPException(status_code=500, detail="Failed to create organization")
    
    org_id = org_res.data[0]["id"]

    # 2. Create User
    pwd_hash = get_password_hash(req.password)
    user_res = supabase.table("users")\
        .insert({
            "org_id": org_id,
            "email": req.admin_email,
            "password_hash": pwd_hash,
            "role": "admin"
        })\
        .execute()
    
    if not user_res.data:
        # Rollback org? (For MVP, we just fail)
        raise HTTPException(status_code=500, detail="Failed to create admin user")
    
    return {"status": "success", "org_id": org_id, "user_id": user_res.data[0]["id"]}

@router.post("/login")
async def login(req: LoginRequest):
    # 1. Find User
    user_res = supabase.table("users")\
        .select("id, org_id, password_hash")\
        .eq("email", req.email)\
        .limit(1)\
        .execute()
    
    if not user_res.data:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    user = user_res.data[0]
    
    # 2. Verify Password
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # 3. Create JWT
    token = create_access_token(data={"sub": user["id"], "org_id": user["org_id"]})
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "org_id": user["org_id"]
    }

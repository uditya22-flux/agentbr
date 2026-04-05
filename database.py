import json
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
LOCAL_FILE = "audit_trail.json"

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Failed to initialize Supabase: {e}")

def get_last_log_hash():
    """Retrieves the most recent log_hash to chain the next transaction."""
    if supabase:
        try:
            response = supabase.table("audit_logs").select("log_hash").order("created_at", desc=True).limit(1).execute()
            if response.data:
                return response.data[0]["log_hash"]
        except: pass
    return "00000000000000000000000000000000"

def verify_api_key(api_key: str) -> bool:
    """Checks if the provided API Key is valid and active in Supabase."""
    if not api_key: return False
    if api_key == "test123": return True # Development bypass
    
    if supabase:
        try:
            response = supabase.table("api_keys").select("*").eq("api_key", api_key).eq("active", True).execute()
            return len(response.data) > 0
        except Exception as e:
            print(f"API Key verification failed: {e}")
            return False
    return False

def get_all_logs():
    if supabase:
        try:
            # Match Gateway v5 column ordering
            response = supabase.table("audit_logs").select("*").order("created_at", desc=True).execute()
            return response.data
        except Exception:
            pass
    if os.path.exists(LOCAL_FILE):
        with open(LOCAL_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_log(log_data: dict):
    if supabase:
        try:
            # Match Gateway v5 schema insertion
            supabase.table("audit_logs").insert(log_data).execute()
        except Exception as e:
            print(f"Supabase write failed: {e}")
            
    # Local fallback
    logs = get_all_logs()
    logs.insert(0, log_data)
    with open(LOCAL_FILE, "w") as f:
        json.dump(logs, f, indent=2)

def get_logs_by_session(session_id: str):
    return [log for log in get_all_logs() if log.get('session_id') == session_id]

def get_high_critical_logs():
    return [log for log in get_all_logs() if log.get('risk_level') in ['high', 'critical']]

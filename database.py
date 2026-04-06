import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

_client = None


def get_supabase():
    """Lazy client so the app can boot (e.g. Render) before env is fully wired."""
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must be set in the environment "
                "(Render: Dashboard → your service → Environment)."
            )
        _client = create_client(url, key)
    return _client


class _SupabaseProxy:
    __slots__ = ()

    def __getattr__(self, name):
        return getattr(get_supabase(), name)


supabase = _SupabaseProxy()

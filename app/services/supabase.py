import os

from supabase import create_client

_public_client = None
_admin_client = None


def init_supabase():
    global _public_client, _admin_client
    if _public_client and _admin_client:
        return
    url = os.environ.get("SUPABASE_URL")
    anon_key = os.environ.get("SUPABASE_ANON_KEY")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not anon_key:
        raise RuntimeError("Falta SUPABASE_URL o SUPABASE_ANON_KEY")
    _public_client = create_client(url, anon_key)
    if service_key:
        _admin_client = create_client(url, service_key)
    else:
        _admin_client = _public_client


def get_public_client():
    return _public_client


def get_admin_client():
    return _admin_client

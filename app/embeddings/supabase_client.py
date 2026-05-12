from supabase.client import Client, create_client
from app.config import settings

def get_supabase_client() -> Client:
    return create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_service_key,
    )

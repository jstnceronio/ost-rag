from app.embeddings.supabase_client import get_supabase_client
from app.config import settings

def test():
    try:
        client = get_supabase_client()
        # This just checks if we can connect and reach the 'documents' table
        response = client.table(settings.supabase_table_name).select("*", count="exact").limit(1).execute()
        print("✅ Successfully connected to Supabase!")
        print(f"Connection URL: {settings.supabase_url}")
        print(f"Table name: {settings.supabase_table_name}")
    except Exception as e:
        print("❌ Connection failed!")
        print(e)

if __name__ == "__main__":
    test()

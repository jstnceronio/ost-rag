from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # OpenAI Settings
    openai_model: str = "gpt-4.1"
    openai_api_key: str

    # Confluence Settings
    confluence_api_key: str
    confluence_base_url: str

    # Embedding Stuff
    embedding_model: str = "text-embedding-3-small"
    vector_store_provider: str = "supabase"
    faiss_index_path: str = "./data/faiss_index"

    # Supabase
    supabase_url: str
    supabase_service_key: str
    supabase_table_name: str

    class Config:
        env_file = ".env"

settings = Settings()
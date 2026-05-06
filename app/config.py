from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

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
    supabase_url: str | None = None
    supabase_service_key: str | None = None
    supabase_table_name: str | None = None

    # API Settings
    api_key: str
    allowed_cors_origins: str = "*"


settings = Settings()

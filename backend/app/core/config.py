from pydantic_settings import BaseSettings
from typing import Optional
import os


# Detectar se está no Railway (container Docker)
def get_default_storage_path():
    if os.path.exists('/app'):
        return '/app/data'
    return '../data'


class Settings(BaseSettings):
    DATABASE_URL: str
    STORAGE_PATH: str = get_default_storage_path()
    SEARCH_PROVIDER: str = "serpapi"
    SERPAPI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-opus-4-5-20251101"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    AI_PROVIDER: str = "anthropic"  # "anthropic" ou "openai"
    SERPAPI_ENGINE: str = "google_shopping"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str
    STORAGE_PATH: str = "../data"
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

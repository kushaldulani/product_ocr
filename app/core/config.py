from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Required
    google_api_key: str

    # Optional with defaults
    database_api_url: str = "http://35.182.153.121:5001/api/products"
    gemini_model: str = "gemini-2.5-flash"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    max_file_size: int = 10485760  # 10MB
    database_timeout: int = 30

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
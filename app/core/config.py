import os
from pydantic_settings import BaseSettings


PG_DSN = os.getenv("PG_DSN", "postgresql://postgres:postgres@localhost:5432/kadracoon")
TMDB_SYNC_URL = os.getenv("TMDB_SYNC_URL", "http://tmdb-sync:8000")
TMDB_CDN_BASE = os.getenv("TMDB_CDN_BASE", "https://image.tmdb.org/t/p")
TMDB_CDN_SIZE = os.getenv("TMDB_CDN_SIZE", "w500")  # например


class Settings(BaseSettings):
    DATABASE_URL: str
    MONGO_URI: str
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change_me")
    JWT_EXP_MINUTES: int = 60

    class Config:
        env_file = ".env"


settings = Settings()

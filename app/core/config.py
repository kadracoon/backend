import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    MONGO_URI: str
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change_me")
    JWT_EXP_MINUTES: int = 60

    class Config:
        env_file = ".env"


settings = Settings()

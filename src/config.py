from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, SecretStr
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DISCORD_TOKEN: SecretStr
    DATABASE_URL: PostgresDsn
    LOG_LEVEL: str = "INFO"
    
    # Optional: Test guild ID for rapid command syncing during dev
    TEST_GUILD_ID: Optional[int] = None

settings = Settings()

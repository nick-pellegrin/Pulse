from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://pulse:pulse@localhost:5432/pulse"
    agent_api_key: str = "dev-key-change-me"
    env: str = "development"


settings = Settings()

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    datasource_host: str = Field(default="db", alias="DATASOURCE_HOST")
    datasource_name: str = Field(alias="DATASOURCE_NAME")
    datasource_username: str = Field(alias="DATASOURCE_USERNAME")
    datasource_password: str = Field(alias="DATASOURCE_PASSWORD")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.datasource_username}:{self.datasource_password}"
            f"@{self.datasource_host}:5432/{self.datasource_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

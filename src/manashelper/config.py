from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    datasource_host: str = Field(default="db", alias="DATASOURCE_HOST")
    datasource_port: int = Field(default=5432, alias="DATASOURCE_PORT", ge=1, le=65535)
    datasource_name: str = Field(alias="DATASOURCE_NAME")
    datasource_username: str = Field(alias="DATASOURCE_USERNAME")
    datasource_password: str = Field(alias="DATASOURCE_PASSWORD")
    obis_encryption_key: str = Field(alias="OBIS_ENCRYPTION_KEY")
    advertisement_channel_id: int = Field(alias="ADVERTISEMENT_CHANNEL_ID")
    advertisement_channel_link: str = Field(alias="ADVERTISEMENT_CHANNEL_LINK")
    moderation_chat_id: int = Field(alias="MODERATION_CHAT_ID")
    admin_chat_id: int = Field(alias="ADMIN_CHAT_ID")
    eders_poll_minutes: int | None = Field(default=30, alias="EDERS_POLL_MINUTES", ge=15, le=60)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.datasource_username}:{self.datasource_password}"
            f"@{self.datasource_host}:{self.datasource_port}/{self.datasource_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from typing import Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    telegram_bot_token: str = Field(alias="MANASHELPER_TELEGRAM_BOT_TOKEN")
    datasource_host: str = Field(default="db", alias="MANASHELPER_DATASOURCE_HOST")
    datasource_name: str = Field(alias="MANASHELPER_DATASOURCE_NAME")
    datasource_username: str = Field(alias="MANASHELPER_DATASOURCE_USERNAME")
    datasource_password: str = Field(alias="MANASHELPER_DATASOURCE_PASSWORD")
    obis_encryption_key: str = Field(alias="MANASHELPER_OBIS_ENCRYPTION_KEY")
    advertisement_channel_id: int = Field(alias="MANASHELPER_ADVERTISEMENT_CHANNEL_ID")
    advertisement_channel_link: str = Field(alias="MANASHELPER_ADVERTISEMENT_CHANNEL_LINK")
    moderation_chat_id: int = Field(alias="MANASHELPER_MODERATION_CHAT_ID")
    admin_chat_id: int = Field(alias="MANASHELPER_ADMIN_CHAT_ID")
    eders_password: SecretStr | None = Field(default=None, alias="MANASHELPER_EDERS_PASSWORD")
    eders_poll_minutes: int | None = Field(default=15, alias="MANASHELPER_EDERS_POLL_MINUTES", ge=15, le=60)
    public_url: str | None = Field(default=None, alias="MANASHELPER_PUBLIC_URL")
    webhook_secret: SecretStr | None = Field(default=None, alias="MANASHELPER_WEBHOOK_SECRET")
    http_port: int = Field(default=8080, alias="MANASHELPER_HTTP_PORT", ge=1, le=65535)

    @model_validator(mode="after")
    def validate_webhook(self) -> Self:
        if not self.public_url:
            self.public_url = None
            return self
        parts = urlsplit(self.public_url)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.path not in {"", "/"}
            or parts.query
            or parts.fragment
        ):
            raise ValueError("MANASHELPER_PUBLIC_URL must be an HTTPS origin without a path or credentials")
        secret = self.webhook_secret.get_secret_value() if self.webhook_secret else ""
        if not 32 <= len(secret) <= 256 or any(
            c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in secret
        ):
            raise ValueError("MANASHELPER_WEBHOOK_SECRET must contain 32-256 URL-safe characters")
        self.public_url = self.public_url.rstrip("/")
        return self

    @property
    def eders_enabled(self) -> bool:
        return self.eders_password is not None and bool(self.eders_password.get_secret_value())

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.datasource_username}:{self.datasource_password}"
            f"@{self.datasource_host}:5432/{self.datasource_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    admin_web_origin: HttpUrl | None = Field(default=None, alias="MANASHELPER_ADMIN_WEB_ORIGIN")
    admin_web_signing_key: SecretStr | None = Field(
        default=None, alias="MANASHELPER_ADMIN_WEB_SIGNING_KEY", min_length=32
    )

    @field_validator("admin_web_origin")
    @classmethod
    def validate_admin_origin(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and (
            value.scheme != "https"
            or value.path not in (None, "/")
            or value.query
            or value.fragment
            or value.username
            or value.password
        ):
            raise ValueError("Admin web origin must be an HTTPS origin without credentials, path, query or fragment")
        return value

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

import os

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Select a deployment environment file at process startup.
# Defaults to .env for backward compatibility.
ENV_FILE = os.getenv("ENV_FILE", ".env")


class Settings(BaseSettings):
    app_name: str = "Investment Platform API"
    company_name: str = "Investment Platform"
    company_tagline: str = "Investment services"
    service_name: str = "investment-api"

    app_url: str = "https://example.invalid"
    api_url: str = "https://api.example.invalid"
    unsubscribe_url: str | None = None

    database_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60

    cors_origins: list[str] = ["http://localhost:3000"]

    resend_api_key: str
    # Accept the old FROM_EMAIL setting as well as EMAIL_FROM.
    from_email: str = Field(
        validation_alias=AliasChoices("EMAIL_FROM", "FROM_EMAIL")
    )

    initial_admin_email: str | None = None
    initial_admin_password: str | None = None
    initial_superadmin_email: str | None = None
    initial_superadmin_password: str | None = None

    # Reserved for cookie authentication if introduced later.
    cookie_domain: str | None = None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

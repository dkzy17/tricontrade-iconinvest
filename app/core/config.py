from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Icon Invest API"

    database_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60

    cors_origins: list[str] = ["http://localhost:3000"]

    resend_api_key: str
    from_email: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
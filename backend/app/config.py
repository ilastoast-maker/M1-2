from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "일어나 API"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "production"] = "development"
    auth_mode: Literal["firebase", "dev"] = "dev"
    use_in_memory_db: bool = True
    allowed_origins_raw: str = Field(
        default="http://localhost:5500,http://127.0.0.1:5500",
        validation_alias="ALLOWED_ORIGINS",
    )

    firebase_project_id: str | None = None
    firebase_service_account_json: str | None = None

    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    openai_max_output_tokens: int = Field(default=500, ge=100, le=2000)
    max_image_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=10 * 1024 * 1024)

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]

    def validate_production(self) -> None:
        if self.app_env != "production":
            return
        if self.auth_mode != "firebase":
            raise RuntimeError("Production requires AUTH_MODE=firebase")
        if self.use_in_memory_db:
            raise RuntimeError("Production cannot use the in-memory database")
        if not self.firebase_service_account_json:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON is required in production")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings

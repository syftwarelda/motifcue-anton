from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    motifcue_api_base_url: AnyHttpUrl
    anton_internal_api_key: SecretStr
    vercel_automation_bypass_secret: SecretStr | None = None

    poll_interval_seconds: float = Field(default=20, ge=1)
    request_timeout_seconds: float = Field(default=45, ge=5)
    media_page_size: int = Field(default=20, ge=1, le=50)
    max_media_items: int = Field(default=100, ge=1, le=500)
    media_analysis_concurrency: int = Field(default=2, ge=1, le=8)
    max_media_bytes: int = Field(default=50 * 1024 * 1024, ge=1_000_000)
    cleanup_media_after_success: bool = False
    data_directory: Path = Path("./data")
    report_directory: Path = Path("./reports")
    database_url: str = "sqlite:///./data/anton.db"
    log_level: str = "INFO"
    log_directory: Path = Path("./logs")
    log_to_file: bool = True

    llm_base_url: AnyHttpUrl = "http://127.0.0.1:11434/v1"
    llm_api_key: SecretStr = SecretStr("ollama")
    llm_text_model: str = "llama3.2:latest"
    llm_vision_model: str = "llama3.2-vision:11b"
    llm_embedding_model: str = "nomic-embed-text"
    llm_embedding_base_url: AnyHttpUrl | None = None
    llm_embedding_api_key: SecretStr | None = None
    llm_priority: str | None = None
    llm_timeout_seconds: float = Field(default=180, ge=10)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    knowledge_context_chunks: int = Field(default=6, ge=0, le=20)

    report_language: Literal["en", "es"] = "en"
    report_brand_name: str = "MotifCue"
    report_storage_driver: Literal["local_only", "local", "s3"] = "local_only"
    report_public_base_url: str | None = None

    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_public_base_url: str | None = None

    @field_validator(
        "motifcue_api_base_url",
        "llm_base_url",
        "llm_embedding_base_url",
        mode="before",
    )
    @classmethod
    def strip_trailing_slash(cls, value: object) -> object:
        return str(value).rstrip("/") if value else value

    def prepare_directories(self) -> None:
        self.data_directory.mkdir(parents=True, exist_ok=True)
        self.report_directory.mkdir(parents=True, exist_ok=True)
        if self.log_to_file:
            self.log_directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings(env_file: str = ".env") -> Settings:
    settings = Settings(_env_file=env_file)  # type: ignore[call-arg]
    settings.prepare_directories()
    return settings

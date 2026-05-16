from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the first FinSRE service shard."""

    model_config = SettingsConfigDict(env_prefix="FINSRE_", env_file=".env", extra="ignore")

    service_name: str = "finsre"
    environment: str = "local"
    gcp_billing_table: str | None = Field(
        default=None,
        description="Fully qualified BigQuery billing export table: project.dataset.table",
    )
    gcp_billing_project: str | None = Field(
        default=None,
        description="Optional BigQuery billing project used when running queries.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

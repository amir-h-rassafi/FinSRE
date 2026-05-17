import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the FinSRE CLI agent."""

    environment: str = "local"
    gcp_billing_account: str | None = None
    gcp_billing_currency: str = "USD"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    openai_api_key: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        return cls(
            environment=env.get("FINSRE_ENVIRONMENT", "local"),
            gcp_billing_account=env.get("FINSRE_GCP_BILLING_ACCOUNT"),
            gcp_billing_currency=env.get("FINSRE_GCP_BILLING_CURRENCY", "USD"),
            llm_provider=env.get("FINSRE_LLM_PROVIDER", "openai"),
            llm_model=env.get("FINSRE_LLM_MODEL", "gpt-4.1-mini"),
            openai_api_key=env.get("OPENAI_API_KEY"),
        )


def get_settings() -> Settings:
    return Settings.from_env(os.environ)

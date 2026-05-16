import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the FinSRE CLI agent."""

    environment: str = "local"
    gcp_billing_account: str | None = None
    gcp_billing_currency: str = "USD"


def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("FINSRE_ENVIRONMENT", "local"),
        gcp_billing_account=os.getenv("FINSRE_GCP_BILLING_ACCOUNT"),
        gcp_billing_currency=os.getenv("FINSRE_GCP_BILLING_CURRENCY", "USD"),
    )

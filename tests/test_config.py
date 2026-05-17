from finsre.config import Settings


def test_settings_from_env_uses_defaults() -> None:
    settings = Settings.from_env({})

    assert settings.environment == "local"
    assert settings.gcp_billing_currency == "USD"
    assert settings.llm_provider == "openai"
    assert settings.llm_model == "gpt-4.1-mini"
    assert settings.openai_api_key is None


def test_settings_from_env_reads_explicit_values() -> None:
    settings = Settings.from_env(
        {
            "FINSRE_ENVIRONMENT": "ci",
            "FINSRE_GCP_BILLING_ACCOUNT": "012345-6789AB-CDEF01",
            "FINSRE_GCP_BILLING_CURRENCY": "GBP",
            "FINSRE_LLM_PROVIDER": "openai",
            "FINSRE_LLM_MODEL": "gpt-test",
            "OPENAI_API_KEY": "secret",
        }
    )

    assert settings.environment == "ci"
    assert settings.gcp_billing_account == "012345-6789AB-CDEF01"
    assert settings.gcp_billing_currency == "GBP"
    assert settings.llm_model == "gpt-test"
    assert settings.openai_api_key == "secret"

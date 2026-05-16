from finsre.config import Settings
from finsre.errors import UnsupportedProviderError
from finsre.llm.base import LLMClient
from finsre.llm.openai_client import OpenAILLMClient


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider != "openai":
        raise UnsupportedProviderError(f"Unsupported LLM provider: {settings.llm_provider}")
    return OpenAILLMClient(api_key=settings.openai_api_key, model=settings.llm_model)

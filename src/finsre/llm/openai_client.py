import os

from finsre.errors import LLMProviderError, OptionalDependencyError
from finsre.llm.base import LLMClient, LLMMessage, LLMResponse, MissingLLMConfiguration


class OpenAILLMClient(LLMClient):
    def __init__(self, api_key: str | None, model: str) -> None:
        if not api_key:
            raise MissingLLMConfiguration("OPENAI_API_KEY is required to run LLM investigation agents.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OptionalDependencyError("Install the LLM extra first: pip install '.[llm]'") from exc

        client = OpenAI(api_key=api_key)
        if _langsmith_tracing_enabled(os.environ):
            try:
                from langsmith.wrappers import wrap_openai
            except ImportError as exc:
                raise OptionalDependencyError("Install the LLM extra first: pip install '.[llm]'") from exc
            client = wrap_openai(client)

        self._client = client
        self._model = model

    def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        try:
            response = self._client.responses.create(
                model=self._model,
                input=[{"role": message.role, "content": message.content} for message in messages],
            )
            return LLMResponse(content=response.output_text, model=self._model)
        except Exception as exc:
            raise LLMProviderError(f"OpenAI LLM call failed: {exc}") from exc
        finally:
            if _langsmith_tracing_enabled(os.environ):
                _flush_langsmith_traces()


def _langsmith_tracing_enabled(env: dict[str, str]) -> bool:
    return env.get("LANGSMITH_TRACING", "").lower() in {"1", "true", "yes", "on"}


def _flush_langsmith_traces() -> None:
    try:
        from langsmith import Client
    except ImportError:
        return
    try:
        Client().flush()
    except Exception:
        return

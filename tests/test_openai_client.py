import sys
import types
from unittest.mock import patch

from finsre.errors import LLMProviderError, OptionalDependencyError
from finsre.llm.openai_client import OpenAILLMClient


class FakeResponse:
    output_text = "traceable response"


class FakeResponses:
    def __init__(self) -> None:
        self.requests = []
        self.error = None

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error is not None:
            raise self.error
        return FakeResponse()


class FakeOpenAIClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.responses = FakeResponses()
        self.was_wrapped = False


def test_openai_client_wraps_sdk_when_langsmith_tracing_is_enabled(monkeypatch) -> None:
    install_fake_openai(monkeypatch)
    install_fake_langsmith(monkeypatch)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    client = OpenAILLMClient(api_key="secret", model="gpt-test")
    response = client.complete([])

    assert response.content == "traceable response"
    assert client._client.was_wrapped is True


def test_openai_client_flushes_langsmith_after_provider_error(monkeypatch) -> None:
    install_fake_openai(monkeypatch)
    fake_langsmith = install_fake_langsmith(monkeypatch)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    client = OpenAILLMClient(api_key="secret", model="gpt-test")
    client._client.responses.error = RuntimeError("429 insufficient_quota")

    try:
        client.complete([])
    except LLMProviderError as exc:
        assert "429 insufficient_quota" in str(exc)
    else:
        raise AssertionError("expected LLMProviderError")
    assert fake_langsmith.flush_count == 1


def test_openai_client_requires_langsmith_when_tracing_is_enabled(monkeypatch) -> None:
    install_fake_openai(monkeypatch)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delitem(sys.modules, "langsmith", raising=False)
    monkeypatch.delitem(sys.modules, "langsmith.wrappers", raising=False)

    real_import = __import__

    def blocked_import(name, *args, **kwargs):
        if name == "langsmith.wrappers":
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=blocked_import):
        try:
            OpenAILLMClient(api_key="secret", model="gpt-test")
        except OptionalDependencyError as exc:
            assert "Install the LLM extra" in str(exc)
        else:
            raise AssertionError("expected OptionalDependencyError")


def install_fake_openai(monkeypatch) -> None:
    openai_module = types.ModuleType("openai")
    openai_module.OpenAI = FakeOpenAIClient
    monkeypatch.setitem(sys.modules, "openai", openai_module)


def install_fake_langsmith(monkeypatch) -> None:
    langsmith_module = types.ModuleType("langsmith")
    wrappers_module = types.ModuleType("langsmith.wrappers")

    class FakeLangSmithClient:
        flush_count = 0

        def flush(self):
            type(self).flush_count += 1

    def wrap_openai(client):
        client.was_wrapped = True
        return client

    langsmith_module.Client = FakeLangSmithClient
    wrappers_module.wrap_openai = wrap_openai
    monkeypatch.setitem(sys.modules, "langsmith", langsmith_module)
    monkeypatch.setitem(sys.modules, "langsmith.wrappers", wrappers_module)
    return FakeLangSmithClient

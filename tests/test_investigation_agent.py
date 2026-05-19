import sys
import warnings
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from finsre.agents.investigation import InvestigationContext
from finsre.agents.langgraph_investigation import LangGraphInvestigationAgent
from finsre.discovery.workflow import SkuDiscoveryWorkflow
from finsre.errors import OptionalDependencyError
from finsre.llm.base import LLMResponse
from finsre.models import Anomaly, CostSeries


class FakeLLM:
    def __init__(self) -> None:
        self.messages = []

    def complete(self, messages):
        self.messages = messages
        return LLMResponse(content="Investigate network egress and missing traffic intent.", model="fake")


def _network_egress_context() -> InvestigationContext:
    series = CostSeries(
        service="Compute Engine",
        sku="egress-1",
        sku_description="Inter-region Egress",
        project_id="prod-api",
        currency="USD",
        points=((date(2026, 5, 8), Decimal("20")),),
    )
    anomaly = Anomaly(
        series=series,
        inflection_date=date(2026, 5, 8),
        baseline_cost=Decimal("10"),
        observed_cost=Decimal("20"),
        magnitude_pct=Decimal("100"),
    )
    plan = SkuDiscoveryWorkflow().plan_for_anomaly(anomaly)
    return InvestigationContext(anomaly=anomaly, discovery_plan=plan)


def test_langgraph_investigation_agent_runs_with_fake_langgraph(fake_langgraph) -> None:
    llm = FakeLLM()
    agent = LangGraphInvestigationAgent(llm_client=llm)

    result = agent.investigate(_network_egress_context())

    assert result.summary == "Investigate network egress and missing traffic intent."
    assert result.evidence[0]["context"]["classification"]["domain"] == "network_egress"
    assert "provided context" in llm.messages[0].content


def test_langgraph_investigation_agent_raises_repo_error_without_langgraph(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "langgraph.graph", raising=False)
    monkeypatch.delitem(sys.modules, "langgraph", raising=False)

    real_import = __import__

    def blocked_import(name, *args, **kwargs):
        if name == "langgraph.graph":
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=blocked_import):
        try:
            LangGraphInvestigationAgent(llm_client=FakeLLM())
        except OptionalDependencyError as exc:
            assert "Install the LLM extra" in str(exc)
        else:
            raise AssertionError("expected OptionalDependencyError")


def test_langgraph_dependency_warning_is_suppressed(fake_langgraph) -> None:
    real_import = __import__

    def noisy_import(name, *args, **kwargs):
        if name == "langgraph.graph":
            warnings.warn(
                "The default value of `allowed_objects` will change in a future version.",
                UserWarning,
                stacklevel=2,
            )
        return real_import(name, *args, **kwargs)

    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        with patch("builtins.__import__", side_effect=noisy_import):
            LangGraphInvestigationAgent(llm_client=FakeLLM())

    assert seen == []

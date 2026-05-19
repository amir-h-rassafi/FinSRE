from dataclasses import dataclass

from finsre.discovery.facts import ContextFact
from finsre.discovery.probes import DiscoveryProbe, ProbeKind
from finsre.discovery.sku import SkuClassification, SkuDomain


@dataclass(frozen=True)
class Question:
    id: str
    entity_id: str
    text: str
    reason: str
    blocks_recommendation: bool = True


class QuestionPlanner:
    """Asks only when missing intent changes the next action."""

    def plan(
        self,
        classification: SkuClassification,
        probes: tuple[DiscoveryProbe, ...],
        facts: tuple[ContextFact, ...] = (),
        *,
        project_id: str | None = None,
    ) -> tuple[Question, ...]:
        fact_types = {fact.fact_type for fact in facts}
        entity_id = project_id or "unknown-project"

        if classification.domain == SkuDomain.NETWORK_EGRESS and "traffic_intent" not in fact_types:
            return (
                Question(
                    id=f"{entity_id}:traffic-intent",
                    entity_id=entity_id,
                    text=(
                        f"Is the billed network traffic for project `{entity_id}` expected for HA, "
                        "migration, or customer traffic?"
                    ),
                    reason="Network egress optimization depends on whether cross-boundary traffic is intentional.",
                ),
            )

        if any(probe.kind == ProbeKind.ASSET for probe in probes) and "owner" not in fact_types:
            return (
                Question(
                    id=f"{entity_id}:owner",
                    entity_id=entity_id,
                    text=f"Who owns project `{entity_id}` for cost and architecture decisions?",
                    reason="Recommendations need an owner before becoming actionable work.",
                    blocks_recommendation=False,
                ),
            )

        return ()

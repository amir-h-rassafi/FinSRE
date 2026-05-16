from dataclasses import dataclass
from enum import StrEnum


class ComponentKind(StrEnum):
    CLI = "cli"
    CONNECTOR = "connector"
    NORMALIZER = "normalizer"
    AGENT = "agent"
    MEMORY = "memory"
    TRACKER = "tracker"


class DeployMode(StrEnum):
    IN_PROCESS = "in_process"
    CLI_JOB = "cli_job"
    QUEUE_WORKER = "queue_worker"
    SERVICE = "service"


@dataclass(frozen=True)
class ComponentManifest:
    """Describes how a module can run now and be split out later."""

    name: str
    kind: ComponentKind
    version: str
    input_events: tuple[str, ...] = ()
    output_events: tuple[str, ...] = ()
    deploy_modes: tuple[DeployMode, ...] = (DeployMode.IN_PROCESS,)
    dependencies: tuple[str, ...] = ()
    description: str = ""

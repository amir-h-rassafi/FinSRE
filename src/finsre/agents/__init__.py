"""Agent orchestration interfaces.

The MVP keeps agent execution optional. LangGraph or another runner should plug
in here behind these interfaces so the CLI/core does not depend on one agent
framework.
"""

from finsre.agents.base import AgentCapability, AgentRequest, AgentResult
from finsre.agents.router import AgentRouter

__all__ = ["AgentCapability", "AgentRequest", "AgentResult", "AgentRouter"]

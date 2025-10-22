# ABOUTME: Agent registration system for HTTP protocols (REST and MCP)
# ABOUTME: Maps agents to request/response models and enables dynamic route/tool generation

import logging

from pydantic import BaseModel

from agent_kit.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistration:
    """Metadata for a registered agent."""

    def __init__(
        self,
        name: str,
        agent_class: type[BaseAgent],
        description: str,
        request_model: type[BaseModel],
        response_model: type[BaseModel],
    ):
        self.name = name
        self.agent_class = agent_class
        self.description = description
        self.request_model = request_model
        self.response_model = response_model


class AgentRegistry:
    """Registry for agents available via HTTP protocols."""

    def __init__(self):
        self._agents: dict[str, AgentRegistration] = {}

    def register(
        self,
        name: str,
        agent_class: type[BaseAgent],
        description: str,
        request_model: type[BaseModel],
        response_model: type[BaseModel],
    ) -> None:
        """Register an agent for HTTP access.

        Args:
            name: Agent name (used in URLs and tool names)
            agent_class: BaseAgent subclass
            description: Human-readable description for API docs and MCP tools
            request_model: Pydantic model for request body
            response_model: Pydantic model for response body
        """
        if name in self._agents:
            logger.warning(f"Agent '{name}' already registered, overwriting")

        self._agents[name] = AgentRegistration(
            name=name,
            agent_class=agent_class,
            description=description,
            request_model=request_model,
            response_model=response_model,
        )

        logger.info(f"Registered agent: {name} ({agent_class.__name__})")

    def get(self, name: str) -> AgentRegistration | None:
        """Get registered agent by name."""
        return self._agents.get(name)

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    def get_all(self) -> dict[str, AgentRegistration]:
        """Get all registered agents."""
        return self._agents.copy()

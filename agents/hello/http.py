# HTTP interface setup for Hello Agent including registry and server configuration

from agent_kit.api.http import AgentRegistry, create_server
from agent_kit.api.mcp import run_mcp_stdio
from agent_kit.config import get_config

from .agent import HelloAgent
from .models import HelloRequest, HelloResponse


def create_hello_registry() -> AgentRegistry:
    """Create and configure agent registry for Hello Agent."""
    registry = AgentRegistry()

    registry.register(
        name="hello",
        agent_class=HelloAgent,
        description="Hello Agent",
        request_model=HelloRequest,
        response_model=HelloResponse,
    )

    return registry


def create_hello_server():
    """Create HTTP server for Hello Agent with config from user directory."""
    config = get_config()
    registry = create_hello_registry()

    return create_server(registry, config.interfaces.http, config.interfaces.session_ttl)


def run_hello_stdio() -> None:
    """Run Hello Agent in MCP stdio mode for Claude Desktop integration."""
    registry = create_hello_registry()
    run_mcp_stdio(registry)

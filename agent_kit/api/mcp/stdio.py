# MCP stdio mode runner

import logging

from agent_kit.api.http.mcp import create_mcp_server, set_mcp_globals
from agent_kit.api.http.registry import AgentRegistry

logger = logging.getLogger(__name__)


def run_mcp_stdio(registry: AgentRegistry) -> None:
    """Run MCP server in stdio mode for Claude Desktop integration."""
    logger.info("Starting MCP stdio mode")

    set_mcp_globals(registry, None)

    mcp = create_mcp_server(registry)

    logger.info("Entering MCP stdio transport")
    mcp.run()

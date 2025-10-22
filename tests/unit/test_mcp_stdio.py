"""Test MCP stdio mode functionality."""

from typing import Any
from unittest.mock import MagicMock, patch


def test_run_mcp_stdio_creates_server(test_registry: Any) -> None:
    """run_mcp_stdio creates MCP server and calls run()."""
    # Mock at the module import level to prevent lifespan execution
    with patch("agent_kit.api.mcp.stdio.create_mcp_server") as mock_create:
        with patch("agent_kit.api.mcp.stdio.set_mcp_globals") as mock_set_globals:
            mock_mcp = MagicMock()
            mock_create.return_value = mock_mcp

            from agent_kit.api.mcp.stdio import run_mcp_stdio

            # Run stdio mode
            run_mcp_stdio(test_registry)

            # Verify globals were set
            mock_set_globals.assert_called_once_with(test_registry, None)

            # Verify server was created
            mock_create.assert_called_once_with(test_registry)

            # Verify run() was called to start stdio transport
            mock_mcp.run.assert_called_once()


def test_run_mcp_stdio_sets_globals(test_registry: Any) -> None:
    """run_mcp_stdio sets global registry for tool execution."""
    # Mock to prevent actual stdio transport
    with patch("agent_kit.api.mcp.stdio.create_mcp_server") as mock_create:
        with patch("agent_kit.api.mcp.stdio.set_mcp_globals") as mock_set_globals:
            mock_mcp = MagicMock()
            mock_create.return_value = mock_mcp

            from agent_kit.api.mcp.stdio import run_mcp_stdio

            # Run stdio mode
            run_mcp_stdio(test_registry)

            # Verify globals were set with registry
            mock_set_globals.assert_called_once_with(test_registry, None)

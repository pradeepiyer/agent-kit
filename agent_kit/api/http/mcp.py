# ABOUTME: MCP (Model Context Protocol) tool generation and server for Claude Desktop integration
# ABOUTME: Dynamically creates MCP tools from registered agents with session management

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import Context, FastMCP

from agent_kit.api.core import SessionStore
from agent_kit.api.http.registry import AgentRegistry
from agent_kit.api.progress import MCPProgressHandler
from agent_kit.config import setup_configuration
from agent_kit.config.config import close_all_clients, get_openai_client

logger = logging.getLogger(__name__)

# Global shared instances
_registry: AgentRegistry | None = None
_session_store: SessionStore | None = None

# Map MCP session ID -> AgentAPI session ID for persistence
_mcp_to_agent_session: dict[str, str] = {}


def set_mcp_globals(registry: AgentRegistry, session_store: SessionStore | None = None) -> None:
    """Set global registry and session store for MCP tools.

    Args:
        registry: Agent registry for tool generation
        session_store: Optional session store. If None, will be created in lifespan.
    """
    global _registry, _session_store
    _registry = registry
    if session_store is not None:
        _session_store = session_store


@asynccontextmanager
async def mcp_lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Initialize configuration and clients in FastMCP's event loop."""
    logger.info("MCP lifespan: Starting initialization")

    # Initialize config and clients
    config = await setup_configuration()
    logger.info("MCP lifespan: Configuration initialized")

    # Initialize session store if not already set
    global _session_store
    if _session_store is None:
        _session_store = SessionStore(get_openai_client(), default_ttl=config.interfaces.session_ttl)
        logger.info(f"MCP lifespan: SessionStore initialized (session_ttl={config.interfaces.session_ttl}s)")

    # Start background cleanup task
    cleanup_task = asyncio.create_task(_periodic_session_cleanup())
    logger.info("MCP lifespan: Started periodic session cleanup task")

    yield

    # Stop cleanup task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("MCP lifespan: Stopped periodic session cleanup task")

    logger.info("MCP lifespan: Shutting down, closing all clients")
    await close_all_clients()
    logger.info("MCP lifespan: All clients closed successfully")


async def _periodic_session_cleanup():
    """Periodically remove mappings for expired agent sessions."""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        if _session_store is None:
            continue

        # Find stale mappings (where agent session no longer exists)
        stale_mcp_sids = [
            mcp_sid
            for mcp_sid, agent_sid in _mcp_to_agent_session.items()
            if await _session_store.get_session(agent_sid) is None
        ]

        # Remove them
        for mcp_sid in stale_mcp_sids:
            del _mcp_to_agent_session[mcp_sid]

        if stale_mcp_sids:
            logger.info(f"Cleaned up {len(stale_mcp_sids)} stale MCP session mappings")


def create_mcp_server(registry: AgentRegistry) -> FastMCP:
    """Create FastMCP server with dynamically generated tools from registry."""
    mcp = FastMCP("agent-kit", lifespan=mcp_lifespan)

    # Dynamically create tools for each registered agent
    for agent_name, registration in registry.get_all().items():
        # Create the tool function dynamically
        async def tool_func(query: str, ctx: Context, agent_name: str = agent_name) -> dict[str, Any]:
            if _registry is None or _session_store is None:
                return {"error": "MCP server not initialized"}

            registration = _registry.get(agent_name)
            if not registration:
                return {"error": f"Unknown agent: {agent_name}"}

            # Get or create session with MCP progress handler
            mcp_sid = ctx.session_id
            progress_handler = MCPProgressHandler(ctx)

            # Check if we have an existing session mapping
            if mcp_sid in _mcp_to_agent_session:
                agent_sid = _mcp_to_agent_session[mcp_sid]
                session = await _session_store.get_session(agent_sid)
                if session is None:
                    # Session expired, create new one
                    logger.info(f"Session expired for MCP session {mcp_sid}, creating new one")
                    del _mcp_to_agent_session[mcp_sid]
                    agent_sid = await _session_store.create_session(progress_handler)
                    _mcp_to_agent_session[mcp_sid] = agent_sid
                else:
                    # Update progress handler for this request
                    session.progress_handler = progress_handler
            else:
                # Create new session
                agent_sid = await _session_store.create_session(progress_handler)
                _mcp_to_agent_session[mcp_sid] = agent_sid
                logger.info(f"Created AgentAPI session {agent_sid} for MCP session {mcp_sid}")

            # Get session and agent
            session = await _session_store.get_session(agent_sid)
            if not session:
                return {"error": "Failed to get session"}

            agent = await session.use_agent(registration.agent_class)

            # Execute agent (assumes agent has a 'process' method)
            try:
                result = await agent.process(query)  # type: ignore[attr-defined]
                # Serialize result
                result_data = result.model_dump() if hasattr(result, "model_dump") else str(result)  # type: ignore[union-attr]
                return {"result": result_data}
            except Exception as e:
                logger.exception(f"Agent execution failed: {e}")
                return {"error": str(e)}

        # Register the tool with FastMCP
        # FastMCP expects the function to be decorated, but we're doing it dynamically
        tool_func.__name__ = f"{agent_name}_agent"
        tool_func.__doc__ = f"{registration.description}\n\nArgs:\n    query: Input query for the agent"

        # Register using FastMCP's tool decorator
        mcp.tool()(tool_func)

    return mcp


def get_mcp_app(registry: AgentRegistry) -> Any:
    """Get MCP ASGI application for mounting into FastAPI."""
    mcp = create_mcp_server(registry)
    return mcp.http_app()

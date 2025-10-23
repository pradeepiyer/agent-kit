# ABOUTME: Unified HTTP server supporting REST and MCP protocols with configuration-driven setup
# ABOUTME: Creates FastAPI application with session management and background cleanup tasks

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer

from agent_kit.api.core import SessionStore
from agent_kit.api.http.mcp import get_mcp_app, set_mcp_globals
from agent_kit.api.http.registry import AgentRegistry
from agent_kit.api.http.rest import create_rest_routes
from agent_kit.config import setup_configuration
from agent_kit.config.config import close_all_clients, get_openai_client
from agent_kit.config.models import HttpConfig

logger = logging.getLogger(__name__)

_http_security = HTTPBearer(auto_error=False)


@asynccontextmanager
async def server_lifespan(app: FastAPI, http_config: HttpConfig, session_ttl: int) -> AsyncIterator[None]:
    """Unified lifespan for REST and MCP protocols."""
    # Initialize configuration and all clients
    await setup_configuration()
    logger.info("Configuration and clients initialized")

    # Get session store from app state
    session_store: SessionStore = app.state.session_store

    enabled: list[str] = []
    if http_config.rest_api:
        enabled.append("REST")
    if http_config.mcp_http:
        enabled.append("MCP")

    protocols_str = ", ".join(enabled) if enabled else "none"
    logger.info(f"HTTP server starting with protocols: {protocols_str}")
    logger.info(f"Session TTL: {session_ttl}s")

    # Start session cleanup background task
    async def periodic_session_cleanup():
        """Periodically clean up expired sessions."""
        while True:
            await asyncio.sleep(300)  # Every 5 minutes
            count = await session_store.cleanup_expired()
            if count > 0:
                logger.info(f"Cleaned up {count} expired sessions")

    cleanup_task = asyncio.create_task(periodic_session_cleanup())

    yield

    # Cleanup
    logger.info("HTTP server shutting down")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await close_all_clients()


def create_server(registry: AgentRegistry, http_config: HttpConfig, session_ttl: int = 3600) -> FastAPI:
    """Create FastAPI app with REST and/or MCP support based on config.

    Args:
        registry: AgentRegistry with registered agents
        http_config: HttpConfig specifying server settings and which protocols to enable
        session_ttl: Session time-to-live in seconds

    Returns:
        Configured FastAPI application
    """
    # Initialize session store
    session_store = SessionStore(get_openai_client(), default_ttl=session_ttl)

    app = FastAPI(
        title="Agent Kit API",
        description="Unified HTTP API for Agent Kit with REST and MCP support",
        version="0.1.0",
        lifespan=lambda app: server_lifespan(app, http_config, session_ttl),
    )

    # Store registry and session store in app state
    app.state.registry = registry
    app.state.session_store = session_store
    app.state.http_config = http_config

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=http_config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth middleware for MCP HTTP endpoints
    if http_config.auth_enabled and http_config.mcp_http:

        @app.middleware("http")
        async def mcp_auth_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:  # pyright: ignore[reportUnusedFunction]
            """Check authentication for MCP HTTP requests."""
            # Only check auth for MCP paths
            if request.url.path.startswith(http_config.mcp_mount_path):
                # Import here to avoid circular dependency
                from agent_kit.api.http.auth import verify_oauth_token

                # Extract token
                auth_header = request.headers.get("Authorization")
                if not auth_header or not auth_header.startswith("Bearer "):
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Missing authentication token"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )

                token = auth_header[7:]  # Remove "Bearer " prefix

                # Verify token
                if not http_config.oauth_issuer or not http_config.oauth_client_id:
                    logger.error("OAuth authentication enabled but oauth_issuer or oauth_client_id not configured")
                    return JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={"detail": "Authentication not properly configured"},
                    )

                try:
                    await verify_oauth_token(token, http_config.oauth_issuer, http_config.oauth_client_id)
                except HTTPException as e:
                    return JSONResponse(status_code=e.status_code, content={"detail": e.detail})

            return await call_next(request)

    # Global exception handlers
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        logger.exception(f"Unhandled exception for {request.url}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Internal server error"}
        )

    # Mount REST routes
    if http_config.rest_api:
        # Create and include REST router
        rest_router = create_rest_routes(registry, session_store)
        app.include_router(rest_router)
        logger.info("REST API endpoints enabled")

    # Mount MCP tools
    if http_config.mcp_http:
        set_mcp_globals(registry, session_store)
        mcp_app = get_mcp_app(registry)
        app.mount(http_config.mcp_mount_path, mcp_app)
        logger.info(f"MCP tools enabled at {http_config.mcp_mount_path}")

    return app

# ABOUTME: REST API routes with Server-Sent Events (SSE) streaming for real-time progress
# ABOUTME: Provides session management and dynamic agent execution endpoints

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import Response, StreamingResponse

from agent_kit.api.core import SessionStore
from agent_kit.api.http import models
from agent_kit.api.http.auth import get_current_user
from agent_kit.api.http.registry import AgentRegistration, AgentRegistry
from agent_kit.api.progress import RESTProgressHandler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


def create_rest_routes(registry: AgentRegistry, session_store: SessionStore) -> APIRouter:
    """Create REST routes dynamically based on registered agents."""

    @router.post("/sessions", response_model=models.SessionCreateResponse, status_code=status.HTTP_201_CREATED)
    async def create_session(user: str = Depends(get_current_user)) -> models.SessionCreateResponse:  # pyright: ignore[reportUnusedFunction]
        """Create new session with no-op progress handler (will be replaced per-request)."""
        from agent_kit.api.progress import NoOpProgressHandler

        session_id = await session_store.create_session(NoOpProgressHandler())
        return models.SessionCreateResponse(session_id=session_id)

    @router.get("/sessions/{session_id}", response_model=models.SessionInfo)
    async def get_session_info(  # pyright: ignore[reportUnusedFunction]
        session_id: Annotated[str, Path()], user: str = Depends(get_current_user)
    ) -> models.SessionInfo:
        """Get session information."""
        session = await session_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        return models.SessionInfo(
            session_id=session.session_id,
            created_at=session.created_at,
            last_accessed=session.last_accessed,
            active_agents=[name for name in session.agents.keys()],
        )

    @router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_session(session_id: Annotated[str, Path()], user: str = Depends(get_current_user)) -> Response:  # pyright: ignore[reportUnusedFunction]
        """Delete session."""
        await session_store.delete_session(session_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/health", response_model=models.HealthResponse)
    async def health() -> models.HealthResponse:  # pyright: ignore[reportUnusedFunction]
        """Health check endpoint."""
        return models.HealthResponse(status="ok", version="0.1.0")

    @router.get("/info", response_model=models.InfoResponse)
    async def info() -> models.InfoResponse:  # pyright: ignore[reportUnusedFunction]
        """API information."""
        from agent_kit.config import get_config

        config = get_config()
        return models.InfoResponse(
            version="0.1.0",
            api_version="v1",
            agents=[
                models.AgentInfo(name=name, description=reg.description) for name, reg in registry.get_all().items()
            ],
            auth_required=config.interfaces.http.auth_enabled,
        )

    # Create dynamic agent routes
    for agent_name, registration in registry.get_all().items():

        def make_endpoint(
            reg: AgentRegistration, name: str
        ) -> Callable[[Any, str], Coroutine[Any, Any, StreamingResponse]]:
            """Factory to create endpoint with proper request model type."""

            async def endpoint(request: reg.request_model, user: str = Depends(get_current_user)) -> StreamingResponse:  # type: ignore[valid-type]
                """Dynamic agent endpoint with SSE streaming."""
                return await stream_agent_operation(request, name, session_store, registry)

            return endpoint  # type: ignore[return-value]

        # Add route dynamically with correct request model
        router.add_api_route(
            f"/{agent_name}",
            make_endpoint(registration, agent_name),
            methods=["POST"],
            response_class=StreamingResponse,
            name=f"{agent_name}_execute",
        )

    return router


async def stream_agent_operation(
    request: Any, agent_name: str, session_store: SessionStore, registry: AgentRegistry
) -> StreamingResponse:
    """Stream agent operation via SSE with proper cleanup."""

    async def event_generator():
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        progress_handler = RESTProgressHandler(queue)

        # Get or create session
        session_id = getattr(request, "session_id", None)
        if not session_id or not await session_store.get_session(session_id):
            session_id = await session_store.create_session(progress_handler)
        else:
            # Update existing session's progress handler
            session = await session_store.get_session(session_id)
            if session:
                session.progress_handler = progress_handler

        # Get agent registration
        registration = registry.get(agent_name)
        if not registration:
            yield f"data: {json.dumps({'type': 'error', 'error': f'Unknown agent: {agent_name}'})}\n\n"
            return

        # Get session
        session = await session_store.get_session(session_id)
        if not session:
            yield f"data: {json.dumps({'type': 'error', 'error': 'Session not found'})}\n\n"
            return

        # Get or create agent
        agent = await session.use_agent(registration.agent_class)

        # Execute agent (assumes agent has a 'process' method)
        # Extract query from request
        query = getattr(request, "query", str(request))

        task: asyncio.Task[Any] = asyncio.create_task(agent.process(query))  # type: ignore[attr-defined]

        try:
            while not task.done():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.1)
                    yield f"data: {json.dumps(event)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"

            try:
                result = await task

                # Drain remaining events from queue
                while True:
                    try:
                        event = queue.get_nowait()
                        yield f"data: {json.dumps(event)}\n\n"
                    except asyncio.QueueEmpty:
                        break

                # Serialize result
                if hasattr(result, "model_dump"):
                    result_data = result.model_dump()
                elif isinstance(result, str):
                    # Wrap plain string results in expected format
                    result_data = {"response": result, "session_id": session_id}
                else:
                    result_data = str(result)
                yield f"data: {json.dumps({'type': 'result', 'data': result_data, 'session_id': session_id})}\n\n"
            except Exception as e:
                logger.exception(f"Agent execution failed: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'session_id': session_id})}\n\n"
        finally:
            # Clean up: cancel task if still running
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

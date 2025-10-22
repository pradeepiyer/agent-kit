# ABOUTME: Request and response models for REST and MCP protocols
# ABOUTME: Base models for session management and health checks

from datetime import datetime

from pydantic import BaseModel


class BaseRequest(BaseModel):
    """Base request with optional session."""

    session_id: str | None = None


class BaseResponse(BaseModel):
    """Base response with session."""

    session_id: str


class SessionCreateResponse(BaseModel):
    """Session creation response."""

    session_id: str


class SessionInfo(BaseModel):
    """Session information."""

    session_id: str
    created_at: datetime
    last_accessed: datetime
    active_agents: list[str]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


class InfoResponse(BaseModel):
    """API info response."""

    version: str
    api_version: str
    agents: list[str]

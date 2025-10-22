# Request and response models for Hello Agent HTTP endpoints

from pydantic import BaseModel, Field


class HelloRequest(BaseModel):
    """Request model for Hello Agent."""

    query: str = Field(..., description="User query or message to process")
    session_id: str | None = Field(None, description="Optional session ID for conversation continuation")


class HelloResponse(BaseModel):
    """Response model for Hello Agent."""

    response: str = Field(..., description="Agent's response message")
    session_id: str = Field(..., description="Session ID for conversation continuation")

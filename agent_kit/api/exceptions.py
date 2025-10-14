"""Exception types for Hello Agent API."""

from agent_kit.exceptions import HelloAgentError


class SessionNotFoundError(HelloAgentError):
    """Raised when a session ID is not found in the session store."""

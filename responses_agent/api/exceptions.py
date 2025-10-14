"""Exception types for Hello Agent API."""

from responses_agent.exceptions import HelloAgentError


class SessionNotFoundError(HelloAgentError):
    """Raised when a session ID is not found in the session store."""

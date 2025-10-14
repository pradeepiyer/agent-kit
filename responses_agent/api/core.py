"""Core API implementation for unified agent access."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from responses_agent.agents.hello.agent import HelloAgent
from responses_agent.api.exceptions import SessionNotFoundError
from responses_agent.api.models import AgentType
from responses_agent.clients.openai_client import OpenAIClient
from responses_agent.config.config import get_openai_client

logger = logging.getLogger(__name__)


class AgentSession:
    """Manages state for a single user session."""

    def __init__(self, session_id: str, openai_client: OpenAIClient):
        self.session_id = session_id
        self.openai_client = openai_client
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.agents: dict[AgentType, Any] = {}
        self.last_active_agent: AgentType | None = None
        self.agent_results: dict[AgentType, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_agent(self, agent_type: AgentType) -> Any:
        """Get existing agent or create new one (lazy creation)."""
        async with self._lock:
            self.last_accessed = datetime.now()

            if agent_type in self.agents:
                logger.debug(f"Reusing existing {agent_type.value} agent for session {self.session_id}")
                return self.agents[agent_type]

            logger.info(f"Creating new {agent_type.value} agent for session {self.session_id}")

            if agent_type == AgentType.HELLO:
                agent = HelloAgent(self.openai_client)
            else:
                raise ValueError(f"Unknown agent type: {agent_type}")

            self.agents[agent_type] = agent
            return agent

    async def update_last_active(self, agent_type: AgentType) -> None:
        """Update the last active agent for this session."""
        async with self._lock:
            self.last_active_agent = agent_type
            self.last_accessed = datetime.now()
            logger.debug(f"Session {self.session_id} last active agent: {agent_type.value}")

    async def store_result(self, agent_type: AgentType, result: Any, **metadata: Any) -> None:
        """Store agent result for cross-agent context."""
        async with self._lock:
            self.agent_results[agent_type] = {"result": result, "timestamp": datetime.now().isoformat(), **metadata}
            logger.debug(f"Stored result for {agent_type.value} in session {self.session_id}")

    async def get_result(self, agent_type: AgentType) -> dict[str, Any] | None:
        """Retrieve stored result from another agent."""
        async with self._lock:
            return self.agent_results.get(agent_type)

    async def clear_results(self, agent_type: AgentType | None = None) -> None:
        """Clear stored results. If agent_type is None, clear all results."""
        async with self._lock:
            if agent_type is None:
                self.agent_results.clear()
                logger.debug(f"Cleared all results in session {self.session_id}")
            else:
                self.agent_results.pop(agent_type, None)
                logger.debug(f"Cleared {agent_type.value} result in session {self.session_id}")

    async def is_expired(self, ttl_seconds: int) -> bool:
        """Check if session has expired based on TTL."""
        async with self._lock:
            age = (datetime.now() - self.last_accessed).total_seconds()
            return age > ttl_seconds


class SessionStore:
    """Async-safe store for managing multiple sessions."""

    def __init__(self, openai_client: OpenAIClient, default_ttl: int = 3600):
        self.openai_client = openai_client
        self.default_ttl = default_ttl
        self.sessions: dict[str, AgentSession] = {}
        self._lock = asyncio.Lock()
        logger.info(f"SessionStore initialized with TTL={default_ttl}s")

    async def create_session(self) -> str:
        """Create a new session and return session ID."""
        session_id = str(uuid.uuid4())
        session = AgentSession(session_id, self.openai_client)

        async with self._lock:
            self.sessions[session_id] = session

        logger.info(f"Created new session: {session_id}")
        return session_id

    async def get_session(self, session_id: str) -> AgentSession | None:
        """Get session by ID, returns None if not found or expired."""
        async with self._lock:
            logger.debug(f"get_session called for session_id: {session_id}")
            logger.debug(f"SessionStore has {len(self.sessions)} total sessions")

            session = self.sessions.get(session_id)

            if session is None:
                logger.warning(f"Session {session_id} not found in store")
                return None

            # Refresh last_accessed on any access (refresh-on-access pattern)
            # This prevents expiry during active usage, even for long operations
            old_age = (datetime.now() - session.last_accessed).total_seconds()
            session.last_accessed = datetime.now()
            logger.debug(f"Session {session_id} accessed (was {old_age:.2f}s old, refreshed to prevent expiry)")

            return session

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID."""
        async with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"Deleted session: {session_id}")
                return True
            return False

    async def cleanup_expired(self) -> int:
        """Remove all expired sessions and return count of removed sessions."""
        async with self._lock:
            # Gather expired session checks asynchronously
            expired_checks = await asyncio.gather(
                *[session.is_expired(self.default_ttl) for session in self.sessions.values()]
            )
            expired_ids = [sid for sid, is_exp in zip(self.sessions.keys(), expired_checks) if is_exp]

            for sid in expired_ids:
                del self.sessions[sid]

            if expired_ids:
                logger.info(f"Cleaned up {len(expired_ids)} expired sessions")

            return len(expired_ids)

    async def get_session_count(self) -> int:
        """Get current number of active sessions."""
        async with self._lock:
            return len(self.sessions)


class AgentAPI:
    """Unified API for all Hello Agent functionality."""

    def __init__(self, openai_client: OpenAIClient | None = None, session_ttl: int = 3600):
        """Initialize AgentAPI with optional client injection."""
        self.openai_client = openai_client or get_openai_client()
        self.session_store = SessionStore(self.openai_client, default_ttl=session_ttl)
        logger.info("AgentAPI initialized")

    async def _get_session(self, session_id: str) -> AgentSession:
        """Get session or raise error if not found."""
        logger.debug(f"_get_session called with session_id: {session_id}")
        session = await self.session_store.get_session(session_id)
        if session is None:
            logger.error(f"Session {session_id} not found or expired - raising SessionNotFoundError")
            raise SessionNotFoundError(f"Session not found or expired: {session_id}")
        logger.debug(f"Session {session_id} found successfully")
        return session

    async def hello(self, name: str, session_id: str) -> str:
        """Execute hello agent hello.

        Args:
            name: Name to greet
            session_id: Session identifier

        Returns:
            Personalized greeting message
        """
        session = await self._get_session(session_id)
        agent = await session.get_or_create_agent(AgentType.HELLO)
        await session.update_last_active(AgentType.HELLO)

        logger.info(f"Executing hello for session {session_id}")
        query = f"Greet {name}"
        result = await agent.process(query, continue_conversation=False)

        await session.store_result(AgentType.HELLO, result, name=name)
        return result

    async def chat(self, query: str, session_id: str) -> str:
        """Execute hello agent chat with conversation continuation.

        Args:
            query: User query
            session_id: Session identifier

        Returns:
            Chat response
        """
        session = await self._get_session(session_id)
        agent = await session.get_or_create_agent(AgentType.HELLO)
        await session.update_last_active(AgentType.HELLO)

        logger.info(f"Executing chat for session {session_id}")
        result = await agent.process(query, continue_conversation=True)

        await session.store_result(AgentType.HELLO, result, query=query)
        return result

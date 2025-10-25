"""Core API implementation for unified agent access."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from agent_kit.agents.base_agent import BaseAgent
from agent_kit.api.progress import ProgressHandler
from agent_kit.clients.openai_client import OpenAIClient

logger = logging.getLogger(__name__)


class AgentSession:
    """Manages state for a single user session."""

    def __init__(self, session_id: str, openai_client: OpenAIClient, progress_handler: ProgressHandler):
        self.session_id = session_id
        self.openai_client = openai_client
        self.progress_handler = progress_handler
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.agents: dict[str, BaseAgent] = {}
        self.last_active_agent: str | None = None
        self.agent_results: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def use_agent(self, agent_class: type[BaseAgent]) -> BaseAgent:
        """Get or create agent instance.

        Args:
            agent_class: Agent class to instantiate

        Returns:
            Cached agent instance for this session
        """
        async with self._lock:
            self.last_accessed = datetime.now()
            agent_key = agent_class.__name__

            if agent_key in self.agents:
                logger.debug(f"Reusing existing {agent_key} for session {self.session_id}")
                return self.agents[agent_key]

            logger.info(f"Creating {agent_key} for session {self.session_id}")
            agent = agent_class(self.openai_client, self.progress_handler)
            self.agents[agent_key] = agent
            return agent

    async def update_last_active(self, agent_key: str) -> None:
        """Update the last active agent for this session."""
        async with self._lock:
            self.last_active_agent = agent_key
            self.last_accessed = datetime.now()
            logger.debug(f"Session {self.session_id} last active agent: {agent_key}")

    async def store_result(self, agent_key: str, result: Any, **metadata: Any) -> None:
        """Store agent result for cross-agent context."""
        async with self._lock:
            self.agent_results[agent_key] = {"result": result, "timestamp": datetime.now().isoformat(), **metadata}
            logger.debug(f"Stored result for {agent_key} in session {self.session_id}")

    async def get_result(self, agent_key: str) -> dict[str, Any] | None:
        """Retrieve stored result from another agent."""
        async with self._lock:
            return self.agent_results.get(agent_key)

    async def clear_results(self, agent_key: str | None = None) -> None:
        """Clear stored results. If agent_key is None, clear all results."""
        async with self._lock:
            if agent_key is None:
                self.agent_results.clear()
                logger.debug(f"Cleared all results in session {self.session_id}")
            else:
                self.agent_results.pop(agent_key, None)
                logger.debug(f"Cleared {agent_key} result in session {self.session_id}")

    async def clear_conversation(self) -> None:
        """Clear conversation context by removing agent instances and results."""
        async with self._lock:
            self.agents.clear()
            self.agent_results.clear()
            logger.debug(f"Cleared conversation context (agents and results) in session {self.session_id}")

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

    async def create_session(self, progress_handler: ProgressHandler) -> str:
        """Create a new session and return session ID."""
        session_id = str(uuid.uuid4())
        session = AgentSession(session_id, self.openai_client, progress_handler)

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

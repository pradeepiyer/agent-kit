"""Test session management functionality."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from agents.hello.agent import HelloAgent
from agent_kit.api.core import AgentSession, SessionStore
from agent_kit.api.progress import NoOpProgressHandler


@pytest.mark.asyncio
async def test_create_and_get_session(mock_openai_client: AsyncMock) -> None:
    """Session creates and retrieves correctly."""
    store = SessionStore(mock_openai_client, default_ttl=3600)

    session_id = await store.create_session(NoOpProgressHandler())

    assert session_id is not None
    session = await store.get_session(session_id)
    assert session is not None
    assert session.session_id == session_id


@pytest.mark.asyncio
async def test_get_nonexistent_session_returns_none(mock_openai_client: AsyncMock) -> None:
    """Getting nonexistent session returns None."""
    store = SessionStore(mock_openai_client)

    session = await store.get_session("nonexistent-id")

    assert session is None


@pytest.mark.asyncio
async def test_agent_creates_lazily_and_reuses(mock_openai_client: AsyncMock) -> None:
    """Agent creates lazily and reuses on subsequent calls."""
    session = AgentSession("test-session", mock_openai_client, NoOpProgressHandler())

    # First call creates agent
    agent1 = await session.use_agent(HelloAgent)
    assert agent1 is not None

    # Second call reuses same agent
    agent2 = await session.use_agent(HelloAgent)
    assert agent1 is agent2


@pytest.mark.asyncio
async def test_session_expiration(mock_openai_client: AsyncMock) -> None:
    """Session expires after TTL."""
    session = AgentSession("test-session", mock_openai_client, NoOpProgressHandler())

    # Set last_accessed to past
    session.last_accessed = datetime.now() - timedelta(seconds=3700)

    is_expired = await session.is_expired(ttl_seconds=3600)

    assert is_expired is True


@pytest.mark.asyncio
async def test_session_not_expired_within_ttl(mock_openai_client: AsyncMock) -> None:
    """Session not expired within TTL."""
    session = AgentSession("test-session", mock_openai_client, NoOpProgressHandler())

    # Set last_accessed to recent
    session.last_accessed = datetime.now() - timedelta(seconds=100)

    is_expired = await session.is_expired(ttl_seconds=3600)

    assert is_expired is False


@pytest.mark.asyncio
async def test_store_and_retrieve_result(mock_openai_client: AsyncMock) -> None:
    """Result stores and retrieves correctly."""
    session = AgentSession("test-session", mock_openai_client, NoOpProgressHandler())

    await session.store_result("HelloAgent", "test result", extra="metadata")

    result = await session.get_result("HelloAgent")

    assert result is not None
    assert result["result"] == "test result"
    assert result["extra"] == "metadata"
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_clear_specific_result(mock_openai_client: AsyncMock) -> None:
    """Clearing specific result works correctly."""
    session = AgentSession("test-session", mock_openai_client, NoOpProgressHandler())

    await session.store_result("HelloAgent", "result1")
    await session.clear_results("HelloAgent")

    result = await session.get_result("HelloAgent")

    assert result is None


@pytest.mark.asyncio
async def test_clear_all_results(mock_openai_client: AsyncMock) -> None:
    """Clearing all results works correctly."""
    session = AgentSession("test-session", mock_openai_client, NoOpProgressHandler())

    await session.store_result("HelloAgent", "result1")
    await session.clear_results()

    result = await session.get_result("HelloAgent")

    assert result is None


@pytest.mark.asyncio
async def test_cleanup_expired_sessions(mock_openai_client: AsyncMock) -> None:
    """Expired sessions cleanup correctly."""
    store = SessionStore(mock_openai_client, default_ttl=1)

    # Create sessions
    session_id1 = await store.create_session(NoOpProgressHandler())
    session_id2 = await store.create_session(NoOpProgressHandler())

    # Make first session old
    session1 = await store.get_session(session_id1)
    if session1:
        session1.last_accessed = datetime.now() - timedelta(seconds=10)

    # Cleanup expired
    count = await store.cleanup_expired()

    # First session expired, second still active
    assert count == 1
    assert await store.get_session(session_id1) is None
    assert await store.get_session(session_id2) is not None


@pytest.mark.asyncio
async def test_delete_session(mock_openai_client: AsyncMock) -> None:
    """Session deletes correctly."""
    store = SessionStore(mock_openai_client)

    session_id = await store.create_session(NoOpProgressHandler())
    deleted = await store.delete_session(session_id)

    assert deleted is True
    assert await store.get_session(session_id) is None


@pytest.mark.asyncio
async def test_delete_nonexistent_session_returns_false(mock_openai_client: AsyncMock) -> None:
    """Deleting nonexistent session returns False."""
    store = SessionStore(mock_openai_client)

    deleted = await store.delete_session("nonexistent-id")

    assert deleted is False


@pytest.mark.asyncio
async def test_session_count(mock_openai_client: AsyncMock) -> None:
    """Session count tracks correctly."""
    store = SessionStore(mock_openai_client)

    count_before = await store.get_session_count()
    await store.create_session(NoOpProgressHandler())
    await store.create_session(NoOpProgressHandler())
    count_after = await store.get_session_count()

    assert count_after == count_before + 2


@pytest.mark.asyncio
async def test_concurrent_agent_creation(mock_openai_client: AsyncMock) -> None:
    """Concurrent agent creation handled safely."""
    session = AgentSession("test-session", mock_openai_client, NoOpProgressHandler())

    # Try to create same agent concurrently
    agents = await asyncio.gather(
        session.use_agent(HelloAgent), session.use_agent(HelloAgent), session.use_agent(HelloAgent)
    )

    # All should be the same agent instance
    assert agents[0] is agents[1]
    assert agents[1] is agents[2]


@pytest.mark.asyncio
async def test_update_last_active_agent(mock_openai_client: AsyncMock) -> None:
    """Last active agent updates correctly."""
    session = AgentSession("test-session", mock_openai_client, NoOpProgressHandler())

    await session.update_last_active("HelloAgent")

    assert session.last_active_agent == "HelloAgent"

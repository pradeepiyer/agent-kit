"""
Base client utilities for responses-agent.

Provides connection pooling and OpenAI client factory.
"""

import asyncio
import inspect
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


# ============= Section 1: Connection Pool =============


@dataclass
class PooledConnection:
    """Represents a pooled client connection."""

    client: Any
    request_count: int = 0
    is_in_use: bool = False
    error_count: int = 0
    consecutive_errors: int = 0
    unhealthy_until: float | None = None

    def record_success(self) -> None:
        """Record successful request."""
        self.request_count, self.consecutive_errors, self.unhealthy_until = self.request_count + 1, 0, None

    def record_error(self) -> None:
        """Record failed request."""
        self.error_count, self.consecutive_errors = self.error_count + 1, self.consecutive_errors + 1
        self.unhealthy_until = time.monotonic() + 10.0 if self.consecutive_errors >= 3 else self.unhealthy_until


class ConnectionFactory(ABC):
    """Abstract factory for creating client connections."""

    @abstractmethod
    async def create_client(self, http_client: httpx.AsyncClient | None = None) -> Any:
        """Create a new client instance."""
        ...

    @property
    @abstractmethod
    def pool_size(self) -> int:
        """Get the pool size."""
        pass

    @property
    @abstractmethod
    def request_timeout(self) -> int:
        """Get the request timeout."""
        pass


class ConnectionPool:
    """Generic connection pool with round-robin load balancing."""

    def __init__(self, factory: ConnectionFactory):
        self.factory = factory
        self.connections: list[PooledConnection] = []
        self.current_index = 0
        self.pool_condition = asyncio.Condition()
        self.is_initialized = False
        self.shared_http_client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        async with self.pool_condition:
            if self.is_initialized:
                return
            logger.info(f"Initializing connection pool with {self.factory.pool_size} connections")
            self.shared_http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.factory.request_timeout),
                limits=httpx.Limits(
                    max_connections=self.factory.pool_size * 2, max_keepalive_connections=self.factory.pool_size
                ),
            )
            self.connections = [await self._create_connection() for _ in range(self.factory.pool_size)]
            self.is_initialized = True
            logger.info(f"Connection pool initialized with {len(self.connections)} connections")

    async def get_connection(self) -> PooledConnection:
        """Get next connection using round-robin with timeout protection."""
        if not self.is_initialized:
            await self.initialize()
        loop = asyncio.get_running_loop()
        start_time = loop.time()
        timeout = self.factory.request_timeout
        while True:
            async with self.pool_condition:
                now = time.monotonic()
                for _ in range(len(self.connections)):
                    conn = self.connections[self.current_index]
                    self.current_index = (self.current_index + 1) % len(self.connections)
                    if not conn.is_in_use and (conn.unhealthy_until is None or now >= conn.unhealthy_until):
                        conn.is_in_use = True
                        return conn
                if (elapsed := loop.time() - start_time) >= timeout:
                    raise TimeoutError(
                        f"All {len(self.connections)} connections are busy after waiting {elapsed:.1f}s (timeout: {timeout}s)"
                    )
                try:
                    await asyncio.wait_for(self.pool_condition.wait(), timeout=min(1.0, timeout - elapsed))
                except TimeoutError:
                    pass

    async def return_connection(self, conn: PooledConnection) -> None:
        """Return connection to pool and notify waiters."""
        async with self.pool_condition:
            conn.is_in_use = False
            self.pool_condition.notify_all()  # Wake all waiters to fairly compete

    async def _create_connection(self) -> PooledConnection:
        """Create a new pooled connection."""
        client = await self.factory.create_client(self.shared_http_client)
        return PooledConnection(client=client)

    async def close(self) -> None:
        """Close all connections and cleanup."""
        async with self.pool_condition:
            for conn in self.connections:
                try:
                    if hasattr(conn.client, "aclose") and callable(conn.client.aclose):
                        await conn.client.aclose()  # type: ignore[misc]
                    elif hasattr(conn.client, "close") and callable(close_method := conn.client.close):
                        await close_method() if inspect.iscoroutinefunction(close_method) else close_method()
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
            if self.shared_http_client:
                try:
                    await self.shared_http_client.aclose()
                except Exception as e:
                    logger.warning(f"Error closing shared HTTP client: {e}")
                finally:
                    self.shared_http_client = None
            self.connections.clear()
            self.is_initialized = False
        logger.info("Connection pool closed")


# ============= Section 2: OpenAI Connection Factory =============


class OpenAIConnectionFactory(ConnectionFactory):
    """Factory for creating OpenAI client connections."""

    def __init__(self, config: Any) -> None:
        from ..config.models import OpenAIConfig

        self.config: OpenAIConfig = config
        self._openai_class = AsyncOpenAI

    async def create_client(self, http_client: httpx.AsyncClient | None = None) -> Any:
        """Create OpenAI client."""
        return self._openai_class(
            api_key=self.config.api_key,
            timeout=self.config.request_timeout,
            max_retries=self.config.retry_attempts,
            http_client=http_client,
        )

    @property
    def pool_size(self) -> int:
        return int(self.config.pool_size)

    @property
    def request_timeout(self) -> int:
        return int(self.config.request_timeout)

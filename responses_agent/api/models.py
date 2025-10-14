"""Data models for Hello Agent API."""

from enum import Enum


class AgentType(str, Enum):
    """Supported agent types in Hello Agent."""

    HELLO = "hello"

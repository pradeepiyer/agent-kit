"""Custom exceptions for Hello Agent."""


class HelloAgentError(Exception):
    """Base exception for all Hello Agent errors."""

    pass


class ClientError(HelloAgentError):
    """Base exception for client errors."""

    pass

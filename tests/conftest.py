"""Shared test fixtures and mocks for agent-kit tests."""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Temporary directory for config files."""
    return tmp_path / "config"


@pytest.fixture
def temp_prompts_dir(tmp_path: Path) -> Path:
    """Temporary directory for prompt files."""
    return tmp_path / "prompts"


@pytest.fixture
def sample_config_dict() -> dict[str, Any]:
    """Sample configuration dictionary for testing."""
    return {
        "connection": {"pool_size": 2, "request_timeout": 60, "retry_attempts": 2},
        "openai": {
            "api_key": "test-key",
            "model": "gpt-5-mini",
            "pool_size": 2,
            "request_timeout": 60,
            "retry_attempts": 2,
            "reasoning_effort": "medium",
            "reasoning_summary": False,
            "output_token_ratio": 0.25,
            "model_limits": {"gpt-5-mini": 400000, "default": 128000},
            "function_models": {},
            "function_reasoning": {},
            "debug_prompts": {"enabled": False, "directory": "/tmp/test", "max_files": 10},
        },
        "logging": {
            "level": "INFO",
            "format": "%(message)s",
            "datefmt": "%H:%M:%S",
            "max_file_size": 1048576,
            "backup_count": 2,
        },
        "agents": {"max_iterations": 10, "max_parallel_tools": 3},
        "hello": {"max_iterations": 5},
    }


@pytest.fixture
def sample_prompt_yaml() -> str:
    """Sample prompt YAML content for testing."""
    return """agent: hello
function: orchestrator
parameters: []
prompt:
  instructions: |
    # Hello Agent
    You are a friendly assistant.
    Greet the user warmly.
"""


@pytest.fixture
def mock_openai_response() -> MagicMock:
    """Mock OpenAI Responses API response."""
    response = MagicMock()
    response.id = "resp_test123"
    response.status = "complete"
    response.output_text = "Hello! How can I help you today?"
    response.output = [MagicMock(type="text", text="Hello! How can I help you today?")]
    response.usage = MagicMock(
        input_tokens=100, output_tokens=50, total_tokens=150, input_tokens_details=None, output_tokens_details=None
    )
    return response


@pytest.fixture
def mock_openai_response_with_tools() -> MagicMock:
    """Mock OpenAI response with tool calls."""
    response = MagicMock()
    response.id = "resp_test456"
    response.status = "complete"

    # Tool call
    tool_call = MagicMock()
    tool_call.type = "function_call"
    tool_call.name = "get_current_time"
    tool_call.arguments = "{}"
    tool_call.call_id = "call_123"

    response.output = [tool_call]
    response.output_text = None
    response.usage = MagicMock(
        input_tokens=100, output_tokens=50, total_tokens=150, input_tokens_details=None, output_tokens_details=None
    )
    return response


@pytest.fixture
def mock_openai_client(mock_openai_response: MagicMock) -> AsyncMock:
    """Mock OpenAI client with Responses API."""
    client = AsyncMock()

    # Mock responses.create method
    client.responses.create = AsyncMock(return_value=mock_openai_response)

    # Mock connection pool behavior
    client.aclose = AsyncMock()

    return client


@pytest.fixture
def mock_openai_client_config() -> MagicMock:
    """Mock OpenAI client config for connection factory."""
    config = MagicMock()
    config.api_key = "test-key"
    config.model = "gpt-5-mini"
    config.pool_size = 2
    config.request_timeout = 60
    config.retry_attempts = 2
    config.reasoning_effort = "medium"
    config.reasoning_summary = False
    config.output_token_ratio = 0.25
    config.model_limits = {"gpt-5-mini": 400000, "default": 128000}
    config.function_models = {}
    config.function_reasoning = {}
    config.debug_prompts = MagicMock(enabled=False, directory="/tmp/test", max_files=10)
    return config


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

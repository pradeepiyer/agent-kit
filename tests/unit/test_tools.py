"""Test tool functionality."""

import pytest

from agent_kit.agents.hello.tools import execute_tool, get_current_time, get_tool_definitions


@pytest.mark.asyncio
async def test_get_current_time_returns_time_info() -> None:
    """get_current_time returns correct time information."""
    result = await get_current_time()

    assert "current_time" in result
    assert "current_date" in result
    assert "day_of_week" in result
    assert "timezone" in result

    # Verify formats
    assert ":" in result["current_time"]  # Should have time format HH:MM:SS
    assert "-" in result["current_date"]  # Should have date format YYYY-MM-DD


@pytest.mark.asyncio
async def test_execute_tool_get_current_time() -> None:
    """execute_tool calls get_current_time correctly."""
    result = await execute_tool("get_current_time", {})

    assert "current_time" in result
    assert "current_date" in result


@pytest.mark.asyncio
async def test_execute_tool_unknown_raises_error() -> None:
    """execute_tool raises ValueError for unknown tools."""
    with pytest.raises(ValueError, match="Unknown tool"):
        await execute_tool("nonexistent_tool", {})


def test_get_tool_definitions_returns_list() -> None:
    """get_tool_definitions returns list of tool definitions."""
    tools = get_tool_definitions()

    assert isinstance(tools, list)
    assert len(tools) > 0


def test_get_tool_definitions_has_web_search() -> None:
    """Tool definitions include web_search."""
    tools = get_tool_definitions()

    web_search = next((t for t in tools if t.get("type") == "web_search"), None)

    assert web_search is not None
    assert web_search["type"] == "web_search"


def test_get_tool_definitions_has_get_current_time() -> None:
    """Tool definitions include get_current_time function."""
    tools = get_tool_definitions()

    time_tool = next((t for t in tools if t.get("name") == "get_current_time"), None)

    assert time_tool is not None
    assert time_tool["type"] == "function"
    assert "description" in time_tool
    assert "parameters" in time_tool


def test_tool_definitions_structure() -> None:
    """Tool definitions have correct structure."""
    tools = get_tool_definitions()

    for tool in tools:
        assert "type" in tool
        if tool["type"] == "function":
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
        elif tool["type"] == "web_search":
            # web_search tools have different structure
            assert "search_context_size" in tool

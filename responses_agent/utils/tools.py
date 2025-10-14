"""Tools for Hello Agent."""

from datetime import datetime
from typing import Any


async def get_current_time() -> dict[str, str]:
    """Get the current time.

    Returns:
        Dictionary with current time information.
    """
    now = datetime.now()
    return {
        "current_time": now.strftime("%I:%M:%S %p"),
        "current_date": now.strftime("%Y-%m-%d"),
        "day_of_week": now.strftime("%A"),
        "timezone": now.astimezone().tzname() or "UTC",
    }


def get_tool_definitions() -> list[dict[str, Any]]:
    """Get tool definitions for OpenAI API.

    Returns:
        List of tool definitions in OpenAI format.
    """
    return [
        {
            "type": "web_search",
            "description": "Search the web for current information, recent updates, documentation, and topics beyond your knowledge cutoff. Use this to find up-to-date answers, verify facts, or gather additional context.",
            "search_context_size": "high",
        },
        {
            "type": "function",
            "name": "get_current_time",
            "description": "Get the current time, date, and day of the week",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    ]


async def execute_tool(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name.

    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments for the tool

    Returns:
        Tool execution result

    Raises:
        ValueError: If tool name is unknown
    """
    if tool_name == "get_current_time":
        return await get_current_time()
    raise ValueError(f"Unknown tool: {tool_name}")

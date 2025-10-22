"""Tools for Hello Agent."""

from datetime import datetime
from typing import Any


async def get_current_time() -> dict[str, str]:
    """Get the current time."""
    now = datetime.now()
    return {
        "current_time": now.strftime("%I:%M:%S %p"),
        "current_date": now.strftime("%Y-%m-%d"),
        "day_of_week": now.strftime("%A"),
        "timezone": now.astimezone().tzname() or "UTC",
    }


def get_tool_definitions() -> list[dict[str, Any]]:
    """Get tool definitions for OpenAI API."""
    return [
        {"type": "web_search", "search_context_size": "high"},
        {
            "type": "function",
            "name": "get_current_time",
            "description": "Get the current time, date, and day of the week",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    ]


async def execute_tool(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name."""
    if tool_name == "get_current_time":
        return await get_current_time()
    raise ValueError(f"Unknown tool: {tool_name}")

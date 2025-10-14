"""Utilities for debugging prompts sent to OpenAI API."""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from agent_kit.config.models import DebugPromptConfig

logger = logging.getLogger(__name__)


def format_tool_output(output_str: str) -> list[str]:
    """Format tool output in human-readable form."""
    try:
        data: dict[str, Any] = json.loads(output_str)
        lines: list[str] = []

        # Handle success/error status first
        if "error" in data:
            lines.append(f"  ✗ Error: {data['error']}")
        elif "success" in data:
            status = "✓" if data["success"] else "✗"
            if not data["success"] and "error" in data:
                lines.append(f"  {status} Error: {data['error']}")
            else:
                lines.append(f"  {status} {data.get('message', 'Operation completed')}")

        # Handle remaining fields
        for key, value in data.items():
            if key in ["success", "message", "error"]:
                continue

            if isinstance(value, list) and value:
                formatted_key = key.replace("_", " ").title()
                value_list: list[Any] = value  # type: ignore[assignment]
                lines.append(f"  {formatted_key}: ({len(value_list)} items)")

                for item in value_list[:5]:
                    if isinstance(item, dict):
                        item_parts = [f"{k}: {v}" for k, v in item.items() if isinstance(v, str | int | float | bool)]  # type: ignore[attr-defined]
                        if item_parts:
                            lines.append(f"    • {', '.join(item_parts)}")
                    else:
                        lines.append(f"    • {item}")

                if len(value_list) > 5:
                    lines.append(f"    ... and {len(value_list) - 5} more")

            elif isinstance(value, dict) and value:
                formatted_key = key.replace("_", " ").title()
                lines.append(f"  {formatted_key}:")
                for k, v in value.items():  # type: ignore[attr-defined]
                    lines.append(f"    • {k}: {v}")

            elif isinstance(value, int | float):
                formatted_key = key.replace("_", " ")
                lines.append(
                    f"  • {formatted_key}: {value:,}"
                    if isinstance(value, int) and value > 1000
                    else f"  • {formatted_key}: {value}"
                )

            elif isinstance(value, bool):
                formatted_key = key.replace("_", " ")
                lines.append(f"  • {formatted_key}: {'Yes' if value else 'No'}")

            elif value:  # Skip None/empty values
                lines.append(f"  • {key.replace('_', ' ')}: {value}")

        return lines if lines else ["  " + output_str]

    except (json.JSONDecodeError, TypeError):
        return ["  " + output_str]


async def cleanup_old_files(directory: Path, max_files: int) -> None:
    """Clean up old prompt files, keeping only the most recent ones."""
    try:
        files = sorted(directory.glob("*.txt"), key=lambda f: f.stat().st_mtime)
        if len(files) > max_files:
            for file in files[: len(files) - max_files]:
                try:
                    file.unlink()
                    logger.debug(f"Removed old prompt file: {file.name}")
                except Exception as e:
                    logger.warning(f"Failed to remove old prompt file {file.name}: {e}")
    except Exception as e:
        logger.warning(f"Failed to cleanup old prompt files: {e}")


async def save_prompt_debug(
    config: DebugPromptConfig,
    timestamp: datetime,
    agent_type: str,
    iteration: int,
    model: str,
    instructions: str | None,
    input_messages: list[dict[str, Any]] | str,
    tools: list[dict[str, Any]] | None,
    max_output_tokens: int | None,
    previous_response_id: str | None,
    response: Any | None = None,
) -> Path | None:
    """Save prompt debug information to a file."""
    if not config.enabled:
        return None

    try:
        debug_dir = Path(config.directory)
        debug_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{agent_type}_iter-{iteration:02d}_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        debug_file_path = debug_dir / filename

        lines: list[str] = ["=" * 80, "HELLO AGENT PROMPT DEBUG", "=" * 80]
        lines.append(f"Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')}")
        lines.append(f"Agent: {agent_type}")
        lines.append(f"Iteration: {iteration}")
        lines.append(f"Model: {model}")
        if max_output_tokens:
            lines.append(f"Max Output Tokens: {max_output_tokens:,}")
        if previous_response_id:
            lines.append(f"Previous Response ID: {previous_response_id} (follow-up)")
        lines.append("")

        # Instructions
        if instructions:
            lines.extend(["=" * 80, "INSTRUCTIONS", "=" * 80, instructions, ""])

        # Input Messages
        lines.extend(["=" * 80, "INPUT MESSAGES", "=" * 80])

        if isinstance(input_messages, str):
            lines.extend(["[1] USER:", input_messages])
        elif input_messages:
            for i, msg in enumerate(input_messages, 1):
                if "type" in msg and msg["type"] == "function_call_output":
                    lines.append(f"[{i}] TOOL OUTPUT (call_id: {msg.get('call_id', 'unknown')}):")
                    lines.extend(format_tool_output(msg.get("output", "")))
                elif "role" in msg:
                    role = msg.get("role", "unknown").upper()
                    content = msg.get("content", "")

                    if role == "TOOL":
                        lines.extend([f"[{i}] TOOL RESPONSE (call_id: {msg.get('tool_call_id', 'unknown')}):", content])
                    else:
                        lines.append(f"[{i}] {role}:")
                        if role == "ASSISTANT" and msg.get("tool_calls"):
                            if content:
                                lines.append(content)
                            lines.append("\nTool Calls:")
                            for tc in msg["tool_calls"]:
                                func = tc.get("function", {})
                                lines.append(f"  - {func.get('name', 'unknown')}({func.get('arguments', '')})")
                        else:
                            lines.append(content)
                else:
                    lines.extend([f"[{i}] UNKNOWN FORMAT:", str(msg)])
                lines.append("")
        else:
            lines.append("(No input messages)")
        lines.append("")

        # Tools
        if tools:
            lines.extend(["=" * 80, "TOOLS", "=" * 80])
            for tool in tools:
                lines.append(f"Tool: {tool.get('name', 'unknown')}")
                if desc := tool.get("description"):
                    lines.append(f"Description: {desc}")

                if params := tool.get("parameters", {}).get("properties", {}):
                    lines.append("Parameters:")
                    required = tool.get("parameters", {}).get("required", [])
                    for param_name, param_info in params.items():
                        req_marker = "required" if param_name in required else "optional"
                        lines.append(
                            f"  - {param_name} ({param_info.get('type', 'unknown')}) ({req_marker}): {param_info.get('description', '')}"
                        )
                lines.append("")

        # Response (if included)
        if response:
            lines.extend(["=" * 80, "RESPONSE", "=" * 80])

            if hasattr(response, "id"):
                lines.append(f"Response ID: {response.id}")
            if hasattr(response, "status"):
                lines.append(f"Status: {response.status}")

            if hasattr(response, "output_text"):
                lines.extend(["\nOutput:", response.output_text or "(No output text)"])

            if hasattr(response, "output") and response.output:
                output = response.output
                if hasattr(output, "tool_calls") and output.tool_calls:
                    lines.append("\nTool Calls Made:")
                    for i, tc in enumerate(output.tool_calls, 1):
                        func = tc.function if hasattr(tc, "function") else tc.get("function", {})
                        name = func.name if hasattr(func, "name") else func.get("name", "unknown")
                        args = func.arguments if hasattr(func, "arguments") else func.get("arguments", "")
                        lines.append(f"{i}. {name}({args})")

            lines.append("")

        lines.extend(["=" * 80, "END OF PROMPT DEBUG", "=" * 80])

        async with aiofiles.open(debug_file_path, "w") as f:
            await f.write("\n".join(lines))

        logger.debug(f"Saved prompt debug to: {debug_file_path}")

        # Cleanup old files (fire and forget)
        cleanup_task = asyncio.create_task(cleanup_old_files(debug_dir, config.max_files))
        cleanup_task.add_done_callback(lambda _: None)

        return debug_file_path

    except Exception as e:
        logger.warning(f"Failed to save prompt debug: {e}")
        return None

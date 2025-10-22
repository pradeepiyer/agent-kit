# Progress handler protocol and concrete implementations for different interfaces

import asyncio
import json
from datetime import datetime
from typing import Any, Protocol

from rich.console import Console


class ProgressHandler(Protocol):
    """Protocol for progress reporting across different interfaces."""

    async def emit(self, message: str, stage: str = "") -> None:
        """Emit a progress message."""
        ...


class ConsoleProgressHandler:
    """Progress handler for interactive console using Rich."""

    def __init__(self, console: Console):
        self.console = console

    async def emit(self, message: str, stage: str = "") -> None:
        """Emit progress to console."""
        if stage == "reasoning":
            self.console.print(f"[dim cyan]💭 {message}[/dim cyan]")
        else:
            self.console.print(f"[dim]⏳ {message}[/dim]")


class RESTProgressHandler:
    """Progress handler for REST API with SSE streaming via asyncio queue."""

    def __init__(self, queue: asyncio.Queue[dict[str, Any]]):
        """Initialize with asyncio queue for event streaming."""
        self.queue = queue

    async def emit(self, message: str, stage: str = "") -> None:
        """Emit progress event to queue."""
        await self.queue.put(
            {
                "type": "reasoning" if stage == "reasoning" else "progress",
                "message": message,
                "stage": stage,
                "timestamp": datetime.now().isoformat(),
            }
        )


class MCPProgressHandler:
    """Progress handler for MCP protocol using Context.report_progress()."""

    def __init__(self, ctx: Any):  # ctx: Context from fastmcp
        self.ctx = ctx
        self.progress_count = 0

    async def emit(self, message: str, stage: str = "") -> None:
        """Emit progress via MCP Context."""
        self.progress_count += 1
        clean_msg = json.dumps(f"{stage}: {message}" if stage else message)[1:-1]
        await self.ctx.report_progress(progress=float(self.progress_count), total=100.0, message=clean_msg)


class NoOpProgressHandler:
    """No-op progress handler for testing or when progress is disabled."""

    async def emit(self, message: str, stage: str = "") -> None:
        """No-op implementation."""
        pass

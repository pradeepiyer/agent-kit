"""Progress handler system with contextvar-based routing."""

import logging
from contextvars import ContextVar
from typing import Protocol

logger = logging.getLogger(__name__)


class ProgressHandler(Protocol):
    """Progress event handler."""

    async def emit(self, message: str, stage: str = "") -> None:
        """Simple progress message."""
        ...


_progress_context: ContextVar[ProgressHandler | None] = ContextVar("progress", default=None)


def set_progress_handler(handler: ProgressHandler) -> None:
    """Set progress handler for current context."""
    _progress_context.set(handler)


def get_progress_handler() -> ProgressHandler:
    """Get current progress handler, raises if not set."""
    handler = _progress_context.get()
    if handler is None:
        raise RuntimeError("Progress handler not set. Each interface must call set_progress_handler().")
    return handler


async def emit_progress(message: str, stage: str = "") -> None:
    """Emit progress update via configured handler."""
    logger.info(f"[Progress] {f'{stage}: ' if stage else ''}{message}")
    handler = get_progress_handler()
    await handler.emit(message, stage)

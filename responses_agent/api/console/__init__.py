"""Enhanced console interface for Hello Agent.

Provides modern terminal UX patterns including enhanced prompts,
file references, and slash commands.
"""

from rich.console import Console

from .prompt import Prompt
from .server import SlashCommands, run_console

# Singleton console instance
_console: Console | None = None


def get_console() -> Console:
    """Get the shared console instance."""
    global _console
    if _console is None:
        _console = Console()
    return _console


def set_console(console: Console) -> None:
    """Set the shared console instance (call once at application startup)."""
    global _console
    _console = console


__all__ = ["Prompt", "SlashCommands", "get_console", "run_console", "set_console"]

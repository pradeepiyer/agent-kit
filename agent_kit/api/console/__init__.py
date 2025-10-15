"""Enhanced console interface for Hello Agent.

Provides modern terminal UX patterns including enhanced prompts,
file references, and slash commands.
"""

from .prompt import Prompt
from .server import SlashCommands, get_console, run_console, set_console

__all__ = ["Prompt", "SlashCommands", "get_console", "run_console", "set_console"]

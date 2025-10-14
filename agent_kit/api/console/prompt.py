"""Simplified interactive prompt using readline for completion."""

import os
import readline
import select
import sys
import termios
from pathlib import Path

from rich.console import Console

from agent_kit.api.console.server import SlashCommands


class Prompt:
    """Interactive prompt with readline-based completion."""

    def __init__(self, console: Console | None = None):
        """Initialize the enhanced prompt."""
        self.console = console or Console()
        self.slash_commands = list(SlashCommands.COMMANDS.keys())
        self.file_extensions = [".py"]
        self._setup_readline()

    def _setup_readline(self) -> None:
        """Set up readline with tab completion."""
        try:
            readline.set_completer(self._readline_completer)
            # Different bindings for macOS (libedit) vs Linux (GNU readline)
            if readline.__doc__ and "libedit" in readline.__doc__:
                readline.parse_and_bind("bind ^I rl_complete")
            else:
                readline.parse_and_bind("tab: complete")
            readline.set_completer_delims(" \t\n")

            # Set up history file
            histfile = os.path.join(os.path.expanduser("~/.agent-kit"), ".history")
            os.makedirs(os.path.dirname(histfile), exist_ok=True)
            try:
                readline.read_history_file(histfile)
                readline.set_history_length(1000)
            except (FileNotFoundError, PermissionError):
                pass

            import atexit

            atexit.register(readline.write_history_file, histfile)

        except (ImportError, AttributeError):
            pass

    def _readline_completer(self, text: str, state: int) -> str | None:
        """Readline completer function."""
        completions: list[str] = []

        if text.startswith("/"):
            completions = [cmd + " " for cmd in self.slash_commands if cmd.startswith(text)]
        elif text.startswith("@"):
            completions = ["@" + comp for comp in self._get_file_completions(text[1:])]

        return completions[state] if state < len(completions) else None

    def get_input(self, prompt_text: str = "") -> str:
        """Get user input with completion support."""
        prompt_text = prompt_text or "> "

        try:
            user_input = input(prompt_text)

            if self._has_pending_input():
                user_input = self._read_multiline_paste(user_input)
            elif user_input.endswith("\\"):
                user_input = self._handle_multiline_input(user_input)

            return user_input.strip()

        except KeyboardInterrupt:
            print("\nCancelled")
            return ""
        except EOFError:
            raise

    def _has_pending_input(self) -> bool:
        """Check if there's pending input in stdin buffer."""
        try:
            return select.select([sys.stdin], [], [], 0)[0] != []
        except Exception:
            return False

    def _read_multiline_paste(self, first_line: str) -> str:
        """Read multiline pasted content from stdin."""
        lines = [first_line]

        try:
            import time

            time.sleep(0.01)

            while self._has_pending_input():
                if line := sys.stdin.readline():
                    lines.append(line.rstrip("\n\r"))
                else:
                    break

            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except Exception:
            pass

        return "\n".join(lines)

    def _handle_multiline_input(self, initial_input: str) -> str:
        """Handle multiline input with backslash continuation."""
        lines: list[str] = []
        current_input = initial_input

        while current_input.endswith("\\"):
            lines.append(current_input[:-1])
            current_input = input("... ")

        lines.append(current_input)
        return "".join(lines)

    def _get_completions(self, text: str) -> list[str]:
        """Get completion options for the given text."""
        completions: list[str] = []

        if text.startswith("/"):
            completions = [cmd for cmd in self.slash_commands if cmd.startswith(text)]
        elif text.startswith("@"):
            completions = ["@" + comp for comp in self._get_file_completions(text[1:])]

        return completions

    def _get_file_completions(self, text: str) -> list[str]:
        """Get file completions for the given text."""
        completions: list[str] = []

        try:
            text = os.path.expanduser(text) if text.startswith("~") else text

            if text.endswith("/"):
                base_path, pattern, prefix = Path(text), "*", text
            elif "/" in text:
                base_path, pattern, prefix = Path(text).parent, Path(text).name + "*", str(Path(text).parent) + "/"
            else:
                base_path, pattern, prefix = Path("."), (text + "*" if text else "*"), ""

            if base_path.exists():
                for path in base_path.glob(pattern):
                    if path.name.startswith("."):
                        continue
                    if path.is_dir():
                        completions.append(prefix + path.name + "/")
                    elif any(str(path).endswith(ext) for ext in self.file_extensions):
                        completions.append(prefix + path.name)

        except Exception:
            pass

        return sorted([c for c in completions if c])

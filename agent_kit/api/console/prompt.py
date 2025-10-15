"""Simplified interactive prompt using readline for completion."""

import os
import readline
import select
import sys
import termios

from rich.console import Console


class Prompt:
    """Interactive prompt with readline-based completion."""

    def __init__(self, console: Console | None = None, commands: dict[str, str] | None = None):
        """Initialize the enhanced prompt.

        Args:
            console: Rich console instance for output
            commands: Command dictionary for tab completion (defaults to empty)
        """
        self.console = console or Console()
        self.slash_commands = list(commands.keys()) if commands else []
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
        """Readline completer function for slash commands."""
        completions: list[str] = []

        if text.startswith("/"):
            completions = [cmd + " " for cmd in self.slash_commands if cmd.startswith(text)]

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

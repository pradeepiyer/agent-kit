"""Console server for interactive CLI interface."""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from importlib.resources import files
from pathlib import Path

from rich.console import Console
from rich.table import Table

from agent_kit.api.core import SessionStore
from agent_kit.api.progress import ConsoleProgressHandler
from agent_kit.config import setup_configuration
from agent_kit.config.config import close_all_clients, get_openai_client
from agent_kit.utils import get_user_dir

from .prompt import Prompt


logger = logging.getLogger(__name__)


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


class SlashCommands:
    """Handle slash commands for quick operations."""

    def __init__(self, console: Console):
        """Initialize slash commands handler."""
        self.console = console
        self.session_store = SessionStore(get_openai_client())
        self.session_id: str | None = None
        self.exit_requested = False

        # Command registry: {command: (handler, description, help_text)}
        self._command_registry: dict[str, tuple[Callable[[list[str]], Awaitable[None]], str, str]] = {}

        # Register framework commands
        self._register_framework_commands()

    async def initialize(self) -> None:
        """Async initialization for session creation."""
        progress_handler = ConsoleProgressHandler(self.console)
        self.session_id = await self.session_store.create_session(progress_handler)
        logger.info(f"SlashCommands initialized with session_id: {self.session_id}")
        session_count = await self.session_store.get_session_count()
        logger.info(f"SessionStore has {session_count} sessions")

    def register_command(
        self, command: str, handler: Callable[[list[str]], Awaitable[None]], description: str, help_text: str
    ) -> None:
        """Register a slash command with its handler and help text.

        Args:
            command: Command name (e.g., "/hello")
            handler: Async function that handles the command, takes args: list[str]
            description: Short description for command list
            help_text: Detailed help text shown with /help <command>
        """
        self._command_registry[command] = (handler, description, help_text)

    @property
    def COMMANDS(self) -> dict[str, str]:
        """Get all registered commands with descriptions (for tab completion)."""
        return {cmd: desc for cmd, (_, desc, _) in self._command_registry.items()}

    def _register_framework_commands(self) -> None:
        """Register framework slash commands."""
        self.register_command(
            "/help",
            self._handle_help,
            "Show available commands and usage",
            "Show available commands\nUsage: /help [command]",
        )
        self.register_command(
            "/init",
            self._handle_init,
            "Initialize configuration files",
            "Copy default configuration files to user directory\nUsage: /init",
        )
        self.register_command(
            "/clear", self._handle_clear, "Clear conversation context", "Clear conversation context (starts fresh conversation)\nUsage: /clear"
        )
        self.register_command("/exit", self._handle_exit, "Exit console", "Exit console\nUsage: /exit")

    def _sanitize_args(self, args: list[str]) -> list[str]:
        """Sanitize command arguments to prevent injection attacks."""
        return [re.sub(r'[;&|`$()\[\]{}"\']', "", arg)[:1000] for arg in args]

    async def handle_input(self, user_input: str) -> bool:
        """Handle slash commands via registry. Returns True if handled, False otherwise."""
        # Only handle slash commands
        if not user_input.startswith("/"):
            return False

        parts = user_input.strip().split()
        if not parts:
            return False

        cmd = parts[0].lower()
        args = self._sanitize_args(parts[1:] if len(parts) > 1 else [])

        # Route via command registry
        if cmd in self._command_registry:
            handler, _, _ = self._command_registry[cmd]
            await handler(args)
            return True

        # Unknown slash command - let subclass handle it
        return False

    def _print_help(self, args: list[str]) -> None:
        """Print help for available commands."""
        if args:
            cmd = args[0] if args[0].startswith("/") else "/" + args[0]
            if cmd in self._command_registry:
                _, _, help_text = self._command_registry[cmd]
                self.console.print(f"\n[bold cyan]{cmd}[/bold cyan]\n{help_text}\n")
            else:
                self.console.print(f"[red]Unknown command: {cmd}[/red]")
        else:
            table = Table(title="Available Commands")
            table.add_column("Command", style="cyan", width=15)
            table.add_column("Description", style="dim")

            for cmd, (_, desc, _) in self._command_registry.items():
                table.add_row(cmd, desc)

            self.console.print(table)
            self.console.print("\n[dim]Chat Mode:[/dim]")
            self.console.print("[dim]Type any message to start chatting[/dim]")

    async def _handle_help(self, args: list[str]) -> None:
        """Handle /help command (async wrapper for registry)."""
        self._print_help(args)

    def show_help(self) -> None:
        """Show help for all commands (public API for external callers)."""
        self._print_help([])

    async def _handle_init(self, args: list[str]) -> None:
        """Initialize configuration files by copying defaults to user directory."""
        user_dir = get_user_dir()
        user_dir.mkdir(parents=True, exist_ok=True)

        created_files: list[Path] = []
        skipped_files: list[Path] = []

        # Copy base config
        try:
            base_config_source = files("agent_kit.data.config") / "config.yaml"
            base_config_target = user_dir / "config.yaml"

            if base_config_target.exists():
                skipped_files.append(base_config_target)
            else:
                base_config_target.write_text(base_config_source.read_text(encoding="utf-8"), encoding="utf-8")
                created_files.append(base_config_target)
        except Exception as e:
            self.console.print(f"[red]Failed to copy base config: {e}[/red]")
            return

        # Copy all agent configs from ./agents/ directory
        agents_dir = Path.cwd() / "agents"
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
                    agent_name = agent_dir.name
                    agent_config_source = agent_dir / "config.yaml"

                    if agent_config_source.exists():
                        try:
                            agent_config_target = user_dir / f"{agent_name}.yaml"

                            if agent_config_target.exists():
                                skipped_files.append(agent_config_target)
                            else:
                                agent_config_target.write_text(
                                    agent_config_source.read_text(encoding="utf-8"), encoding="utf-8"
                                )
                                created_files.append(agent_config_target)
                        except Exception as e:
                            self.console.print(
                                f"[yellow]Warning: Failed to copy config for agent '{agent_name}': {e}[/yellow]"
                            )

        # Display results
        self.console.print()
        if created_files:
            for file_path in created_files:
                self.console.print(f"[green]✓[/green] Created {file_path}")

        if skipped_files:
            self.console.print()
            for file_path in skipped_files:
                self.console.print(f"[yellow]⊘[/yellow] Skipped {file_path} (already exists)")

        if created_files:
            self.console.print(f"\n[dim]Next steps: Customize agent settings in {user_dir}/*.yaml[/dim]")

        self.console.print()

    async def _handle_clear(self, args: list[str]) -> None:
        """Clear conversation context."""
        if not self.session_id:
            self.console.print("[red]Session not initialized[/red]")
            return
        session = await self.session_store.get_session(self.session_id)
        if session:
            await session.clear_conversation()
            self.console.print("[green]✓[/green] Cleared conversation context")
        else:
            self.console.print("[red]Session not found[/red]")

    async def _handle_exit(self, args: list[str]) -> None:
        """Handle exit command."""
        self.exit_requested = True
        self.console.print("[yellow]Goodbye![/yellow]")


async def run_console(commands_class: type[SlashCommands] = SlashCommands) -> None:
    """Run interactive console interface."""
    console = get_console()

    try:
        await setup_configuration()
    except Exception as e:
        console.print(f"[red]Error: Configuration setup failed: {e}[/red]")
        console.print("[dim]Please check your configuration and environment variables[/dim]")
        return

    slash_commands = commands_class(console)
    await slash_commands.initialize()
    prompt = Prompt(console, commands=slash_commands.COMMANDS)

    # Show help at startup
    slash_commands.show_help()

    while True:
        try:
            # Get input using enhanced prompt
            user_input = prompt.get_input()

            if not user_input:
                continue

            # Handle input via commands (slash commands or chat, depending on implementation)
            await slash_commands.handle_input(user_input)

            if slash_commands.exit_requested:
                await close_all_clients()
                break

        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled[/yellow]")
            continue
        except asyncio.CancelledError:
            console.print("\n[yellow]Operation cancelled[/yellow]")
            continue
        except EOFError:
            console.print("\n[yellow]Goodbye![/yellow]")
            await close_all_clients()
            break
        except Exception as e:
            console.print(f"[red]Error:[/red] {e!s}")
            error_str = str(e).lower()
            if "connection" in error_str or "initialization" in error_str:
                console.print(
                    "[yellow]There seems to be a connection issue. Please check your network and credentials.[/yellow]"
                )
                await close_all_clients()
                break

"""Console server for interactive CLI interface."""

import logging
import re
from typing import ClassVar

from rich.console import Console
from rich.table import Table

from responses_agent.api import AgentAPI

logger = logging.getLogger(__name__)


class ConsoleProgressHandler:
    """Terminal output via rich console."""

    async def emit(self, message: str, stage: str = "") -> None:
        """Emit simple progress message to console."""
        from responses_agent.api.console import get_console

        console = get_console()
        if stage == "reasoning":
            console.print(f"💭 [dim italic]{message}[/dim italic]")
        else:
            console.print(f"⚡ {message}")


class SlashCommands:
    """Handle slash commands for quick operations."""

    COMMANDS: ClassVar[dict[str, str]] = {
        "/hello": "Generate a personalized greeting",
        "/clear": "Clear session context",
        "/help": "Show available commands and usage",
        "/exit": "Exit Hello Agent",
    }

    def __init__(self, console: Console):
        """Initialize slash commands handler."""
        self.console = console
        self.agent_api = AgentAPI()
        self.session_id: str | None = None
        self.exit_requested = False

    async def initialize(self) -> None:
        """Async initialization for session creation."""
        self.session_id = await self.agent_api.session_store.create_session()
        logger.info(f"SlashCommands initialized with session_id: {self.session_id}")
        session_count = await self.agent_api.session_store.get_session_count()
        logger.info(f"SessionStore has {session_count} sessions")

    def _sanitize_args(self, args: list[str]) -> list[str]:
        """Sanitize command arguments to prevent injection attacks."""
        return [re.sub(r'[;&|`$()\[\]{}"\']', "", arg)[:1000] for arg in args]

    async def handle_input(self, user_input: str) -> bool:
        """Handle all agent inputs (slash commands and chat). Returns True if input was handled."""
        # Handle slash commands
        if user_input.startswith("/"):
            parts = user_input.strip().split()
            if not parts:
                return False

            cmd = parts[0].lower()
            args = self._sanitize_args(parts[1:] if len(parts) > 1 else [])

            if cmd == "/help":
                self.show_help(args)
                return True
            elif cmd == "/hello":
                await self._handle_hello(args)
                return True
            elif cmd == "/clear":
                await self._handle_clear()
                return True
            elif cmd == "/exit":
                self._handle_exit()
                return True
            else:
                self.console.print(f"[red]Unknown command: {cmd}[/red]")
                self.console.print("Type [cyan]/help[/cyan] to see available commands")
                return True

        # Handle regular chat input
        await self._handle_chat(user_input)
        return True

    def show_help(self, args: list[str]) -> None:
        """Show help for available commands."""
        if args:
            cmd = args[0] if args[0].startswith("/") else "/" + args[0]
            if cmd in self.COMMANDS:
                self._show_command_help(cmd)
        else:
            table = Table(title="Available Commands")
            table.add_column("Command", style="cyan", width=15)
            table.add_column("Description", style="dim")

            for cmd, desc in self.COMMANDS.items():
                table.add_row(cmd, desc)

            self.console.print(table)
            self.console.print("\n[dim]Chat Mode:[/dim]")
            self.console.print("[dim]Type any message to chat with Hello Agent (supports follow-up questions)[/dim]")
            self.console.print("[dim]Usage: /hello <name>[/dim]")

    def _show_command_help(self, command: str) -> None:
        """Show detailed help for a specific command."""
        help_text = {
            "/hello": "Generate a personalized greeting\nUsage: /hello <name>\nExample: /hello Alice",
            "/help": "Show available commands\nUsage: /help [command]",
            "/clear": "Clear all session context\nUsage: /clear",
            "/exit": "Exit Hello Agent\nUsage: /exit",
        }

        if command in help_text:
            self.console.print(f"\n[bold cyan]{command}[/bold cyan]\n{help_text[command]}\n")
        else:
            self.console.print(f"[red]No detailed help available for {command}[/red]")

    async def _handle_clear(self) -> None:
        """Clear all session context."""
        if not self.session_id:
            self.console.print("[red]Session not initialized[/red]")
            return
        session = await self.agent_api.session_store.get_session(self.session_id)
        if session:
            await session.clear_results()
            self.console.print("[green]✓[/green] Cleared all session context")
        else:
            self.console.print("[red]Session not found[/red]")

    def _handle_exit(self) -> None:
        """Handle exit command."""
        self.exit_requested = True
        self.console.print("[yellow]Goodbye![/yellow]")

    async def _handle_hello(self, args: list[str]) -> None:
        """Handle /hello command using AgentAPI."""
        if not args:
            self.console.print("[dim]Usage: /hello <name>[/dim]")
            return

        if not self.session_id:
            self.console.print("[red]Session not initialized[/red]")
            return

        name = args[0]

        self.console.print(f"[dim]▶ Generating greeting for {name}[/dim]")

        try:
            greeting = await self.agent_api.hello(name, self.session_id)
            self.console.print("\n[bold green]Hello Agent:[/bold green]")
            self.console.print(greeting, markup=False)
            self.console.print()
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")

    async def _handle_chat(self, query: str) -> None:
        """Handle chat input using AgentAPI."""
        if not self.session_id:
            self.console.print("[red]Session not initialized[/red]")
            return

        try:
            response = await self.agent_api.chat(query, self.session_id)
            self.console.print("\n[bold green]Hello Agent:[/bold green]")
            self.console.print(response, markup=False)
            self.console.print()
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")


async def run_console() -> None:
    """Run interactive console interface."""
    import asyncio

    from responses_agent.api.progress import set_progress_handler
    from responses_agent.config import setup_configuration
    from responses_agent.config.config import close_all_clients

    from . import get_console
    from .prompt import Prompt

    console = get_console()

    try:
        await setup_configuration()
    except Exception as e:
        console.print(f"[red]Error: Configuration setup failed: {e}[/red]")
        console.print("[dim]Please check your configuration and environment variables[/dim]")
        return

    # Set progress handler for console interface
    set_progress_handler(ConsoleProgressHandler())

    # Initialize enhanced console components
    prompt = Prompt(console)
    slash_commands = SlashCommands(console)
    await slash_commands.initialize()

    # Show help at startup
    slash_commands.show_help([])

    while True:
        try:
            # Get input using enhanced prompt
            user_input = prompt.get_input()

            if not user_input:
                continue

            # Handle slash commands and chat
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

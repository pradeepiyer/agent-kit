"""Console integration for Hello agent - demonstrates extension pattern."""

from typing import cast

from rich.console import Console

from agents.hello.agent import HelloAgent
from agent_kit.api.console.server import SlashCommands


class HelloCommands(SlashCommands):
    """Extended commands with Hello agent integration."""

    def __init__(self, console: Console):
        """Initialize Hello commands and register agent-specific commands."""
        super().__init__(console)

        # Register hello agent commands
        self.register_command(
            "/hello",
            self._handle_hello,
            "Generate a personalized greeting",
            "Generate a personalized greeting\nUsage: /hello <name>",
        )

    async def handle_input(self, user_input: str) -> bool:
        """Handle commands via registry, then fall back to chat."""
        # Try registered commands first (framework + agent)
        if await super().handle_input(user_input):
            return True

        # If it's an unknown slash command, show error
        if user_input.startswith("/"):
            cmd = user_input.split()[0] if user_input.split() else "/"
            self.console.print(f"[red]Unknown command: {cmd}[/red]")
            self.console.print("Type [cyan]/help[/cyan] to see available commands")
            return True

        # Handle non-command input as chat with HelloAgent
        await self._handle_chat(user_input)
        return True

    async def _handle_hello(self, args: list[str]) -> None:
        """Handle /hello command using HelloAgent."""
        if not args:
            self.console.print("[dim]Usage: /hello <name>[/dim]")
            return

        if not self.session_id:
            self.console.print("[red]Session not initialized[/red]")
            return

        name = args[0]
        self.console.print(f"[dim]▶ Generating greeting for {name}[/dim]")

        try:
            session = await self.session_store.get_session(self.session_id)
            if not session:
                self.console.print("[red]Session not found[/red]")
                return

            agent = cast(HelloAgent, await session.use_agent(HelloAgent))
            greeting = await agent.process(f"Greet {name}", continue_conversation=False)

            self.console.print("\n[bold green]Hello Agent:[/bold green]")
            self.console.print(greeting, markup=False)
            self.console.print()
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")

    async def _handle_chat(self, user_input: str) -> None:
        """Handle chat input using HelloAgent."""
        if not self.session_id:
            self.console.print("[red]Session not initialized[/red]")
            return

        try:
            session = await self.session_store.get_session(self.session_id)
            if not session:
                self.console.print("[red]Session not found[/red]")
                return

            agent = cast(HelloAgent, await session.use_agent(HelloAgent))
            response = await agent.process(user_input, continue_conversation=True)

            self.console.print("\n[bold green]Hello Agent:[/bold green]")
            self.console.print(response, markup=False)
            self.console.print()
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")

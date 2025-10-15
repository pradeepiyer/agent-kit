"""
Agent Kit CLI - Agent framework built on OpenAI Responses API.

Main entry point for the application with interactive chat mode.
"""

import asyncio
import logging
import sys
from importlib.resources import files
from pathlib import Path

import typer

from .agents.hello.console import HelloCommands
from .api.console import get_console, run_console

app = typer.Typer(name="agent-kit", help="Agent Framework built on OpenAI Responses API")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration"),
    with_examples: bool = typer.Option(True, "--examples/--no-examples", help="Copy example agent configs"),
):
    """Initialize Agent Kit configuration."""
    # Check if configuration already exists
    user_config_dir = Path.home() / ".agent-kit"
    config_file = user_config_dir / "config.yaml"

    if config_file.exists() and not force:
        get_console().print("[yellow]Configuration already exists.[/yellow] Use --force to overwrite.")
        return

    # Create configuration directory
    user_config_dir.mkdir(parents=True, exist_ok=True)

    get_console().print("[bold green]Agent Kit Configuration Setup[/bold green]\n")

    # Read the framework config template from package data
    config_resource = files("agent_kit.data.config") / "config.yaml"
    config_content = config_resource.read_text()

    # Write framework configuration
    config_file.write_text(config_content)
    get_console().print(f"[green]✓[/green] Framework config saved to {config_file}")

    # Optionally copy example agent configs
    if with_examples:
        try:
            # Copy hello agent config as example
            hello_config_resource = files("agent_kit.agents.hello") / "config.yaml"
            hello_config_file = user_config_dir / "hello.yaml"
            hello_config_file.write_text(hello_config_resource.read_text())
            get_console().print(f"[green]✓[/green] Example agent config saved to {hello_config_file}")
        except Exception as e:
            get_console().print(f"[yellow]⚠[/yellow] Could not copy example agent config: {e}")

    get_console().print("\n[bold]Next steps:[/bold]")
    get_console().print("1. Edit the configuration file to add your API keys or set them as environment variables")
    get_console().print(f"   Framework config: [cyan]{config_file}[/cyan]")
    if with_examples:
        get_console().print(f"   Agent configs: [cyan]{user_config_dir}/<agent-name>.yaml[/cyan]")
    get_console().print("2. Run [cyan]uv run agent-kit[/cyan] to start the interactive console")


def main():
    """Main entry point for the application."""

    # Configure basic logging
    logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")

    # Handle special case where no arguments are provided or it's a slash command
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1].startswith("/")):
        # Run in interactive mode with proper KeyboardInterrupt handling
        try:
            asyncio.run(run_console(HelloCommands))
        except KeyboardInterrupt:
            # Graceful shutdown on Ctrl+C
            get_console().print("\n[yellow]Shutdown requested. Goodbye![/yellow]")
            sys.exit(0)
    else:
        # Use Typer for command parsing
        app()


if __name__ == "__main__":
    main()

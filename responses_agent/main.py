"""
Responses Agent CLI - Agent framework built on OpenAI Responses API.

Main entry point for the application with interactive chat mode.
"""

import asyncio
import logging
import sys
from importlib.resources import files
from pathlib import Path

import typer

from .api.console import get_console, run_console

app = typer.Typer(name="responses-agent", help="Agent Framework built on OpenAI Responses API")


@app.command()
def init(force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration")):
    """Initialize Responses Agent configuration."""
    # Check if configuration already exists
    user_config_dir = Path.home() / ".responses-agent"
    config_file = user_config_dir / "config.yaml"

    if config_file.exists() and not force:
        get_console().print("[yellow]Configuration already exists.[/yellow] Use --force to overwrite.")
        return

    # Create configuration directory
    user_config_dir.mkdir(parents=True, exist_ok=True)

    get_console().print("[bold green]Responses Agent Configuration Setup[/bold green]\n")

    # Read the config template from package data
    config_resource = files("responses_agent.data.config") / "config.yaml"
    config_content = config_resource.read_text()

    # Write configuration
    config_file.write_text(config_content)
    get_console().print(f"[green]✓[/green] Configuration saved to {config_file}")
    get_console().print("\nEdit the configuration file to add your API keys or set them as environment variables.")
    get_console().print(f"Configuration file: [cyan]{config_file}[/cyan]")


def main():
    """Main entry point for the application."""

    # Configure basic logging
    logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")

    # Handle special case where no arguments are provided or it's a slash command
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1].startswith("/")):
        # Run in interactive mode with proper KeyboardInterrupt handling
        try:
            asyncio.run(run_console())
        except KeyboardInterrupt:
            # Graceful shutdown on Ctrl+C
            get_console().print("\n[yellow]Shutdown requested. Goodbye![/yellow]")
            sys.exit(0)
    else:
        # Use Typer for command parsing
        app()


if __name__ == "__main__":
    main()

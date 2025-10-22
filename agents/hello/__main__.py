# ABOUTME: Standalone entry point for hello agent demonstrating user directory override.
# ABOUTME: Shows how downstream projects can use set_app_name() to customize their user directory.

"""Standalone hello agent entry point.

Run with: python -m agents.hello
"""

import asyncio
import sys

from agent_kit.api.console import run_console
from agent_kit.config import setup_configuration
from agent_kit.utils import set_app_name

from .console import HelloCommands


async def main_async():
    """Run hello agent with interface selection based on config."""
    # Set custom user directory before any imports that use get_user_dir()
    set_app_name("hello-agent")

    # Load configuration to determine which interfaces are enabled
    config = await setup_configuration()

    # Start appropriate interface(s)
    if config.interfaces.http.enabled:
        # HTTP mode (REST and/or MCP over HTTP)
        import uvicorn

        from .http import create_hello_server

        app = create_hello_server()
        uvicorn.run(app, host=config.interfaces.http.host, port=config.interfaces.http.port, log_level="info")
    elif config.interfaces.console.enabled:
        # Console mode
        await run_console(HelloCommands)
    elif config.interfaces.mcp_stdio.enabled:
        # MCP stdio mode for Claude Desktop
        from .http import run_hello_stdio

        run_hello_stdio()
    else:
        print("Error: No interfaces enabled. Check your configuration.")
        sys.exit(1)


def main():
    """Entry point wrapper."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()

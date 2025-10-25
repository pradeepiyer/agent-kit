# ABOUTME: Standalone entry point for hello agent demonstrating user directory override.
# ABOUTME: Shows how downstream projects can use set_app_name() to customize their user directory.

"""Standalone hello agent entry point.

Run with: python -m agents.hello
"""

import asyncio
import sys

import uvicorn

from agent_kit.config import setup_configuration
from agent_kit.utils import set_app_name
from agent_kit.api.console import run_console
from .http import create_hello_server
from .console import HelloCommands
from .http import run_hello_stdio



def main():
    """Entry point wrapper."""
    try:
        # Set custom user directory before any imports that use get_user_dir()
        set_app_name("hello-agent")

        # Load configuration to determine which interfaces are enabled
        config = asyncio.run(setup_configuration())

        # Start appropriate interface(s)
        if config.interfaces.http.enabled:
            app = create_hello_server()
            uvicorn.run(app, host=config.interfaces.http.host, port=config.interfaces.http.port, log_level="info")
        elif config.interfaces.console.enabled:
            asyncio.run(run_console(HelloCommands))
        elif config.interfaces.mcp_stdio.enabled:
            run_hello_stdio()
        else:
            print("Error: No interfaces enabled. Check your configuration.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()

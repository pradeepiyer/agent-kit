# ABOUTME: Standalone entry point for hello agent demonstrating user directory override.
# ABOUTME: Shows how downstream projects can use set_app_name() to customize their user directory.

"""Standalone hello agent entry point.

Run with: python -m agent_kit.agents.hello
"""

import asyncio
import sys

from agent_kit.api.console import run_console
from agent_kit.utils import set_app_name

from .console import HelloCommands


def main():
    """Run hello agent with custom user directory."""
    # Set custom user directory before any imports that use get_user_dir()
    set_app_name("hello-agent")

    # Run the console
    try:
        asyncio.run(run_console(HelloCommands))
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()

"""Global configuration management for Agent Kit Framework.

Hard dependencies are imported eagerly to fail fast if missing and
to avoid surprising runtime ImportErrors due to lazy imports.
"""

import asyncio
import logging
import logging.handlers
from pathlib import Path
from typing import TYPE_CHECKING

from agent_kit.utils import get_user_dir

from .loader import ConfigLoader
from .models import AgentKitConfig

# Avoid importing client modules at import time to prevent circular imports
# during test discovery (clients import config, and config.__init__ imports this module).
# Use TYPE_CHECKING for type hints only.
if TYPE_CHECKING:  # pragma: no cover - types only
    from agent_kit.clients.openai_client import OpenAIClient

# Global configuration instance
_config: AgentKitConfig | None = None
_config_file_path: Path | None = None

# Global client instances
_openai_client: "OpenAIClient | None" = None

# Single lock for configuration initialization only
_config_lock = asyncio.Lock()


def load_config_from_file() -> AgentKitConfig:
    """Load configuration from YAML file synchronously (no client initialization).

    Checks for config in this order:
    1. AGENT_KIT_CONFIG environment variable (if set)
    2. ~/.{app-name}/config.yaml (default location)
    3. Built-in defaults (if no file exists)

    Returns:
        AgentKitConfig instance with settings from file or defaults.
    """
    config_loader = ConfigLoader()
    config_file = config_loader.find_config_file()
    return config_loader.load_config(config_file)


async def setup_configuration() -> AgentKitConfig:
    """Initialize global configuration, logging, and all clients."""
    global _config, _config_file_path

    async with _config_lock:
        if _config is None:
            # Load config using synchronous function
            _config = load_config_from_file()
            _config_file_path = ConfigLoader().find_config_file()

            # Setup logging based on configuration
            log_level = getattr(logging, _config.logging.level.upper())
            root_logger = logging.getLogger()
            root_logger.setLevel(log_level)
            root_logger.handlers.clear()

            # Create rotating file handler
            log_dir = get_user_dir() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_dir / "agent-kit.log",
                maxBytes=_config.logging.max_file_size,
                backupCount=_config.logging.backup_count,
            )
            file_handler.setLevel(log_level)
            formatter = logging.Formatter(_config.logging.format, datefmt=_config.logging.datefmt)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            # Reduce verbosity of HTTP/2 and networking libraries and OpenAI client
            for lib in ("httpcore", "httpx", "hpack", "h2", "openai"):
                logging.getLogger(lib).setLevel(logging.WARNING)

        await initialize_all_clients()
        return _config


def get_config() -> AgentKitConfig:
    """Get the global configuration instance."""
    if _config is None:
        raise RuntimeError("Configuration not initialized. Call await setup_configuration() first.")
    return _config


def get_openai_client() -> "OpenAIClient":
    """Get the global shared OpenAI client instance."""
    if _openai_client is None:
        raise RuntimeError("OpenAI client not initialized. Call await setup_configuration() first.")
    return _openai_client


async def close_openai_client() -> None:
    """Close the global OpenAI client and cleanup resources."""
    global _openai_client
    if _openai_client is not None:
        await _openai_client.close()
        _openai_client = None
        logging.info("Closed shared OpenAI client")


async def initialize_all_clients() -> None:
    """Initialize all configured clients at startup."""
    global _openai_client

    # OpenAI is always required
    logging.info("Initializing OpenAI client...")
    from agent_kit.clients.openai_client import OpenAIClient

    _openai_client = OpenAIClient()
    await _openai_client.initialize()

    logging.info("All configured clients initialized successfully")


async def close_all_clients() -> None:
    """Close all global clients and cleanup resources."""
    try:
        await close_openai_client()
    except Exception as e:  # pragma: no cover - defensive cleanup
        logging.warning(f"Error closing client during shutdown: {e}")

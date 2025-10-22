"""Configuration loader with environment variable and file support."""

import json
import logging
import os
import re
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

import yaml

from agent_kit.utils import get_user_dir

from .models import AgentKitConfig

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Configuration loader with support for YAML/JSON files with environment variable substitution."""

    @classmethod
    def load_from_file(cls, file_path: Path) -> dict[str, Any]:
        """Load configuration from a file (YAML or JSON)."""
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        file_content = file_path.read_text(encoding="utf-8")

        # Parse FIRST, then substitute (safe approach)
        try:
            if file_path.suffix.lower() in {".yaml", ".yml"}:
                data: dict[str, Any] = yaml.safe_load(file_content) or {}
            elif file_path.suffix.lower() == ".json":
                data: dict[str, Any] = json.loads(file_content)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            raise ValueError(f"Invalid {file_path.suffix.upper()} in {file_path}: {e}")

        return cls._substitute_env_vars_in_dict(data)

    @classmethod
    def _substitute_env_vars_in_dict(cls, data: Any) -> Any:
        """Safely substitute ${VAR} patterns in dictionary values after parsing."""
        if isinstance(data, dict):
            return {key: cls._substitute_env_vars_in_dict(value) for key, value in cast(dict[str, Any], data).items()}
        if isinstance(data, list):
            return [cls._substitute_env_vars_in_dict(item) for item in cast(list[Any], data)]
        if isinstance(data, str):
            return re.sub(r"\$\{([^}]+)\}", lambda m: os.getenv(m.group(1), m.group(0)), data)
        return data

    @classmethod
    def find_config_file(cls, config_paths: list[Path] | None = None) -> Path | None:
        """Find the first existing configuration file from the search paths."""
        return next(
            (
                path
                for path in (config_paths or AgentKitConfig.get_default_config_paths())
                if path.exists() and path.is_file()
            ),
            None,
        )

    @classmethod
    def load_default_config(cls) -> dict[str, Any]:
        """Load default configuration from package resources."""
        try:
            config_file = files("agent_kit.data.config") / "config.yaml"
            with config_file.open("r", encoding="utf-8") as f:
                data: dict[str, Any] = yaml.safe_load(f.read()) or {}
            return cls._substitute_env_vars_in_dict(data)
        except Exception as e:
            import logging

            logging.warning(f"Failed to load default config from package: {e}")
            return {}

    @classmethod
    def load_agent_configs(cls) -> dict[str, dict[str, Any]]:
        """Discover and load all agent configs from user and project directories.

        Search order for each agent (later configs deep-merge into earlier):
        1. User: ~/.{app-name}/{agent}.yaml
        2. Project: ./agents/{agent}/config.yaml

        Returns:
            Dict mapping agent name to agent config dict
        """
        agent_configs: dict[str, dict[str, Any]] = {}

        # 1. Merge from user directory (~/.{app-name}/{agent}.yaml)
        user_config_dir = get_user_dir()
        if user_config_dir.exists():
            for agent_config_file in user_config_dir.glob("*.yaml"):
                # Skip the main config.yaml
                if agent_config_file.name == "config.yaml":
                    continue
                agent_name = agent_config_file.stem  # e.g., "hello" from "hello.yaml"
                try:
                    user_config = cls.load_from_file(agent_config_file)
                    if agent_name not in agent_configs:
                        agent_configs[agent_name] = {}
                    cls._deep_merge(agent_configs[agent_name], user_config)
                    logger.debug(f"Merged user config for agent '{agent_name}' from {agent_config_file}")
                except Exception as e:
                    logger.warning(f"Failed to load user config for agent '{agent_name}': {e}")

        # 2. Merge from project agents (./agents/{agent}/config.yaml)
        custom_agents_dir = Path.cwd() / "agents"
        if custom_agents_dir.exists():
            for agent_dir in custom_agents_dir.iterdir():
                if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
                    agent_name = agent_dir.name
                    agent_config_file = agent_dir / "config.yaml"
                    if agent_config_file.exists():
                        try:
                            custom_config = cls.load_from_file(agent_config_file)
                            if agent_name not in agent_configs:
                                agent_configs[agent_name] = {}
                            cls._deep_merge(agent_configs[agent_name], custom_config)
                            logger.debug(f"Merged custom config for agent '{agent_name}' from {agent_config_file}")
                        except Exception as e:
                            logger.warning(f"Failed to load custom config for agent '{agent_name}': {e}")

        return agent_configs

    @classmethod
    def load_config(cls, config_file: Path | None = None, config_data: dict[str, Any] | None = None) -> AgentKitConfig:
        """Load configuration from multiple sources with precedence."""
        final_config: dict[str, Any] = {}

        # 1. Always start with packaged defaults so user configs can be sparse
        try:
            cls._deep_merge(final_config, cls.load_default_config())
        except Exception as e:
            import logging

            logging.debug(f"Package config load failed, continuing without defaults: {e}")

        # 2. Merge configuration file (user overrides packaged defaults)
        if config_file:
            if not config_file.exists():
                raise FileNotFoundError(f"Specified config file not found: {config_file}")
            cls._deep_merge(final_config, cls.load_from_file(config_file))
        elif found_config := cls.find_config_file():
            cls._deep_merge(final_config, cls.load_from_file(found_config))

        # 3. Merge explicit config data (highest precedence)
        if config_data:
            cls._deep_merge(final_config, config_data)

        # 4. Load and merge agent configs
        final_config["agent_configs"] = cls.load_agent_configs()

        # 5. Apply connection defaults to client configs
        cls._apply_connection_defaults(final_config)

        # 6. Validate and create the configuration object
        return AgentKitConfig(**final_config)

    @classmethod
    def _apply_connection_defaults(cls, config: dict[str, Any]) -> None:
        """Apply global connection defaults to client configs if not explicitly set."""
        connection_defaults = config.get("connection", {})
        client_configs = ["openai"]

        for client_name in client_configs:
            if client_name in config:
                client_config = config[client_name]
                # Initialize None configs as empty dicts
                if client_config is None:
                    config[client_name] = client_config = {}
                # Apply defaults only if not explicitly set and config is a dict
                if isinstance(client_config, dict):
                    for field in ["pool_size", "request_timeout", "retry_attempts"]:
                        if field in connection_defaults and field not in client_config:
                            client_config[field] = connection_defaults[field]

    @classmethod
    def _deep_merge(cls, target: dict[str, Any], source: dict[str, Any]) -> None:
        """Deep merge source dict into target dict."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                cls._deep_merge(cast(dict[str, Any], target[key]), cast(dict[str, Any], value))
            else:
                target[key] = value


# Convenience function for loading configuration
def load_config(config_file: Path | None = None, config_data: dict[str, Any] | None = None) -> AgentKitConfig:
    """Convenience function to load configuration."""
    return ConfigLoader.load_config(config_file=config_file, config_data=config_data)

"""Test config loading functionality."""

import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from responses_agent.config.loader import ConfigLoader


def test_load_yaml_config(temp_config_dir: Path, sample_config_dict: dict[str, Any]) -> None:
    """Config loads from YAML file correctly."""
    temp_config_dir.mkdir(parents=True, exist_ok=True)
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(yaml.dump(sample_config_dict))

    result = ConfigLoader.load_from_file(config_file)

    assert result["openai"]["model"] == "gpt-5-mini"
    assert result["openai"]["api_key"] == "test-key"
    assert result["connection"]["pool_size"] == 2


def test_load_json_config(temp_config_dir: Path, sample_config_dict: dict[str, Any]) -> None:
    """Config loads from JSON file correctly."""
    temp_config_dir.mkdir(parents=True, exist_ok=True)
    config_file = temp_config_dir / "config.json"
    config_file.write_text(json.dumps(sample_config_dict))

    result = ConfigLoader.load_from_file(config_file)

    assert result["openai"]["model"] == "gpt-5-mini"
    assert result["openai"]["api_key"] == "test-key"


def test_env_var_substitution(temp_config_dir: Path) -> None:
    """Environment variables substitute correctly in config."""
    os.environ["TEST_API_KEY"] = "my-secret-key"
    os.environ["TEST_MODEL"] = "gpt-5"

    temp_config_dir.mkdir(parents=True, exist_ok=True)
    config_file = temp_config_dir / "config.yaml"
    config_content = """
openai:
  api_key: "${TEST_API_KEY}"
  model: "${TEST_MODEL}"
"""
    config_file.write_text(config_content)

    result = ConfigLoader.load_from_file(config_file)

    assert result["openai"]["api_key"] == "my-secret-key"
    assert result["openai"]["model"] == "gpt-5"

    # Cleanup
    del os.environ["TEST_API_KEY"]
    del os.environ["TEST_MODEL"]


def test_env_var_not_set_keeps_placeholder(temp_config_dir: Path) -> None:
    """Missing environment variables remain as placeholders."""
    temp_config_dir.mkdir(parents=True, exist_ok=True)
    config_file = temp_config_dir / "config.yaml"
    config_content = """
openai:
  api_key: "${NONEXISTENT_VAR}"
"""
    config_file.write_text(config_content)

    result = ConfigLoader.load_from_file(config_file)

    assert result["openai"]["api_key"] == "${NONEXISTENT_VAR}"


def test_load_nonexistent_file_raises_error() -> None:
    """Loading nonexistent config file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="not found"):
        ConfigLoader.load_from_file(Path("/nonexistent/config.yaml"))


def test_load_invalid_yaml_raises_error(temp_config_dir: Path) -> None:
    """Loading invalid YAML raises ValueError."""
    temp_config_dir.mkdir(parents=True, exist_ok=True)
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text("invalid: yaml: content: [")

    with pytest.raises(ValueError, match="Invalid"):
        ConfigLoader.load_from_file(config_file)


def test_load_invalid_json_raises_error(temp_config_dir: Path) -> None:
    """Loading invalid JSON raises ValueError."""
    temp_config_dir.mkdir(parents=True, exist_ok=True)
    config_file = temp_config_dir / "config.json"
    config_file.write_text("{invalid json")

    with pytest.raises(ValueError, match="Invalid"):
        ConfigLoader.load_from_file(config_file)

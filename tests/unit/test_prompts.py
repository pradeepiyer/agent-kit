"""Test prompt loading functionality."""

from pathlib import Path

import pytest

from responses_agent.prompts.loader import PromptLoader


def test_load_prompt_from_file(temp_prompts_dir: Path, sample_prompt_yaml: str) -> None:
    """Prompt loads from YAML file correctly."""
    temp_prompts_dir.mkdir(parents=True, exist_ok=True)
    agent_dir = temp_prompts_dir / "hello"
    agent_dir.mkdir(parents=True, exist_ok=True)

    prompt_file = agent_dir / "orchestrator.yaml"
    prompt_file.write_text(sample_prompt_yaml)

    loader = PromptLoader(prompts_dir=temp_prompts_dir)
    config = loader.load_prompt("hello", "orchestrator")

    assert config.agent == "hello"
    assert config.function == "orchestrator"
    assert "Hello Agent" in config.prompt["instructions"]
    assert "friendly assistant" in config.prompt["instructions"]


def test_inject_parameters(temp_prompts_dir: Path) -> None:
    """Parameters inject into prompt templates correctly."""
    temp_prompts_dir.mkdir(parents=True, exist_ok=True)
    agent_dir = temp_prompts_dir / "hello"
    agent_dir.mkdir(parents=True, exist_ok=True)

    prompt_content = """agent: hello
function: greet
parameters:
  - name: user_name
    type: string
    required: true
  - name: greeting_style
    type: string
    required: false
    default: casual
prompt:
  instructions: |
    Greet {user_name} in a {greeting_style} manner.
"""
    prompt_file = agent_dir / "greet.yaml"
    prompt_file.write_text(prompt_content)

    loader = PromptLoader(prompts_dir=temp_prompts_dir)
    config = loader.load_prompt("hello", "greet")
    result = loader.inject_parameters(config, {"user_name": "Alice"})

    assert "Greet Alice in a casual manner" in result["instructions"]


def test_inject_required_parameter_missing_raises_error(temp_prompts_dir: Path) -> None:
    """Missing required parameter raises ValueError."""
    temp_prompts_dir.mkdir(parents=True, exist_ok=True)
    agent_dir = temp_prompts_dir / "hello"
    agent_dir.mkdir(parents=True, exist_ok=True)

    prompt_content = """agent: hello
function: greet
parameters:
  - name: user_name
    type: string
    required: true
prompt:
  instructions: "Greet {user_name}"
"""
    prompt_file = agent_dir / "greet.yaml"
    prompt_file.write_text(prompt_content)

    loader = PromptLoader(prompts_dir=temp_prompts_dir)
    config = loader.load_prompt("hello", "greet")

    with pytest.raises(ValueError, match="Missing required parameter"):
        loader.inject_parameters(config, {})


def test_prompt_caching_works(temp_prompts_dir: Path, sample_prompt_yaml: str) -> None:
    """Same prompt loads from cache on second call."""
    temp_prompts_dir.mkdir(parents=True, exist_ok=True)
    agent_dir = temp_prompts_dir / "hello"
    agent_dir.mkdir(parents=True, exist_ok=True)

    prompt_file = agent_dir / "orchestrator.yaml"
    prompt_file.write_text(sample_prompt_yaml)

    loader = PromptLoader(prompts_dir=temp_prompts_dir)

    # First load - reads from file
    config1 = loader.load_prompt("hello", "orchestrator")

    # Modify file after first load
    prompt_file.write_text(sample_prompt_yaml.replace("friendly", "helpful"))

    # Second load - should return cached version
    config2 = loader.load_prompt("hello", "orchestrator")

    # Should still have "friendly" from cache
    assert config1 is config2
    assert "friendly" in config2.prompt["instructions"]


def test_load_nonexistent_prompt_raises_error(temp_prompts_dir: Path) -> None:
    """Loading nonexistent prompt raises FileNotFoundError."""
    temp_prompts_dir.mkdir(parents=True, exist_ok=True)

    loader = PromptLoader(prompts_dir=temp_prompts_dir)

    with pytest.raises(FileNotFoundError, match="not found"):
        loader.load_prompt("nonexistent", "function")


def test_load_invalid_yaml_prompt_raises_error(temp_prompts_dir: Path) -> None:
    """Loading invalid YAML prompt raises ValueError."""
    temp_prompts_dir.mkdir(parents=True, exist_ok=True)
    agent_dir = temp_prompts_dir / "hello"
    agent_dir.mkdir(parents=True, exist_ok=True)

    prompt_file = agent_dir / "bad.yaml"
    prompt_file.write_text("invalid: yaml: [")

    loader = PromptLoader(prompts_dir=temp_prompts_dir)

    with pytest.raises(ValueError, match="Invalid YAML"):
        loader.load_prompt("hello", "bad")


def test_load_and_inject_convenience_method(temp_prompts_dir: Path) -> None:
    """Convenience method loads and injects in one call."""
    temp_prompts_dir.mkdir(parents=True, exist_ok=True)
    agent_dir = temp_prompts_dir / "hello"
    agent_dir.mkdir(parents=True, exist_ok=True)

    prompt_content = """agent: hello
function: greet
parameters:
  - name: user_name
    type: string
    required: true
prompt:
  instructions: "Hello {user_name}!"
"""
    prompt_file = agent_dir / "greet.yaml"
    prompt_file.write_text(prompt_content)

    loader = PromptLoader(prompts_dir=temp_prompts_dir)
    result = loader.load_and_inject("hello", "greet", {"user_name": "Bob"})

    assert result["instructions"] == "Hello Bob!"


def test_default_parameter_values_apply(temp_prompts_dir: Path) -> None:
    """Default parameter values apply when not provided."""
    temp_prompts_dir.mkdir(parents=True, exist_ok=True)
    agent_dir = temp_prompts_dir / "hello"
    agent_dir.mkdir(parents=True, exist_ok=True)

    prompt_content = """agent: hello
function: greet
parameters:
  - name: style
    type: string
    required: false
    default: formal
prompt:
  instructions: "Style: {style}"
"""
    prompt_file = agent_dir / "greet.yaml"
    prompt_file.write_text(prompt_content)

    loader = PromptLoader(prompts_dir=temp_prompts_dir)
    config = loader.load_prompt("hello", "greet")
    result = loader.inject_parameters(config, {})

    assert "Style: formal" in result["instructions"]

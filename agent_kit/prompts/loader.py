"""Prompt loader for external YAML-based prompt management."""

from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from .models import PromptConfig


class PromptLoader:
    """Loads and manages YAML-based prompts with versioning support."""

    def __init__(self, prompts_dir: Path | None = None, search_paths: list[str | Path] | None = None):
        """Initialize the prompt loader.

        Args:
            prompts_dir: Legacy single directory support (deprecated, use search_paths)
            search_paths: List of directories to search for prompts (searched in order)
        """
        self._cache: dict[str, PromptConfig] = {}

        # Handle legacy prompts_dir parameter
        if prompts_dir is not None:
            self.search_paths = [Path(prompts_dir)]
            self.use_package_resources = False
        elif search_paths:
            self.search_paths = [Path(p) for p in search_paths]
            self.use_package_resources = False
        else:
            self.search_paths = []
            self.use_package_resources = True

        # Legacy compatibility
        self.prompts_dir = self.search_paths[0] if self.search_paths else Path("agent_kit/agents")

    def _load_file_content(self, file_path: Path) -> str:
        """Load file content from either filesystem or package resources."""
        if self.use_package_resources:
            try:
                # New location: agent_kit/agents/{agent}/prompts/{function}.yaml
                relative_path = file_path.relative_to(Path("agent_kit/agents"))
                resource_file = files("agent_kit.agents")
                for part in relative_path.parts:
                    resource_file = resource_file / part
                with resource_file.open("r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                raise FileNotFoundError(f"Package resource not found: {file_path}")
        with open(file_path, encoding="utf-8") as f:
            return f.read()

    def _file_exists(self, file_path: Path) -> bool:
        """Check if file exists in either filesystem or package resources."""
        if self.use_package_resources:
            try:
                # New location: agent_kit/agents/{agent}/prompts/{function}.yaml
                relative_path = file_path.relative_to(Path("agent_kit/agents"))
                resource_file = files("agent_kit.agents")
                for part in relative_path.parts:
                    resource_file = resource_file / part
                with resource_file.open("r"):
                    pass
                return True
            except Exception:
                return False
        return file_path.exists()

    def load_prompt(self, agent: str, function: str, version: str | None = None) -> PromptConfig:
        """Load a prompt configuration from YAML file.

        Searches custom search_paths first, then falls back to package resources.
        """
        cache_key = f"{agent}:{function}:{version or 'latest'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt_path = self._find_prompt_file(agent, function, version)
        if not self._file_exists(prompt_path):
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        try:
            config = PromptConfig(**yaml.safe_load(self._load_file_content(prompt_path)))
            self._cache[cache_key] = config
            return config
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {prompt_path}: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load prompt from {prompt_path}: {e}")

    def inject_parameters(self, config: PromptConfig, params: dict[str, Any]) -> dict[str, str]:
        """Inject parameters into prompt templates."""
        validated_params = config.validate_parameters(params)
        result: dict[str, Any] = {}
        for prompt_type, template in config.prompt.items():
            try:
                result[prompt_type] = template.format(**validated_params)
            except (KeyError, ValueError) as e:
                raise ValueError(f"Template error for {prompt_type}: {e}")
        return result

    def _find_prompt_file(self, agent: str, function: str, version: str | None = None) -> Path:
        """Find the appropriate prompt file based on agent, function, and version.

        Searches across all search_paths in order, then falls back to package resources.
        New location: agent_kit/agents/{agent}/prompts/{function}.yaml
        """
        # Search custom paths first
        for search_dir in self.search_paths:
            agent_path = search_dir / agent / "prompts" / f"{function}.yaml"
            paths: list[Path] = [
                search_dir / "versions" / f"v{version}" / "agents" / agent / "prompts" / f"{function}.yaml"
                if version
                else agent_path,
                agent_path,
                search_dir / "common" / f"{function}.yaml",
            ]
            for path in paths:
                if self._file_exists(path):
                    return path

        # Fallback to package resources if using them
        if self.use_package_resources:
            # New path: agent_kit/agents/{agent}/prompts/{function}.yaml
            agent_path = self.prompts_dir / agent / "prompts" / f"{function}.yaml"
            return agent_path

        # If nothing found, return default path for error message
        return self.prompts_dir / agent / "prompts" / f"{function}.yaml"

    def load_and_inject(
        self, agent: str, function: str, params: dict[str, Any], version: str | None = None
    ) -> dict[str, str]:
        """Convenience method to load prompt and inject parameters in one call."""
        return self.inject_parameters(self.load_prompt(agent, function, version), params)

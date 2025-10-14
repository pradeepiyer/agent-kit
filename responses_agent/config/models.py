"""Core configuration models for responses-agent-framework."""

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class LogLevel(str, Enum):
    """Logging level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DebugPromptConfig(BaseModel):
    """Configuration for prompt debugging."""

    enabled: bool = Field(default=False, description="Enable saving prompts to temp files")
    directory: str = Field(default="/tmp/responses-agent-prompts", description="Directory for saving prompts")
    max_files: int = Field(default=100, ge=1, description="Maximum number of prompt files to keep")


class ConnectionConfig(BaseModel):
    """Base configuration for connection pooling and retry logic."""

    pool_size: int = Field(ge=1, le=20, description="Number of connections in pool")
    request_timeout: int = Field(gt=0, description="Individual request timeout in seconds")
    retry_attempts: int = Field(ge=0, description="Number of retry attempts on failure")


class OpenAIConfig(ConnectionConfig):
    """OpenAI API configuration with connection pooling."""

    # Core API settings
    api_key: str = Field(..., description="OpenAI API key")
    model: str = Field(description="Default OpenAI model to use")
    output_token_ratio: float = Field(default=0.25, ge=0.1, le=0.5, description="Ratio of context to use for output")

    # Model context limits (total tokens)
    model_limits: dict[str, int] = Field(default_factory=dict, description="Model context limits in tokens")

    # Function-based model overrides
    function_models: dict[str, str] = Field(
        default_factory=dict, description="Model overrides by agent/function pair (e.g., 'hello/hello')"
    )

    # Reasoning configuration for GPT-5 extended thinking (RLVR)
    reasoning_effort: Literal["minimal", "medium", "high"] = Field(
        default="medium",
        description="Default reasoning effort: minimal (fast), medium (balanced), high (deep thinking with RLVR)",
    )
    function_reasoning: dict[str, Literal["minimal", "medium", "high"]] = Field(
        default_factory=dict, description="Per-function reasoning effort overrides (e.g., 'hello/hello': 'minimal')"
    )
    reasoning_summary: bool = Field(
        default=False,
        description="Enable reasoning summaries in progress updates (uses auto mode for best compatibility)",
    )

    # Override default pool_size for OpenAI (higher usage)
    pool_size: int = Field(ge=1, le=20, description="Number of connections in pool")

    # Debug prompt configuration
    debug_prompts: DebugPromptConfig = Field(
        default_factory=DebugPromptConfig, description="Debug prompt configuration"
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or not v.startswith("sk-"):
            raise ValueError("OpenAI API key must start with 'sk-' and cannot be empty")
        return v


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: LogLevel = Field(description="Log level")
    format: str = Field(description="Log format")
    datefmt: str | None = Field(default=None, description="Date format for asctime (optional)")
    max_file_size: int = Field(gt=0, description="Max log file size in bytes")
    backup_count: int = Field(ge=0, description="Number of backup log files to keep")

    @field_validator("level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str | LogLevel) -> LogLevel:
        if isinstance(v, LogLevel):
            return v
        try:
            return LogLevel(v.upper())
        except (ValueError, AttributeError):
            raise ValueError(f"Log level must be one of: {[level.value for level in LogLevel]}")


class AgentsConfig(BaseModel):
    """Global configuration for all agents."""

    max_iterations: int = Field(ge=1, le=20, description="Maximum tool-calling iterations for agents")
    max_parallel_tools: int = Field(default=5, ge=1, le=10, description="Maximum parallel tool executions")


class HelloConfig(BaseModel):
    """Hello agent configuration."""

    max_iterations: int = Field(
        default=3, ge=1, le=20, description="Maximum tool-calling iterations (overrides global default)"
    )


class ResponsesAgentConfig(BaseModel):
    """Main configuration for responses-agent-framework application."""

    connection: ConnectionConfig = Field(..., description="Global connection defaults")
    agents: AgentsConfig = Field(..., description="Global agent configuration defaults")
    openai: OpenAIConfig
    logging: LoggingConfig
    hello: HelloConfig

    @model_validator(mode="before")
    @classmethod
    def inherit_agent_defaults(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Inherit max_iterations from global agents config if not set explicitly."""
        if global_max := values.get("agents", {}).get("max_iterations", 3):
            for section in ["hello"]:
                if section in values and "max_iterations" not in values[section]:
                    values[section]["max_iterations"] = global_max
        return values

    @classmethod
    def get_default_config_paths(cls) -> list[Path]:
        """Get default configuration file paths to search."""
        return [
            Path.home() / ".responses-agent" / "config.yaml",  # User config (highest priority)
            Path.cwd() / "config.yaml",  # Project root
        ]

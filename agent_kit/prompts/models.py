"""Data models for prompt management system."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class PromptParameter(BaseModel):
    """Parameter definition for prompt templates."""

    name: str
    type: str = Field(..., pattern="^(string|int|float|bool|list|dict)$")
    required: bool = True
    default: Any | None = None
    description: str | None = None

    @field_validator("default")
    @classmethod
    def validate_default_matches_type(cls, v: Any, info: Any) -> Any | None:
        if v is None:
            return v

        param_type = info.data.get("type")
        type_checks = {"string": str, "int": int, "float": (int, float), "bool": bool, "list": list, "dict": dict}

        if param_type in type_checks and not isinstance(v, type_checks[param_type]):
            raise ValueError(f"Default value must be {param_type}, got {type(v).__name__}")

        return v  # type: ignore[return-value]


class PromptConfig(BaseModel):
    """Complete prompt configuration loaded from YAML file."""

    agent: str
    function: str
    prompt: dict[str, str] = Field(..., min_length=1)
    parameters: list[PromptParameter] | None = None

    @field_validator("prompt")
    @classmethod
    def validate_prompt_structure(cls, v: dict[str, str]) -> dict[str, str]:
        if not {"instructions"}.issubset(v.keys()):
            raise ValueError("Prompt must contain keys: {'instructions'}")
        return v

    def get_parameter_names(self) -> list[str]:
        """Get list of parameter names defined in this prompt."""
        return [param.name for param in self.parameters] if self.parameters else []

    def get_required_parameters(self) -> list[str]:
        """Get list of required parameter names."""
        return [param.name for param in self.parameters if param.required] if self.parameters else []

    def get_parameter_defaults(self) -> dict[str, Any]:
        """Get dictionary of parameter defaults."""
        return (
            {param.name: param.default for param in self.parameters if param.default is not None}
            if self.parameters
            else {}
        )

    def validate_parameters(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate and prepare parameters for injection."""
        if not self.parameters:
            return params

        # Check required parameters
        if missing := set(self.get_required_parameters()) - set(params.keys()):
            raise ValueError(f"Missing required parameters: {sorted(missing)}")

        # Apply defaults for missing optional parameters
        result = dict(params)
        for param_name, default_value in self.get_parameter_defaults().items():
            if param_name not in result:
                result[param_name] = default_value

        return result

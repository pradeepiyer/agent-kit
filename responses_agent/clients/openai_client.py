"""
Pooled OpenAI client with load balancing and error recovery.
"""

import logging
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel

from ..exceptions import ClientError
from ..utils.prompt_debug import save_prompt_debug
from .base import ConnectionPool, OpenAIConnectionFactory
from responses_agent.config.config import get_config

logger = logging.getLogger(__name__)

# T must be a Pydantic BaseModel for structured outputs
T = TypeVar("T", bound=BaseModel)


class OpenAIClient:
    """Pooled OpenAI client with Responses API support."""

    def __init__(self):
        """Initialize the pooled OpenAI client."""

        self.config = get_config().openai
        factory = OpenAIConnectionFactory(self.config)
        self.pool = ConnectionPool(factory)
        self._initialized = False

        logger.info(f"Initialized pooled OpenAI client (pool_size={self.config.pool_size}, model={self.config.model})")

        # Log debug prompt configuration
        if self.config.debug_prompts.enabled:
            logger.info(f"Debug prompts enabled: saving to {self.config.debug_prompts.directory}")

    async def initialize(self) -> None:
        """Initialize connection pool eagerly."""
        if not self._initialized:
            await self.pool.initialize()
            self._initialized = True

    async def responses_create(
        self,
        iteration: int,  # Mandatory iteration number for debugging
        agent_type: str,  # Mandatory agent type for debugging
        model: str | None = None,
        instructions: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        reasoning_effort: str | None = None,  # GPT-5 reasoning effort: minimal/medium/high
        max_output_tokens: int | None = None,
        response_format: type[BaseModel] | None = None,
        previous_response_id: str | None = None,
        prompt_cache_key: str | None = None,  # Cache key for routing to improve cache hits
        store: bool = True,
        truncation: str | None = "auto",  # Enable auto-truncation by default
    ) -> Any:
        """Direct Responses API call with reasoning model support."""
        # Format input properly
        if isinstance(input, str):
            formatted_input = [{"role": "user", "content": input}]
        else:
            formatted_input = input if input else []

        # Handle structured output format
        response_format_dict = None
        if response_format:
            schema = response_format.model_json_schema()
            response_format_dict = {
                "format": {"type": "json_schema", "name": response_format.__name__, "schema": schema, "strict": True}
            }

        # Track timestamp for debugging
        timestamp = datetime.now()

        # Build reasoning dict for GPT-5 models if effort specified
        reasoning_dict = None
        if reasoning_effort:
            reasoning_dict = {"effort": reasoning_effort}
            if self.config.reasoning_summary:
                reasoning_dict["summary"] = "auto"

        # Make the API call directly with typed parameters
        connection = None
        response = None
        try:
            connection = await self.pool.get_connection()

            # Calculate max_output_tokens dynamically if not provided
            if not max_output_tokens:
                context_limit = self.config.model_limits.get(
                    model or self.config.model, self.config.model_limits.get("default", 128000)
                )
                max_output_tokens = int(context_limit * self.config.output_token_ratio)

            # Direct SDK call with typed parameters - no dict building
            response = await connection.client.responses.create(
                model=model or self.config.model,
                input=formatted_input,
                instructions=instructions,
                tools=tools,
                tool_choice=tool_choice,
                reasoning=reasoning_dict,
                max_output_tokens=max_output_tokens,
                previous_response_id=previous_response_id,
                prompt_cache_key=prompt_cache_key,
                text=response_format_dict,
                store=store,
                truncation=truncation,
            )

            connection.record_success()
            return response

        except Exception as e:
            if connection:
                connection.record_error()
            logger.error(f"Direct Responses API call failed: {e}")
            raise ClientError(f"Responses API call failed: {e}")
        finally:
            # Save prompt debug after API call (whether success or failure)
            if self.config.debug_prompts.enabled:
                await save_prompt_debug(
                    config=self.config.debug_prompts,
                    timestamp=timestamp,
                    agent_type=agent_type,
                    iteration=iteration,
                    model=model or self.config.model,
                    instructions=instructions,
                    input_messages=input if input else formatted_input,
                    tools=tools,
                    max_output_tokens=max_output_tokens,
                    previous_response_id=previous_response_id,
                    response=response,  # Will be None if API call failed
                )

            if connection:
                await self.pool.return_connection(connection)

    async def close(self) -> None:
        """Close the connection pool and cleanup resources."""
        await self.pool.close()
        logger.info("OpenAI client closed")

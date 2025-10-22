"""
Base agent class with common patterns and utilities.

"""

import asyncio
import json
import logging
from abc import ABC
from collections.abc import Awaitable, Callable
from typing import Any

from agent_kit.prompts.loader import PromptLoader
from agent_kit.prompts.models import PromptConfig

from ..clients.openai_client import OpenAIClient
from ..config.config import get_config
from ..exceptions import HelloAgentError
from agent_kit.api.progress import ProgressHandler
from pathlib import Path


class BaseAgent(ABC):
    """Base class for all Hello Agent components with common functionality."""

    def __init__(self, openai_client: OpenAIClient, progress_handler: ProgressHandler):
        """Initialize base agent with common setup."""
        self.client = openai_client
        self.progress_handler = progress_handler
        self.logger = logging.getLogger(self.__class__.__module__ + "." + self.__class__.__name__)
        self.last_response_id: str | None = None

        self.prompt_loader = PromptLoader(search_paths=[Path.cwd() / "agents"])
        self.last_prompt_config: PromptConfig | None = None
        self.prompt_cache_key: str | None = None
        self.agent_type = self.__class__.__name__.replace("Agent", "").lower()

    def _process_response_metadata(
        self,
        response: Any,
        iteration: int,
        max_iterations: int,
        response_id: str | None,
        previous_response_id: str | None,
    ) -> bool:
        """Process response metadata: track tokens, check limits, handle incomplete responses."""
        current_input_tokens = 0
        if hasattr(response, "usage"):
            usage = response.usage
            tokens_info = f"model={self.client.config.model}, input={usage.input_tokens}"
            if (
                hasattr(usage, "input_tokens_details")
                and (details := usage.input_tokens_details)
                and hasattr(details, "cached_tokens")
                and details.cached_tokens > 0
            ):
                tokens_info += f" (cached={details.cached_tokens})"
            tokens_info += f", output={usage.output_tokens}"
            if (
                hasattr(usage, "output_tokens_details")
                and (details := usage.output_tokens_details)
                and hasattr(details, "reasoning_tokens")
                and details.reasoning_tokens > 0
            ):
                tokens_info += f" (reasoning={details.reasoning_tokens})"
            tokens_info += f", total={usage.total_tokens}, iteration={iteration + 1}/{max_iterations}"
            if response_id:
                tokens_info += f", response_id={response_id}"
            if previous_response_id and iteration == 0:
                tokens_info += " [follow-up]"
            self.logger.info(f"Token usage: {tokens_info}")
            current_input_tokens = usage.input_tokens

            if self.client.config.model_limits:
                context_limit = self.client.config.model_limits.get(
                    self.client.config.model, self.client.config.model_limits.get("default", 128000)
                )
                projected_total = current_input_tokens + int(context_limit * self.client.config.output_token_ratio)
                if projected_total > context_limit * 0.9:
                    self.logger.info(
                        f"Context usage high: current={current_input_tokens}, projected={projected_total}/{context_limit} "
                        f"({projected_total / context_limit * 100:.1f}%) - auto-truncation will handle if needed"
                    )

        if hasattr(response, "status") and response.status == "incomplete":
            reason = (
                getattr(response.incomplete_details, "reason", "unknown")
                if hasattr(response, "incomplete_details")
                else "unknown"
            )
            self.logger.warning(
                f"Response incomplete despite auto-truncation: {reason} at iteration {iteration + 1}. "
                f"This may indicate the response itself exceeded token limits."
            )
            return True
        return False

    async def _extract_and_emit_reasoning_summary(self, response: Any) -> None:
        """Extract reasoning summary from response and emit as progress."""
        if not self.client.config.reasoning_summary or not (hasattr(response, "output") and response.output):
            return

        # Find reasoning output items
        reasoning_items = [item for item in response.output if hasattr(item, "type") and item.type == "reasoning"]

        if not reasoning_items:
            return

        for item in reasoning_items:
            if hasattr(item, "summary") and item.summary:
                for summary_part in item.summary:
                    if hasattr(summary_part, "text") and summary_part.text:
                        await self.progress_handler.emit(summary_part.text, stage="reasoning")

    async def _execute_tool_calls(
        self, response: Any, tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None
    ) -> tuple[bool, list[dict[str, Any]]]:
        """Execute tool calls from response if present. Returns tuple of (has_tool_calls, tool_outputs)."""
        if not (hasattr(response, "output") and response.output):
            return False, []
        tool_calls = [item for item in response.output if hasattr(item, "type") and item.type == "function_call"]
        if not tool_calls:
            return False, []

        await self.progress_handler.emit(
            f"Executing {len(tool_calls)} tool(s): {', '.join(getattr(tc, 'name', 'unknown') for tc in tool_calls)}",
            "tools",
        )
        semaphore = asyncio.Semaphore(get_config().agents.max_parallel_tools)

        async def execute_single_tool(item: Any) -> dict[str, Any]:
            async with semaphore:
                args: dict[str, Any] = json.loads(item.arguments) if item.arguments else {}
                self.logger.info(f"Processing tool call: {item.name}")
                try:
                    tool_result = (
                        await tool_executor(item.name, args)
                        if tool_executor
                        else {"error": "Tool executor not provided"}
                    )
                    if not tool_executor:
                        self.logger.error(f"Tool executor not provided for {item.name}")
                except Exception as e:
                    self.logger.error(f"Tool execution failed for {item.name}: {e}")
                    tool_result = {"error": str(e)}
                return {
                    "type": "function_call_output",
                    "call_id": getattr(item, "call_id", getattr(item, "id", "unknown")),
                    "output": json.dumps(tool_result),
                }

        return True, await asyncio.gather(*[execute_single_tool(item) for item in tool_calls])

    def render_prompt(self, agent: str, function: str, **params: Any) -> dict[str, str]:
        """Load and render a prompt with parameters using shared PromptLoader."""
        try:
            self.last_prompt_config = self.prompt_loader.load_prompt(agent, function)
            self.prompt_cache_key = f"{agent}/{function}"
            return self.prompt_loader.inject_parameters(self.last_prompt_config, params)
        except Exception as e:
            raise HelloAgentError(f"Failed to render prompt for {agent}/{function}: {e}")

    async def execute_tool_conversation(
        self,
        instructions: str,
        initial_input: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
        max_iterations: int = 1,
        previous_response_id: str | None = None,
        response_format: type[Any] | None = None,
        store: bool = True,
    ) -> Any:
        """Execute a conversation flow with tool calls using Responses API."""

        input_list, response_id, final_content, iteration = initial_input, None, None, 0
        while iteration < max_iterations:
            self.logger.info(
                f"Iteration {iteration + 1}/{max_iterations} - Current input messages: {len(input_list)}, "
                f"Instructions length: {len(instructions)}"
            )
            await self.progress_handler.emit(f"Processing iteration {iteration + 1}/{max_iterations}")

            # Disable tools on last iteration if we have a response format
            tool_choice, tools_to_pass = (
                ("none", None) if response_format and iteration == max_iterations - 1 else (None, tools)
            )

            model = reasoning_effort = None
            if self.last_prompt_config:
                function_key = f"{self.last_prompt_config.agent}/{self.last_prompt_config.function}"
                model = self.client.config.function_models.get(function_key)
                reasoning_effort = self.client.config.function_reasoning.get(
                    function_key, self.client.config.reasoning_effort
                )

            response = await self.client.responses_create(
                iteration=iteration + 1,  # Use 1-based iteration for display
                agent_type=self.agent_type,
                model=model,
                instructions=instructions,
                input=input_list,
                tools=tools_to_pass,
                tool_choice=tool_choice,
                reasoning_effort=reasoning_effort,
                previous_response_id=previous_response_id if iteration == 0 else response_id,
                prompt_cache_key=self.prompt_cache_key,
                response_format=response_format,
                store=store,
            )

            response_id = response.id if hasattr(response, "id") else response_id
            await self._extract_and_emit_reasoning_summary(response)
            is_incomplete = self._process_response_metadata(
                response, iteration, max_iterations, response_id, previous_response_id
            )
            if is_incomplete:
                iteration += 1
                continue

            # Check for tool calls first - structured output should only be parsed when no tools remain
            has_tool_calls, input_list = await self._execute_tool_calls(response, tool_executor)

            # Finalize if no tool calls or reached max iterations
            if not has_tool_calls or iteration == max_iterations - 1:
                if iteration == max_iterations - 1:
                    self.logger.info(f"Reached max iterations ({max_iterations}), finalizing response")

                await self.progress_handler.emit("Finalizing response", "complete")

                # Try to parse structured output if format specified
                if response_format and hasattr(response, "output_text") and response.output_text:
                    try:
                        final_content = response_format.model_validate_json(response.output_text)
                        self.logger.info(f"Parsed structured output: {response_format.__name__}")
                        break  # Successfully parsed, exit loop
                    except Exception as e:
                        self.logger.warning(f"Could not parse structured output: {e}")
                        if iteration == max_iterations - 1:
                            raise  # Re-raise on last iteration
                        # Continue loop to retry parsing on next iteration
                        iteration += 1
                        continue
                else:
                    # If response_format is set but output_text missing, fail on last iteration
                    if response_format and iteration == max_iterations - 1:
                        raise RuntimeError(
                            f"Structured output requested ({response_format.__name__}) but response has no output_text"
                        )
                    final_content = response
                break

            iteration += 1

        if store:
            self.last_response_id = response_id
        return final_content

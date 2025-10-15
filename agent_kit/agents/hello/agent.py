"""Hello Agent - A simple example agent demonstrating the framework."""

import logging

from agent_kit.agents.base_agent import BaseAgent
from agent_kit.clients.openai_client import OpenAIClient
from agent_kit.config.config import get_config

from .tools import execute_tool, get_tool_definitions

logger = logging.getLogger(__name__)


class HelloAgent(BaseAgent):
    """A simple hello agent that can chat and use tools."""

    def __init__(self, openai_client: OpenAIClient):
        """Initialize Hello Agent."""
        super().__init__(openai_client)
        logger.info("HelloAgent initialized")

    async def process(self, query: str, continue_conversation: bool = False) -> str:
        """Process a query with optional conversation continuation.

        Args:
            query: User query to process
            continue_conversation: If True, continues previous conversation using last_response_id.
                                  If False, starts fresh conversation.

        Returns:
            Response message
        """
        logger.info(f"Processing query (continue={continue_conversation}): {query[:100]}")

        # Render orchestrator prompt
        prompts = self.render_prompt("hello", "orchestrator")

        # Get max iterations from agent config (with fallback to global default)
        max_iterations = self.get_agent_config("max_iterations", get_config().agents.max_iterations)

        # Execute the conversation with tools
        response = await self.execute_tool_conversation(
            instructions=prompts["instructions"],
            initial_input=[{"role": "user", "content": query}],
            tools=get_tool_definitions(),
            tool_executor=execute_tool,
            max_iterations=max_iterations,
            previous_response_id=self.last_response_id if continue_conversation else None,
            response_format=None,  # No structured output for conversational responses
        )

        # Extract text from response
        if hasattr(response, "output_text") and response.output_text:
            logger.info(f"Successfully processed query: {response.output_text[:100]}")
            return response.output_text
        elif (
            hasattr(response, "output")
            and response.output
            and (text_items := [item for item in response.output if hasattr(item, "type") and item.type == "text"])
        ):
            if text_items and hasattr(text_items[0], "text"):
                logger.info(f"Successfully extracted text from response: {text_items[0].text[:100]}")
                return text_items[0].text

        # Fallback
        logger.warning("Could not extract text from response, using fallback")
        return "I'm having trouble processing that request. Please try again."

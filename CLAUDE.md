# Agent Kit - Claude Instructions

## Overview
Developer toolkit for building AI agents with OpenAI Responses API. Demonstrates core patterns: conversation continuation with `previous_response_id`, session management, tool integration, and structured outputs.

## Tech Stack
- Python 3.13+, uv package manager
- OpenAI Responses API for tool-calling conversations
- Typer CLI with rich console interface
- Pydantic models with structured outputs
- YAML-based configuration and prompt templates

## Architecture
- **Base Agent**: Unified `execute_tool_conversation()` for all agents
- **Responses API**: Native tool execution with `previous_response_id` for conversation continuation
- **Session Management**: Thread-safe session store with automatic expiration
- **Prompt System**: YAML-based prompts in markdown format with parameter injection
- **Tool System**: Centralized tool definitions in `utils/tools.py`
- **Connection Pooling**: Efficient OpenAI client with retry logic

## Key Features
- **Chat Interface**: Interactive console with slash commands
- **Hello Command** (`/hello`): Fresh greeting conversations
- **Chat Mode**: Continuous conversation with context via Responses API
- **Web Search**: Native OpenAI web search with citation support
- **Progress Tracking**: Context-aware progress updates with reasoning summaries
- **Tool Execution**: Async tool calling (web search, time utilities)

## Agent Patterns
```python
# Standard Responses API pattern with single process() method
async def process(self, query: str, continue_conversation: bool = False) -> str:
    prompts = self.render_prompt("agent", "orchestrator")

    result = await self.execute_tool_conversation(
        instructions=prompts["instructions"],
        initial_input=[{"role": "user", "content": query}],
        tools=get_tool_definitions(),
        tool_executor=execute_tool,
        previous_response_id=self.last_response_id if continue_conversation else None,
        response_format=None,  # Or Pydantic model for structured output
        max_iterations=10
    )
    # response_id is stored internally as self.last_response_id
    return result
```

## Development Guidelines
- Async/await patterns throughout
- Pydantic models with `model_config = {"extra": "forbid"}` for structured outputs
- OpenAI Responses API over manual prompting
- YAML prompts in markdown format with `# Headers` and `## Subheaders`
- Single public method pattern: `process(query, continue_conversation)`
- Minimal comments, brief and contextual
- Run all Python commands under uv
- Follow DRY principle aggressively
- Don't commit by default - wait for review

## Testing
```bash
# Run linter
ruff check .

# Run formatter
ruff format .

# Run type checker
pyright

# Run tests
pytest
```

## Type Checking
- **Strict mode enabled**: All new code must pass `pyright` in strict mode
- Avoid type ignores unless absolutely necessary
- Use proper type annotations: `dict[str, Any]` not `dict`
- Run `uv run pyright` to check types before committing

## Key Principles
- **No backward compatibility needed**: Move fast, improve the framework
- **Avoid code bloat**: Keep abstractions minimal and purposeful
- **Responses API for conversations**: Use `previous_response_id` for context, not message arrays
- **Structured outputs via Pydantic**: Enable reliable parsing with `extra="forbid"`
- **Single method pattern**: One public `process()` method per agent
- **Centralized tools**: Define all tools in `utils/tools.py`
- **Markdown prompts**: Use `#` headers for structure, not verbose text blocks
- **Brief docstrings**: Single line by default, expand only when necessary
- **Session-based context**: Let AgentAPI manage sessions, agents focus on processing
- **Tool-first design**: Prefer tool calls over prompt engineering for dynamic data

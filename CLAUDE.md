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
- **Session Management**: Async session store with automatic expiration
- **Progress Handling**: Protocol-based progress reporting (console, REST SSE, MCP)
- **Prompt System**: YAML-based prompts in markdown format with parameter injection
- **Tool System**: Centralized tool definitions with async execution
- **Connection Pooling**: Efficient OpenAI client with retry logic
- **Multiple Interfaces**: Console, REST API with SSE, and MCP protocol

## Key Features
- **Multiple Interfaces**: Console, REST API with SSE streaming, MCP for Claude Desktop
- **Agent Registry**: Dynamic route and tool generation for HTTP protocols
- **Chat Interface**: Interactive console with slash commands
- **Hello Command** (`/hello`): Fresh greeting conversations
- **Chat Mode**: Continuous conversation with context via Responses API
- **Web Search**: Native OpenAI web search with citation support
- **Progress Tracking**: Unified progress handler across all interfaces
- **Tool Execution**: Async tool calling (web search, time utilities)

## Agent Patterns
```python
# BaseAgent requires progress_handler parameter
class MyAgent(BaseAgent):
    def __init__(self, openai_client: OpenAIClient, progress_handler: ProgressHandler):
        super().__init__(openai_client, progress_handler)

    async def process(self, query: str) -> str:
        prompts = self.render_prompt("agent", "orchestrator")

        result = await self.execute_tool_conversation(
            instructions=prompts["instructions"],
            initial_input=[{"role": "user", "content": query}],
            tools=get_tool_definitions(),
            tool_executor=execute_tool,
            previous_response_id=self.last_response_id,
            response_format=None,  # Or Pydantic model for structured output
            max_iterations=10
        )
        # response_id is stored internally as self.last_response_id
        # Conversation continues automatically within same session
        return result
```

## HTTP Patterns

### Agent Registry
```python
from agent_kit.api.http import AgentRegistry, create_server

registry = AgentRegistry()
registry.register(
    name="my_agent",
    agent_class=MyAgent,
    description="Agent description for API docs and MCP tools",
    request_model=MyRequest,  # Pydantic model
    response_model=MyResponse,  # Pydantic model
)

app = create_server(registry, config.interfaces.http, config.interfaces.session_ttl)
```

### Interface Configuration
```yaml
interfaces:
  session_ttl: 3600  # Shared across all interfaces

  http:              # HTTP server
    enabled: false
    host: "0.0.0.0"
    port: 8000
    cors_origins: ["http://localhost:*"]
    rest_api: true   # Enable REST endpoints
    mcp_http: true   # Enable MCP over HTTP
    mcp_mount_path: "/mcp"

  console:
    enabled: true

  mcp_stdio:
    enabled: false   # MCP stdio for Claude Desktop
```

### Progress Handlers
- **ConsoleProgressHandler**: Rich console output with formatting
- **RESTProgressHandler**: SSE streaming via asyncio queue
- **MCPProgressHandler**: Context.report_progress() for Claude Desktop
- **NoOpProgressHandler**: Silent handler for testing

## Development Guidelines
- Async/await patterns throughout
- Pydantic models with `model_config = {"extra": "forbid"}` for structured outputs
- OpenAI Responses API over manual prompting
- YAML prompts in markdown format with `# Headers` and `## Subheaders`
- Minimal comments, brief and contextual
- Run all Python commands under uv
- Follow DRY principle aggressively
- Don't commit by default - wait for review

## Testing
```bash
# Run linter
uv run ruff check --fix .

# Run type checker
uv run pyright

# Run tests
uv run pytest
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
- **Markdown prompts**: Use `#` headers for structure, not verbose text blocks
- **Brief docstrings**: Single line by default, expand only when necessary
- **Session-based context**: Let AgentAPI manage sessions, agents focus on processing
- **Tool-first design**: Prefer tool calls over prompt engineering for dynamic data

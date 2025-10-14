# Agent Kit

Developer toolkit for building production-ready AI agents with OpenAI Responses API.

## Features
- **OpenAI Response API**: Support OpenAI Responses API with conversation continuation
- **Configuration System**: YAML-based configuration with environment variable substitution
- **Connection Pooling**: Efficient OpenAI client with connection pool management
- **Base Agent Framework**: Abstract base class for building custom agents
- **Prompt Management**: YAML-based prompt templates with parameter injection
- **Progress Tracking**: Context-aware progress updates and todo tracking
- **Session Management**: Multi-session support with automatic cleanup
- **Interactive Console**: Rich terminal interface with slash commands
- **Web Search Integration**: Built-in web search with citation support
- **Example Agent**: Hello Agent demonstrating the framework

## Quick Start

```bash
# Install dependencies
uv sync

# Initialize configuration
agent-kit init

# Set your OpenAI API key
export OPENAI_API_KEY="sk-..."

# Run the interactive console
agent-kit

# Try the hello agent
/hello Alice
/hello Bob
/hello Charlie
```

## Programmatic Usage

You can also use the AgentAPI directly in your Python code:

```python
from agent_kit.api import AgentAPI

# Initialize API
api = AgentAPI()
session_id = await api.session_store.create_session()

# Use hello() for fresh conversations
greeting = await api.hello("Alice", session_id)
print(greeting)

# Use chat() for conversation continuation
response = await api.chat("What's the weather like?", session_id)
print(response)

# Follow-up questions maintain context via OpenAI Responses API
followup = await api.chat("How about tomorrow?", session_id)
print(followup)
```

## Architecture

### Core Components

- **`config/`** - Configuration management with YAML loading
- **`clients/`** - OpenAI client with connection pooling
- **`agents/`** - Base agent and example implementations
- **`prompts/`** - Prompt template system
- **`api/`** - API layer with session management
- **`api/console/`** - Interactive terminal interface

### Hello Agent Example

The Hello Agent demonstrates:
- Extending `BaseAgent` with single `process()` method pattern
- Using prompt templates (markdown format)
- Tool integration (web search, time utilities)
- Conversation continuation via OpenAI Responses API
- Progress updates and reasoning summaries
- Session management with context preservation

See `agent_kit/agents/hello/` for implementation.

## Configuration

Configuration is loaded from `~/.agent-kit/config.yaml`:

```yaml
# OpenAI Configuration
openai:
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-4o"
  pool_size: 8
  reasoning_effort: "medium"

# Logging Configuration
logging:
  level: "INFO"
  max_file_size: 10485760  # 10MB
  backup_count: 5

# Agent Configuration
agents:
  max_iterations: 20
  max_parallel_tools: 5
  enable_todos: false
```

## Building Your Own Agent

1. **Create agent directory**: `agent_kit/agents/myagent/`

2. **Define models** (`models.py`):
```python
from pydantic import BaseModel, Field

class MyRequest(BaseModel):
    model_config = {"extra": "forbid"}  # Required for OpenAI structured output

    query: str = Field(..., description="User query")

class MyResponse(BaseModel):
    model_config = {"extra": "forbid"}  # Required for OpenAI structured output

    result: str = Field(..., description="Agent response")
```

3. **Implement agent** (`agent.py`):
```python
from agent_kit.agents.base_agent import BaseAgent
from agent_kit.clients.openai_client import OpenAIClient
from agent_kit.utils.tools import get_tool_definitions, execute_tool

class MyAgent(BaseAgent):
    def __init__(self, openai_client: OpenAIClient):
        super().__init__(openai_client)

    async def process(self, query: str, continue_conversation: bool = False) -> str:
        """Process query with optional conversation continuation."""
        prompts = self.render_prompt("myagent", "orchestrator")

        response = await self.execute_tool_conversation(
            instructions=prompts["instructions"],
            initial_input=[{"role": "user", "content": query}],
            tools=get_tool_definitions(),  # Optional: add tools
            tool_executor=execute_tool,    # Optional: tool executor
            max_iterations=10,
            previous_response_id=self.last_response_id if continue_conversation else None,
            response_format=None,  # Or MyResponse for structured output
        )

        return response if isinstance(response, str) else response.result
```

4. **Create prompt** (`data/prompts/myagent/orchestrator.yaml`):
```yaml
agent: myagent
function: orchestrator
prompt:
  instructions: |
    # Role and Objective
    You are a helpful assistant that processes user queries.

    # Capabilities
    - Respond to user queries with helpful information
    - Use available tools to enhance responses

    ## Guidelines
    - Be concise and clear
    - Use tools when they provide value

    ## Available Tools
    - `web_search`: Search the web for current information
    - `get_current_time`: Get current time and date

parameters: []
```

5. **Update API layer** to expose your agent in `api/core.py`:
```python
async def my_action(self, query: str, session_id: str) -> str:
    """Execute my agent action."""
    session = self._get_session(session_id)
    agent = session.get_or_create_agent(AgentType.MY_AGENT)
    session.update_last_active(AgentType.MY_AGENT)

    result = await agent.process(query, continue_conversation=True)
    session.store_result(AgentType.MY_AGENT, result, query=query)
    return result
```

## Development

```bash
# Install development dependencies
uv sync --dev

# Run linter
ruff check .

# Run formatter
ruff format .

# Run type checker
pyright

# Run tests
pytest
```

## Project Structure

```
agent-kit-framework/
├── agent_kit/
│   ├── agents/          # Agent implementations
│   │   ├── base_agent.py
│   │   └── hello/       # Example hello agent
│   ├── api/             # API layer
│   │   ├── core.py      # AgentAPI, SessionStore
│   │   ├── models.py    # Data models
│   │   ├── progress.py  # Progress handlers
│   │   └── console/     # Interactive console
│   ├── clients/         # API clients
│   │   ├── base.py      # Connection pooling
│   │   └── openai_client.py
│   ├── config/          # Configuration system
│   │   ├── config.py    # Global config management
│   │   ├── loader.py    # YAML loader
│   │   └── models.py    # Config models
│   ├── prompts/         # Prompt management
│   │   ├── loader.py    # Prompt loader
│   │   └── models.py    # Prompt models
│   ├── utils/           # Utilities
│   │   ├── prompt_debug.py
│   │   └── tools.py     # Tool definitions and executor
│   ├── data/            # Data files
│   │   ├── config/      # Config templates
│   │   └── prompts/     # Prompt templates
│   ├── exceptions.py    # Custom exceptions
│   └── main.py          # CLI entry point
├── pyproject.toml
└── README.md
```

## Key Design Patterns

### 1. Connection Pooling
Efficient OpenAI API usage with connection pool, retry logic, and circuit breakers.

### 2. Conversation Continuation
Uses OpenAI Responses API with `previous_response_id` for seamless conversation flow without storing message history.

### 3. Prompt Templates
YAML-based prompts in markdown format with parameter validation and versioning support.

### 4. Session Management
Thread-safe session store with automatic expiration and context sharing across agents.

### 5. Tool Integration
Centralized tool definitions in `utils/tools.py` supporting both OpenAI native tools (web_search) and custom functions.

### 6. Progress Updates
Context-aware progress emission using Python contextvars with reasoning summary support.

### 7. Single Method Pattern
Agents expose a single `process(query, continue_conversation)` method for both fresh and continued conversations.

## Requirements

- Python 3.13+
- OpenAI API key
- Dependencies managed with `uv`

## License

MIT License (or specify your license here)

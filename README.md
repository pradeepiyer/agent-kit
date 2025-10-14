# Agent Kit

Developer toolkit for building AI agents with OpenAI Responses API.

## Features

- OpenAI Responses API with `previous_response_id` for conversation continuation
- YAML-based configuration and prompt templates
- Connection pooling with retry logic
- Session management with automatic cleanup
- Tool integration (web search, time utilities)
- Interactive console with rich terminal interface

## Quick Start

```bash
# Install and setup
uv sync
agent-kit init
export OPENAI_API_KEY="sk-..."

# Run console
agent-kit

# Try commands
/hello Alice
```

## Programmatic Usage

```python
from agent_kit.api import AgentAPI

api = AgentAPI()
session_id = await api.session_store.create_session()

# Fresh conversation
greeting = await api.hello("Alice", session_id)

# Continued conversation (uses previous_response_id)
response = await api.chat("What's the weather?", session_id)
followup = await api.chat("How about tomorrow?", session_id)
```

## Architecture

```
agent_kit/
├── agents/          # BaseAgent and implementations
├── api/             # AgentAPI, SessionStore, Console
├── clients/         # OpenAI client with pooling
├── config/          # YAML configuration system
├── prompts/         # Prompt template loader
├── utils/           # Tool definitions and utilities
└── data/            # Config and prompt templates
```

## Building Custom Agents

### 1. Define Models

```python
from pydantic import BaseModel

class MyResponse(BaseModel):
    model_config = {"extra": "forbid"}  # Required for structured outputs
    result: str
```

### 2. Implement Agent

```python
from agent_kit.agents.base_agent import BaseAgent
from agent_kit.utils.tools import get_tool_definitions, execute_tool

class MyAgent(BaseAgent):
    async def process(self, query: str, continue_conversation: bool = False) -> str:
        prompts = self.render_prompt("myagent", "orchestrator")

        response = await self.execute_tool_conversation(
            instructions=prompts["instructions"],
            initial_input=[{"role": "user", "content": query}],
            tools=get_tool_definitions(),
            tool_executor=execute_tool,
            previous_response_id=self.last_response_id if continue_conversation else None,
            response_format=None,  # Or MyResponse for structured output
            max_iterations=10
        )

        return response if isinstance(response, str) else response.result
```

### 3. Create Prompt Template

`data/prompts/myagent/orchestrator.yaml`:

```yaml
agent: myagent
function: orchestrator
prompt:
  instructions: |
    # Role
    You are a helpful assistant.

    ## Available Tools
    - `web_search`: Search the web
    - `get_current_time`: Get current time
parameters: []
```

### 4. Add to API

```python
async def my_action(self, query: str, session_id: str) -> str:
    session = self._get_session(session_id)
    agent = session.get_or_create_agent(AgentType.MY_AGENT)
    result = await agent.process(query, continue_conversation=True)
    session.store_result(AgentType.MY_AGENT, result, query=query)
    return result
```

## Configuration

`~/.agent-kit/config.yaml`:

```yaml
openai:
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-4o"
  pool_size: 8
  reasoning_effort: "medium"

agents:
  max_iterations: 20
  enable_todos: false
```

## Development

```bash
# Lint and format
ruff check . && ruff format .

# Type check
pyright

# Test
pytest

# Run CI checks locally
make ci
```

## Key Patterns

- **Conversation Continuation**: Uses `previous_response_id` instead of message arrays
- **Single Method Pattern**: One `process(query, continue_conversation)` method per agent
- **Connection Pooling**: Efficient OpenAI API usage with retry logic
- **YAML Prompts**: Markdown-formatted prompts with parameter injection
- **Tool-First Design**: Centralized tool definitions in `utils/tools.py`

## Requirements

- Python 3.13+
- OpenAI API key
- `uv` package manager

## License

MIT

# Agent Kit

Framework for building AI agents with OpenAI Responses API.

## Features

- Conversation continuation via `previous_response_id` (no message array juggling)
- Session management with automatic cleanup
- YAML-based prompts and configuration
- Connection pooling with retry logic
- Tool integration (web search, time utilities)
- Interactive console with slash commands

## Quick Start

```bash
uv sync
uv run agent-kit init
export OPENAI_API_KEY="sk-..."
uv run agent-kit
```

Try `/hello Alice` or ask questions in chat mode.

## Usage

```python
from agent_kit import SessionStore
from agent_kit.agents.hello.agent import HelloAgent
from agent_kit.config import get_openai_client

# Create session
session_store = SessionStore(get_openai_client())
session_id = await session_store.create_session()
session = await session_store.get_session(session_id)

# Use agent
agent = await session.use_agent(HelloAgent)

# Fresh conversation
response = await agent.process("Greet Alice", continue_conversation=False)

# Continue conversation (uses previous_response_id)
followup = await agent.process("What's the weather?", continue_conversation=True)
```

## Extending

Agent-Kit is designed for extension. See `agent_kit/agents/hello/` for the complete pattern.

### Custom Agent

```python
from agent_kit import BaseAgent

class MyAgent(BaseAgent):
    async def process(self, query: str, continue_conversation: bool = False) -> str:
        prompts = self.render_prompt("my_agent", "orchestrator")

        response = await self.execute_tool_conversation(
            instructions=prompts["instructions"],
            initial_input=[{"role": "user", "content": query}],
            tools=get_tool_definitions(),
            tool_executor=execute_tool,
            previous_response_id=self.last_response_id if continue_conversation else None,
        )

        return response.output_text or "Error"
```

### Agent Structure

```
my_agents/analyzer/
├── agent.py          # Implements BaseAgent
├── tools.py          # Tool definitions and executor
├── console.py        # Optional: slash commands
├── config.yaml       # Agent-specific config
└── prompts/
    └── orchestrator.yaml
```

### Console Commands

```python
from agent_kit.api.console.server import SlashCommands
from rich.console import Console

class MyCommands(SlashCommands):
    def __init__(self, console: Console):
        super().__init__(console)

        # Register commands
        self.register_command(
            "/analyze",
            self._handle_analyze,
            "Run analysis",
            "Analyze data\nUsage: /analyze <topic>"
        )

    async def _handle_analyze(self, args: list[str]) -> None:
        # Your implementation
        pass

# Run console
await run_console(MyCommands)
```

### Configuration

Framework config (`~/.agent-kit/config.yaml`):
```yaml
openai:
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-4o"
  pool_size: 8

agents:
  max_iterations: 20
```

Agent config (`~/.agent-kit/my_agent.yaml`):
```yaml
max_iterations: 15
```

Configs auto-loaded from:
- `agent_kit/agents/{agent}/config.yaml` (package defaults)
- `~/.agent-kit/{agent}.yaml` (user overrides)

## Development

```bash
uv run ruff check . && uv run ruff format .  # Lint and format
uv run pyright                                # Type check
uv run pytest                                 # Test
make ci                                       # Run all checks
```

## Requirements

- Python 3.13+
- OpenAI API key
- uv package manager

## License

MIT

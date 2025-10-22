# Agent Kit

Pure Python library for building AI agents with OpenAI Responses API.

## Features

- Conversation continuation via `previous_response_id` (no message array juggling)
- Session management with automatic cleanup
- YAML-based prompts and configuration
- Connection pooling with retry logic
- Tool integration (web search, time utilities)
- Interactive console with slash commands

## Quick Start

Install agent-kit as a library:
```bash
uv add agent-kit
# or: pip install agent-kit
```

Try the hello agent example:
```bash
git clone https://github.com/yourusername/agent-kit
cd agent-kit
uv sync
export OPENAI_API_KEY="sk-..."
uv run python -m agents.hello
# or: make console
```

The hello agent demonstrates the framework patterns and uses `~/.hello-agent` for its configuration.

## Usage

```python
from agent_kit import SessionStore
from agents.hello.agent import HelloAgent
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

Agent-Kit is designed for extension. See `agents/hello/` for the complete pattern.

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

### Customizing User Directory

By default, agent-kit auto-detects your application name and uses `~/.{app-name}` for configuration. You can customize this:

```python
# In your application's entry point (before any agent-kit imports)
from agent_kit.utils import set_app_name

set_app_name("my-awesome-agent")  # Uses ~/.my-awesome-agent
```

Example from hello agent (`agents/hello/__main__.py`):
```python
from agent_kit.utils import set_app_name
set_app_name("hello-agent")  # Uses ~/.hello-agent instead of ~/.agent-kit
```

Auto-detection priority:
1. Explicitly set via `set_app_name()`
2. Environment variable `AGENT_KIT_APP_NAME`
3. Auto-detect from `__main__` module name
4. Fallback to `"agent-kit"`

### Configuration

Framework config (`~/.{app-name}/config.yaml`):
```yaml
openai:
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-4o"
  pool_size: 8

agents:
  max_iterations: 20
```

Agent config (`~/.{app-name}/my_agent.yaml`):
```yaml
max_iterations: 15
```

Configs auto-loaded from:
- `./agents/{agent}/config.yaml` (project defaults)
- `~/.{app-name}/{agent}.yaml` (user overrides)

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

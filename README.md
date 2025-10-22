# Agent Kit

Pure Python library for building AI agents with OpenAI Responses API.

## Features

- **Multiple Interfaces**: Console, REST API with SSE streaming, and MCP (Model Context Protocol)
- **Conversation Continuation**: Via `previous_response_id` (no message array juggling)
- **Session Management**: Automatic cleanup with configurable TTL
- **Progress Reporting**: Unified progress handling across all interfaces
- **YAML Configuration**: Prompts and configuration with environment variable substitution
- **Connection Pooling**: With retry logic and timeout handling
- **Tool Integration**: Web search, time utilities, and custom tools
- **Agent Registry**: Dynamic route and tool generation for HTTP protocols

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
from agent_kit.api.progress import ConsoleProgressHandler
from agents.hello.agent import HelloAgent
from agent_kit.config import get_openai_client
from rich.console import Console

# Create session with progress handler
console = Console()
progress_handler = ConsoleProgressHandler(console)
session_store = SessionStore(get_openai_client())
session_id = await session_store.create_session(progress_handler)
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
from agent_kit.api.progress import ProgressHandler
from agent_kit.clients.openai_client import OpenAIClient

class MyAgent(BaseAgent):
    def __init__(self, openai_client: OpenAIClient, progress_handler: ProgressHandler):
        super().__init__(openai_client, progress_handler)

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

### HTTP Interfaces (REST and MCP)

Agent-Kit supports REST API with SSE streaming and MCP protocol for Claude Desktop integration.

#### Registry Setup

```python
from agent_kit.api.http import AgentRegistry, create_server
from agent_kit.config import get_config
from pydantic import BaseModel, Field

# Define request/response models
class MyRequest(BaseModel):
    query: str = Field(..., description="User query")
    session_id: str | None = None

class MyResponse(BaseModel):
    response: str = Field(..., description="Agent response")
    session_id: str

# Create registry and register agents
registry = AgentRegistry()
registry.register(
    name="my_agent",
    agent_class=MyAgent,
    description="My agent description for API docs and MCP tools",
    request_model=MyRequest,
    response_model=MyResponse,
)

# Create HTTP server
config = get_config()
app = create_server(registry, config.interfaces.http, config.interfaces.session_ttl)
```

#### Running the Server

```bash
# Or via configuration-driven entry point (see hello agent example)
uv run python -m agents.hello  # Starts interface based on config
```

#### REST API Endpoints

- `POST /api/v1/sessions` - Create session
- `GET /api/v1/sessions/{id}` - Get session info
- `DELETE /api/v1/sessions/{id}` - Delete session
- `POST /api/v1/{agent_name}` - Execute agent (SSE streaming)
- `GET /api/v1/health` - Health check
- `GET /api/v1/info` - API information

#### MCP Integration

MCP tools are automatically generated from registered agents. Two modes are supported:

**HTTP Mode**: Mount at `/mcp` for web-based access
- Enable via `interfaces.http.mcp_http: true` in config
- Access tools via HTTP transport at configured mount path

**Stdio Mode**: For Claude Desktop integration
- Enable via `interfaces.mcp_stdio.enabled: true` in config
- Configure Claude Desktop:

```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "hello-agent": {
      "command": "uv",
      "args": ["run", "python", "-m", "agents.hello"]
    }
  }
}
```

Note: Only one interface can be active at a time. Stdio mode requires disabling console and HTTP interfaces in config.

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

interfaces:
  session_ttl: 3600  # Shared across all interfaces

  http:                # HTTP server for REST/MCP
    enabled: false
    host: "0.0.0.0"
    port: 8000
    cors_origins: ["http://localhost:*"]
    rest_api: true     # Enable REST endpoints
    mcp_http: true     # Enable MCP over HTTP
    mcp_mount_path: "/mcp"

  console:
    enabled: true

  mcp_stdio:
    enabled: false     # MCP stdio for Claude Desktop
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

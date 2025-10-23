# Agent Kit

Python library for building AI agents with OpenAI Responses API.

## Features

- **Multiple Interfaces**: Console, REST API with SSE, and MCP
- **Conversation Continuation**: Via `previous_response_id`
- **Session Management**: Automatic cleanup with configurable TTL
- **Agent Registry**: Dynamic route and tool generation

## Quick Start

```bash
git clone https://github.com/pradeepiyer/agent-kit
cd agent-kit
uv sync
export OPENAI_API_KEY="sk-..."
uv run python -m agents.hello
```

## Extending

See `agents/hello/` for complete examples.

### Console Commands

```python
from agent_kit.api.console.server import SlashCommands

class MyCommands(SlashCommands):
    def __init__(self, console):
        super().__init__(console)
        self.register_command("/analyze", self._handle_analyze, "Run analysis")

    async def _handle_analyze(self, args: list[str]) -> None:
        pass
```

### HTTP Server (REST + MCP)

```python
from agent_kit.api.http import AgentRegistry, create_server

registry = AgentRegistry()
registry.register(
    name="my_agent",
    agent_class=MyAgent,
    description="Agent description",
    request_model=MyRequest,
    response_model=MyResponse,
)

config = get_config()
app = create_server(registry, config.interfaces.http, config.interfaces.session_ttl)
```

#### REST Endpoints

- `POST /api/v1/{agent_name}` - Execute agent (SSE streaming)
- `POST /api/v1/sessions` - Create session
- `GET /api/v1/sessions/{id}` - Get session

#### MCP Integration

**HTTP Mode**: Enable via `interfaces.http.mcp_http: true`

**Stdio Mode** (Claude Desktop):
```json
{
  "mcpServers": {
    "hello-agent": {
      "command": "uv",
      "args": ["run", "python", "-m", "agents.hello"]
    }
  }
}
```

### Configuration

`~/.{app-name}/config.yaml`:
```yaml
openai:
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-4o"

interfaces:
  session_ttl: 3600

  http:
    enabled: false
    port: 8000
    rest_api: true
    mcp_http: true

  console:
    enabled: true

  mcp_stdio:
    enabled: false
```

## Development

```bash
uv run ruff check . && uv run ruff format .
uv run pyright
uv run pytest
```

## Requirements

- Python 3.13+
- OpenAI API key
- uv package manager

## License

MIT

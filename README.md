# Rexi MCP Server

An MCP (Model Context Protocol) server that wraps the Rexi API and exposes tools and resources for AI assistants.

## Features

### Tools
- **`list_endpoints(tag: Optional[str])`** – Lists all API endpoints discovered from `docs/openapi.generated.yaml`, optionally filtered by tag.
- **`call_rexi(...)`** – Generic caller for any Rexi API endpoint with full parameter support:
  - `method`: HTTP method (GET, POST, PUT, PATCH, DELETE, etc.)
  - `path`: API path (e.g., `/v1/contracts/{contract_address}`)
  - `path_params`: Dictionary to substitute `{placeholders}` in the path
  - `query`: Query parameters as key-value pairs
  - `body`: Request body (sent as JSON)
  - `extra_headers`: Additional HTTP headers
  - `timeout_seconds`: Request timeout (default: 30s)

### Resources
- **`rexi://openapi`** – Raw OpenAPI YAML specification
- **`rexi://routes`** – JSON summary of all methods, paths, summaries, and tags
- **`rexi://schemas`** – JSON array of available schema filenames
- **`rexi-schemas://{name}`** – Contents of a specific schema file from `schema/` directory

## Requirements

- **Python 3.10+**
- **Dependencies**: Install via `pip install -r requirements.txt`
  - `mcp[cli]` – MCP SDK with CLI tools
  - `httpx` – Async HTTP client
  - `PyYAML` – YAML parser for OpenAPI spec
  - `python-dotenv` – Environment variable management
- **Rexi API Key** (optional but recommended): Set via `REXI_API_KEY` environment variable

### Environment Setup

Create a `.env` file in the project root (see `.env.example`):
```bash
REXI_API_KEY=your_api_key_here
```

Environment variables are loaded automatically when the server starts.

## Running with the MCP CLI (Inspector)

From the project root:

```bash
uv run mcp dev mcp/server.py
# or with pipx / pip if you installed the CLI another way:
# mcp dev mcp/server.py
```

This opens the MCP Inspector to interactively test tools and resources.

## Install into Claude Desktop (or other hosts)

```bash
uv run mcp install mcp/server.py \
  -v REXI_API_KEY=your_api_key_here
```

You can also pass `-f .env` to load environment variables from a file.

## Configuration

The server determines the base URL from the OpenAPI spec `servers[0].url`. If not found, it defaults to `https://api.rexi.sh`.

- Auth header: `x-api-key` populated from `REXI_API_KEY` env var if present.
- OpenAPI file path: `docs/openapi.generated.yaml`.
- Schema directory: `schema/`.


## Notes

- When calling `call_rexi`, supply any required `path_params` to fill placeholders like `{contract_address}` in the `path` you pass.
- `query` and `body` are sent as query parameters and JSON body respectively.
- The server validates nothing beyond basic substitution; refer to the schemas under `schema/` for expected shapes.
- All context parameters (`ctx`) are automatically injected by FastMCP - you don't need to pass them manually.

## Troubleshooting

### Import Errors
If you get import errors for `mcp`, ensure you've installed the dependencies:
```bash
pip install -r requirements.txt
```

### API Key Issues
If API calls fail with authentication errors, verify your `REXI_API_KEY` is set correctly in your `.env` file or environment.

### Missing OpenAPI/Schema Files
The server gracefully handles missing `docs/openapi.generated.yaml` and `schema/` directory. If these files are missing:
- `list_endpoints()` will return an empty list
- Resources will return appropriate error messages
- The server will still start and run

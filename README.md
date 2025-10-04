# Rexi MCP Server

This folder contains an MCP server that wraps the Rexi API and exposes:

- **Tools**:
  - `list_endpoints(tag: Optional[str])` – lists endpoints discovered from `docs/openapi.generated.yaml`.
  - `call_rexi(method, path, path_params?, query?, body?, extra_headers?, timeout_seconds?)` – generic caller for any endpoint in the OpenAPI.
- **Resources**:
  - `rexi://openapi` – raw OpenAPI YAML.
  - `rexi://routes` – JSON summary of methods, paths, summaries, tags.
  - `rexi://schemas` – JSON array of available schema filenames.
  - `rexi-schemas://{name}` – returns the contents of a schema file by name (from `schema/`).

## Requirements

- Python 3.10+
- Dependencies in project `requirements.txt` (including `mcp[cli]`, `httpx`, `PyYAML`, `python-dotenv`).
- Rexi API key (optional but recommended) via env var `REXI_API_KEY`.

You can place environment variables in a `.env` file at the repo root; they will be loaded automatically.

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

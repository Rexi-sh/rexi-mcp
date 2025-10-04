import os
import re
import json
import glob
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import sys
import site
import httpx
import yaml

# Ensure site-packages precedes the project root so the external 'mcp' SDK resolves
try:
    site_paths: List[str] = []
    try:
        site_paths.extend(site.getsitepackages())
    except Exception:
        pass
    try:
        usp = site.getusersitepackages()
        if isinstance(usp, str):
            site_paths.append(usp)
        elif isinstance(usp, list):
            site_paths.extend(usp)
    except Exception:
        pass
    for sp in site_paths:
        if sp and sp not in sys.path:
            sys.path.insert(0, sp)
except Exception:
    pass

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

# Load environment variables from a .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


OPENAPI_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "openapi.generated.yaml")
SCHEMA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schema")
DEFAULT_BASE_URL = "https://api.rexi.sh"
API_KEY_ENV = "REXI_API_KEY"
API_KEY_HEADER = "x-api-key"


@dataclass
class AppState:
    base_url: str
    api_key: Optional[str]
    openapi: Dict[str, Any]
    endpoints: List[Dict[str, Any]]
    schemas_index: List[str]


def _load_openapi() -> Dict[str, Any]:
    if not os.path.exists(OPENAPI_PATH):
        return {}
    with open(OPENAPI_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _discover_base_url_from_openapi(openapi: Dict[str, Any]) -> Optional[str]:
    try:
        servers = openapi.get("servers", [])
        if servers and isinstance(servers, list):
            url = servers[0].get("url")
            if isinstance(url, str) and url:
                return url
    except Exception:
        pass
    return None


def _iter_http_methods() -> List[str]:
    # HTTP methods commonly used in OpenAPI path objects
    return [
        "get", "post", "put", "patch", "delete", "head", "options"
    ]


def _extract_endpoints(openapi: Dict[str, Any]) -> List[Dict[str, Any]]:
    endpoints: List[Dict[str, Any]] = []
    paths = openapi.get("paths", {}) if isinstance(openapi, dict) else {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in _iter_http_methods():
            if method in path_item:
                op = path_item[method] or {}
                summary = op.get("summary") or op.get("operationId") or f"{method.upper()} {path}"
                parameters = op.get("parameters", [])
                request_body = op.get("requestBody")
                endpoints.append({
                    "method": method.upper(),
                    "path": path,
                    "summary": summary,
                    "parameters": parameters,
                    "has_request_body": request_body is not None,
                    "tags": op.get("tags", []),
                })
    return endpoints


def _load_schemas_index() -> List[str]:
    if not os.path.isdir(SCHEMA_DIR):
        return []
    files = sorted(glob.glob(os.path.join(SCHEMA_DIR, "*.json")))
    return [os.path.basename(p) for p in files]


def _substitute_path_params(path_template: str, path_params: Dict[str, Any]) -> str:
    # Replace {param} occurrences in path with provided values
    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key not in path_params:
            raise ValueError(f"Missing path parameter: {key}")
        return str(path_params[key])

    return re.sub(r"\{([^}/]+)\}", repl, path_template)


# Lifespan to load OpenAPI + schemas and determine base URL
@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[AppState]:
    openapi = _load_openapi()
    base = _discover_base_url_from_openapi(openapi) or DEFAULT_BASE_URL
    api_key = os.getenv(API_KEY_ENV)
    endpoints = _extract_endpoints(openapi)
    schemas_index = _load_schemas_index()

    state = AppState(
        base_url=base,
        api_key=api_key,
        openapi=openapi,
        endpoints=endpoints,
        schemas_index=schemas_index,
    )
    try:
        yield state
    finally:
        # nothing to clean up currently
        pass


# Recreate FastMCP with lifespan so ctx.request_context.lifespan_context is set
mcp = FastMCP(
    name="Rexi API MCP Server",
    instructions=(
        "MCP server wrapping Rexi API. Use 'list_endpoints' to discover routes and 'call_rexi' to call them. "
        "OpenAPI spec and JSON schemas are available as resources."
    ),
    website_url="https://api.rexi.sh",
    lifespan=lifespan,
)


# Re-register tools and resources on the new mcp instance
@mcp.tool()
async def list_endpoints(
    tag: Optional[str] = None,
    ctx: Context[ServerSession, AppState] = None,
) -> List[Dict[str, Any]]:
    endpoints = ctx.request_context.lifespan_context.endpoints
    if tag:
        return [e for e in endpoints if tag in (e.get("tags") or [])]
    return endpoints


@mcp.tool()
async def call_rexi(
    method: str,
    path: str,
    path_params: Optional[Dict[str, Any]] = None,
    query: Optional[Dict[str, Any]] = None,
    body: Optional[Any] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    timeout_seconds: float = 30.0,
    ctx: Context[ServerSession, AppState] = None,
) -> Dict[str, Any]:
    await ctx.info(f"Calling {method.upper()} {path}")
    state = ctx.request_context.lifespan_context
    base_url = state.base_url

    path_params = path_params or {}
    query = query or {}
    headers: Dict[str, str] = {
        "accept": "application/json",
    }
    if state.api_key:
        headers[API_KEY_HEADER] = state.api_key
    if extra_headers:
        headers.update({k: str(v) for k, v in extra_headers.items()})

    url_path = _substitute_path_params(path, path_params) if "{" in path else path
    url = base_url.rstrip("/") + "/" + url_path.lstrip("/")

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.request(method.upper(), url, params=query, json=body, headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {"text": resp.text}
        return {
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "url": str(resp.request.url),
            "data": data,
        }


@mcp.resource("rexi://openapi")
def get_openapi_spec(ctx: Context[ServerSession, AppState]) -> str:
    if not os.path.exists(OPENAPI_PATH):
        return "OpenAPI spec not found."
    with open(OPENAPI_PATH, "r", encoding="utf-8") as f:
        return f.read()


@mcp.resource("rexi://routes")
def get_routes_index(ctx: Context[ServerSession, AppState]) -> str:
    endpoints = ctx.request_context.lifespan_context.endpoints
    return json.dumps(endpoints, indent=2)


@mcp.resource("rexi-schemas://{name}")
def get_schema_file(name: str, ctx: Context[ServerSession, AppState]) -> str:
    safe_name = os.path.basename(name)
    path = os.path.join(SCHEMA_DIR, safe_name)
    if not os.path.isfile(path):
        return json.dumps({"error": f"schema '{safe_name}' not found"})
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@mcp.resource("rexi://schemas")
def list_schema_files(ctx: Context[ServerSession, AppState]) -> str:
    files = ctx.request_context.lifespan_context.schemas_index
    return json.dumps(files, indent=2)


def main() -> None:
    # Run with stdio by default; use `uv run mcp dev mcp/server.py` for inspector
    mcp.run()


if __name__ == "__main__":
    main()

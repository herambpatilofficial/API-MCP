# API MCP Server (Python)

A lightweight and extensible MCP server for defining and executing API tools,
written in Python. This is a faithful port of
[AdamShannag/api-mcp-server](https://github.com/AdamShannag/api-mcp-server).

It reads a JSON file describing HTTP-backed tools, exposes them over the
[Model Context Protocol](https://modelcontextprotocol.io), and executes them as
HTTP requests. Supports `stdio` and `sse` transports, typed arguments,
environment-variable substitution and optional Bearer authentication.

## Installation

```bash
pip install .            # stdio support (mcp + httpx)
pip install ".[all]"     # + SSE (starlette/uvicorn) and metrics (prometheus-client)
```

This installs the `api-mcp-server-py` console script (named to avoid clashing
with the Go binary). You can also run it as a module: `python -m api_mcp_server`.

## Usage

```bash
api-mcp-server-py -t stdio -c ./examples/jsonplaceholder.tools.json
api-mcp-server-py -t sse   -c ./examples/jsonplaceholder.tools.json
```

### CLI flags

| Flag | Description | Default |
| --- | --- | --- |
| `-t`, `--transport` | Transport type: `stdio` or `sse` | `stdio` |
| `-c`, `--config` | Path to JSON tool configuration | `./config.json` |
| `-v`, `--version` | Show version and exit | - |
| `-m`, `--metrics` | Enable Prometheus metrics and health check server | - |
| `--metrics-port` | Metrics and health check server port | `8080` |

### Environment variables

| Variable | Description | Default |
| --- | --- | --- |
| `API_MCP_HOST` | SSE host to bind to | `127.0.0.1` |
| `API_MCP_PORT` | SSE port to bind to | `13080` |
| `API_MCP_SSE_API_KEY` | Optional Bearer token for SSE auth | *(none)* |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARN`, `ERROR` | `INFO` |

## Tool configuration

Each tool has a `name`, a `description`, a `request` object and an optional
list of `args`.

```json
{
  "name": "GetTodo",
  "description": "Retrieves a specific todo item by its ID",
  "request": {
    "host": "{{env API_HOST:jsonplaceholder.typicode.com}}",
    "endpoint": "/todos/:id",
    "method": "GET",
    "secure": true,
    "pathParams": ["id"]
  },
  "args": [
    {
      "name": "id",
      "description": "The unique identifier of the todo item to retrieve.",
      "required": true,
      "type": "int"
    }
  ]
}
```

### Request fields

- `host` – target API domain (env placeholders supported).
- `method` – HTTP method (`GET`, `POST`, `PUT`, ...).
- `secure` – `true` uses `https`, otherwise `http`.
- `endpoint` – path, with `:name` placeholders for path parameters.
- `pathParams` – argument names substituted into the endpoint (URL-encoded).
- `queryParams` – argument names appended as query-string parameters.
- `body` – the name of the argument whose value is sent as the raw body.
- `headers` – static or dynamic headers (env placeholders supported).

### Arguments

Each argument has `name`, `description`, `required`, `type` and an optional
`defaultValue`. Supported types: `string`, `int` (`integer`), `float`
(`number`), `bool` (`boolean`); unknown types fall back to `string`.

### Environment placeholders

`{{env VAR_NAME:default_value}}` is replaced at load time with the value of the
environment variable, or `default_value` when the variable is unset/empty.

## Client configuration (opencode)

Add the server to `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "api": {
      "type": "local",
      "command": [
        "api-mcp-server-py",
        "-t", "stdio",
        "-c", "E:\\Atlasea\\api-mcp-server-py\\examples\\jsonplaceholder.tools.json"
      ],
      "environment": { "API_HOST": "jsonplaceholder.typicode.com" }
    }
  }
}
```

For the SSE transport, run the server and point a `"type": "remote"` client at
`http://<host>:<port>/sse`, adding `Authorization: Bearer <key>` when
`API_MCP_SSE_API_KEY` is set.

## Security note

Only expose tools whose APIs you trust. Path/query arguments are URL-encoded,
but argument values are otherwise passed through to the configured host. The
SSE Bearer token is optional; enable it whenever the endpoint is reachable
beyond localhost.

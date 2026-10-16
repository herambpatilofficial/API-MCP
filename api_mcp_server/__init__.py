"""A lightweight and extensible MCP server for defining and executing API tools.

Python port of https://github.com/AdamShannag/api-mcp-server
"""

from .config import load_tools, resolve_env_placeholders
from .executor import ExecutorError, HttpExecutor
from .models import Arg, Request, Tool
from .server import VERSION, ApiMcpServer

__version__ = VERSION

__all__ = [
    "ApiMcpServer",
    "Arg",
    "ExecutorError",
    "HttpExecutor",
    "Request",
    "Tool",
    "VERSION",
    "__version__",
    "load_tools",
    "resolve_env_placeholders",
]

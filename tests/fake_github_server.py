"""fake_github_server.py - a local stand-in for GitHub's MCP server.

It has the same tool names that the examples use, and it marks `owner` and
`repo` with `x-mcp-header`, like the real server does. The data is fake.

    python tests/fake_github_server.py 8765
"""
import sys
import time
from typing import Annotated

import uvicorn
from pydantic import Field
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("fake-github")
Owner = Annotated[str, Field(json_schema_extra={"x-mcp-header": "Owner"})]
Repo = Annotated[str, Field(json_schema_extra={"x-mcp-header": "Repo"})]


@mcp.tool()
def get_latest_release(owner: Owner, repo: Repo) -> dict:
    time.sleep(0.05)  # a little network time
    if repo == "missing":
        raise ValueError("Not Found")
    return {"tag_name": f"v1.0-{owner}-{repo}", "name": "release"}


@mcp.tool()
def get_me() -> dict:
    return {"login": "tester"}


@mcp.tool()
def slow() -> str:
    time.sleep(3)  # long enough to cancel
    return "done"


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=port, log_level="warning")

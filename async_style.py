"""async_style.py - the same agent the way most tutorials write it."""
import asyncio
import json
import os

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

URL = os.environ.get("GITHUB_MCP_URL", "https://api.githubcopilot.com/mcp/")


async def call_json(client, tool, arguments):  # async ...
    result = await client.call_tool(tool, arguments)
    return json.loads(result.content[0].text)


async def latest_release(client, repo):  # ... so this must be async ...
    owner, name = repo.split("/")
    args = {"owner": owner, "repo": name}
    return (await call_json(client, "get_latest_release", args))["tag_name"]


async def report(client, repos):  # ... and this ...
    jobs = [latest_release(client, repo) for repo in repos]
    return await asyncio.gather(*jobs)


async def main():  # ... all the way up
    headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}
    async with httpx2.AsyncClient(headers=headers) as http:
        transport = streamable_http_client(URL, http_client=http)
        async with Client(transport) as client:
            await client.list_tools()
            repos = ["github/github-mcp-server",
                     "modelcontextprotocol/python-sdk"]
            print(await report(client, repos))

asyncio.run(main())

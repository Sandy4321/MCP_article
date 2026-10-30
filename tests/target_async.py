"""Target for debug_console_check.py: the usual all-async design."""
import asyncio
import os

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


async def main():
    async with httpx2.AsyncClient() as http:
        transport = streamable_http_client(os.environ["MCP_URL"], http_client=http)
        async with Client(transport) as gh:
            await gh.list_tools()
            result = await gh.call_tool("get_me", {})
            print("paused here")  # BREAKPOINT

asyncio.run(main())

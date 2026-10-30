"""mcp_bridge.py - the async MCP SDK behind a plain, blocking API."""
import asyncio
import concurrent.futures
import sys
import threading
from contextlib import asynccontextmanager

import httpx2  # installed together with mcp 2.x
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"


class SyncMCP:
    """One background thread owns the event loop and the MCP session.
    Your code calls normal blocking methods, from any thread."""

    def __init__(self, open_client, timeout=60.0):
        self.timeout = timeout
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, name="mcp-loop", daemon=True)
        self._thread.start()
        self._ready = concurrent.futures.Future()
        self._owner = asyncio.run_coroutine_threadsafe(
            self._own(open_client), self._loop)
        try:
            self._ready.result(timeout)  # connection errors are raised here
        except BaseException:
            self._owner.cancel()  # don't leave the thread behind
            self.close()
            raise

    def _run_loop(self):
        _keep_running_when_paused()
        self._loop.run_forever()

    async def _own(self, open_client):
        self._stop = asyncio.Event()
        try:
            # one task opens AND closes the session (an anyio rule)
            async with open_client() as client:
                self._client, self.tools, cursor = client, [], None
                while True:  # read the whole menu before the first call
                    page = await client.list_tools(cursor=cursor)
                    self.tools += page.tools
                    if not (cursor := page.next_cursor):
                        break
                self._ready.set_result(None)
                await self._stop.wait()
        except BaseException as exc:
            if not self._ready.done():
                self._ready.set_exception(exc)
            raise

    def start_tool(self, name, arguments=None):
        """Start a call and return a Future at once (it can be cancelled)."""
        if threading.current_thread() is self._thread:
            raise RuntimeError("never call SyncMCP from its own loop")
        call = self._client.call_tool(
            name, arguments or {}, read_timeout_seconds=self.timeout)
        return asyncio.run_coroutine_threadsafe(call, self._loop)

    def call_tool(self, name, arguments=None):
        """Call a tool and wait for the result, like a normal function."""
        return self.start_tool(name, arguments).result(self.timeout + 5)

    def close(self):
        self._loop.call_soon_threadsafe(self._stop.set)
        concurrent.futures.wait([self._owner], timeout=10)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        if not self._thread.is_alive():
            self._loop.close()


def _keep_running_when_paused():
    """VS Code (debugpy): don't freeze this thread at your breakpoints."""
    try:
        debugpy = sys.modules.get("debugpy")
        if debugpy and debugpy.is_client_connected():
            debugpy.trace_this_thread(False)
    except Exception:
        pass  # debugpy is loaded but not debugging this process


def github(token, url=None):
    """GitHub's official MCP server, read-only tools."""
    headers = {"Authorization": f"Bearer {token}",
               "X-MCP-Readonly": "true"}

    @asynccontextmanager
    async def open_client():
        timeout = httpx2.Timeout(30, read=300)
        async with httpx2.AsyncClient(headers=headers,
                                      timeout=timeout) as http:
            transport = streamable_http_client(url or GITHUB_MCP_URL,
                                               http_client=http)
            async with Client(transport) as client:
                yield client

    return SyncMCP(open_client)


def text_of(result):
    """The text blocks of a tool result, joined."""
    return "\n".join(b.text for b in result.content if b.type == "text")

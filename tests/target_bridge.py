"""Target for debug_console_check.py: the plain, threaded design."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mcp_bridge  # noqa: E402

gh = mcp_bridge.github("not-needed", url=os.environ["MCP_URL"])
result = gh.call_tool("get_me", {})
print("paused here")  # BREAKPOINT
gh.close()

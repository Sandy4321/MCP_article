"""agent_example.py - nested plain functions + threads, one MCP session."""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from mcp_bridge import github, text_of


def call_json(gh, tool, arguments):
    result = gh.call_tool(tool, arguments)  # F10 steps over the call
    if result.is_error:  # errors should never pass silently
        raise RuntimeError(f"{tool}: {text_of(result)}")
    return json.loads(text_of(result))


def latest_release(gh, repo):
    owner, name = repo.split("/")
    args = {"owner": owner, "repo": name}
    return call_json(gh, "get_latest_release", args)["tag_name"]


def report(gh, repos, serial=False):
    if serial:  # one job at a time: follow it end to end
        return [latest_release(gh, repo) for repo in repos]
    with ThreadPoolExecutor(max_workers=8) as pool:  # one shared session
        return list(pool.map(lambda repo: latest_release(gh, repo), repos))


if __name__ == "__main__":
    gh = github(os.environ["GITHUB_TOKEN"])
    try:
        repos = ["github/github-mcp-server", "modelcontextprotocol/python-sdk"]
        print(report(gh, repos, serial="--serial" in sys.argv))
    finally:
        gh.close()

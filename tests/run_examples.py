"""run_examples.py - run the three examples against the local fake server.

    python tests/run_examples.py

No GitHub token is needed. Exit code 0 means that all checks passed.
"""
import os
import runpy
import socket
import subprocess
import sys
import threading
import time
from contextlib import redirect_stdout
from io import StringIO

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

EXPECTED = ["v1.0-github-github-mcp-server", "v1.0-modelcontextprotocol-python-sdk"]
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(port):
    server = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "fake_github_server.py"), str(port)],
        stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            return server
        except OSError:
            time.sleep(0.1)
    server.kill()
    raise RuntimeError("the fake server did not start")


def run_script(name, *args):
    """Run an example as __main__ and return what it printed."""
    sys.argv = [name, *args]
    out = StringIO()
    with redirect_stdout(out):
        runpy.run_path(os.path.join(ROOT, name), run_name="__main__")
    return out.getvalue().strip()


def main():
    port = free_port()
    url = f"http://127.0.0.1:{port}/mcp"
    os.environ["GITHUB_TOKEN"] = "not-needed"
    os.environ["GITHUB_MCP_URL"] = url  # async_style.py reads this
    server = start_server(port)
    try:
        import mcp_bridge
        from agent_example import call_json, report
        mcp_bridge.GITHUB_MCP_URL = url  # agent_example.py uses the default URL

        check("agent_example.py (threads)", run_script("agent_example.py") == str(EXPECTED))
        check("agent_example.py --serial", run_script("agent_example.py", "--serial") == str(EXPECTED))
        check("async_style.py", run_script("async_style.py") == str(EXPECTED))

        gh = mcp_bridge.github("not-needed", url=url)
        check("tool list is read at start", {"get_latest_release", "get_me"} <= {t.name for t in gh.tools})
        try:
            call_json(gh, "get_latest_release", {"owner": "x", "repo": "missing"})
            check("a failed tool result raises", False)
        except RuntimeError as exc:
            check("a failed tool result raises", True, str(exc))

        future = gh.start_tool("slow")
        time.sleep(0.3)
        check("a running call can be cancelled", future.cancel() and future.cancelled())

        start = time.perf_counter()
        report(gh, [f"o/r{i}" for i in range(16)], serial=True)
        serial = time.perf_counter() - start
        start = time.perf_counter()
        report(gh, [f"o/r{i}" for i in range(16)])
        threaded = time.perf_counter() - start
        check("threads share one session", threaded < serial, f"16 calls: {serial:.2f} s serial, {threaded:.2f} s threads")

        gh.close()
        check("close() stops the thread and the loop", not gh._thread.is_alive() and gh._loop.is_closed())

        try:
            mcp_bridge.github("not-needed", url="http://127.0.0.1:1/mcp")
            check("a bad URL raises", False)
        except BaseException as exc:  # anyio reports it as an ExceptionGroup
            check("a bad URL raises", True, type(exc).__name__)
        time.sleep(0.2)
        check("no thread is left behind", [t.name for t in threading.enumerate()] == ["MainThread"])
    finally:
        server.terminate()
    print(f"\n{sum(results)} of {len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

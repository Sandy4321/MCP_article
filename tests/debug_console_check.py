"""debug_console_check.py - the pause-and-ask test, driven through debugpy.

    python tests/debug_console_check.py

It starts each target program under debugpy, stops at its breakpoint and
types tool calls into the Debug Console, like VS Code does. Needs debugpy.
"""
import json
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
results = []


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class DebugAdapter:
    """A minimal Debug Adapter Protocol client."""

    def __init__(self, port):
        for _ in range(100):
            try:
                self.sock = socket.create_connection(("127.0.0.1", port))
                break
            except OSError:
                time.sleep(0.1)
        self.buffer, self.seq = b"", 0

    def send(self, command, **arguments):
        self.seq += 1
        body = json.dumps({"seq": self.seq, "type": "request",
                           "command": command, "arguments": arguments}).encode()
        self.sock.sendall(b"Content-Length: %d\r\n\r\n" % len(body) + body)
        return self.seq

    def receive(self, timeout):
        self.sock.settimeout(timeout)
        while b"\r\n\r\n" not in self.buffer:
            self.buffer += self.sock.recv(65536)
        head, rest = self.buffer.split(b"\r\n\r\n", 1)
        length = int(head.split(b":")[1])
        while len(rest) < length:
            rest += self.sock.recv(65536)
        self.buffer = rest[length:]
        return json.loads(rest[:length])

    def wait(self, match, timeout):
        end = time.time() + timeout
        while True:
            left = end - time.time()
            if left <= 0:
                raise TimeoutError
            message = self.receive(left)
            if match(message):
                return message

    def answer(self, seq, timeout):
        return self.wait(lambda m: m.get("request_seq") == seq, timeout)


def pause_and_ask(target, expressions, timeout=15):
    """Stop at the '# BREAKPOINT' line of target and evaluate each expression."""
    server_port, debug_port = free_port(), free_port()
    env = dict(os.environ, MCP_URL=f"http://127.0.0.1:{server_port}/mcp", PYDEVD_DISABLE_FILE_VALIDATION="1")
    server = subprocess.Popen([sys.executable, os.path.join(HERE, "fake_github_server.py"), str(server_port)],
                              stderr=subprocess.DEVNULL)
    time.sleep(2.5)
    path = os.path.join(HERE, target)
    line = next(i for i, text in enumerate(open(path), 1) if "# BREAKPOINT" in text)
    program = subprocess.Popen([sys.executable, "-Xfrozen_modules=off", "-m", "debugpy", "--listen",
                                f"127.0.0.1:{debug_port}", "--wait-for-client", path],
                               env=env, cwd=ROOT, stdout=subprocess.DEVNULL)
    answers = {}
    try:
        dap = DebugAdapter(debug_port)
        dap.send("initialize", adapterID="python", linesStartAt1=True, columnsStartAt1=True)
        dap.send("attach", justMyCode=False)
        dap.wait(lambda m: m.get("event") == "initialized", 20)
        dap.send("setBreakpoints", source={"path": path}, breakpoints=[{"line": line}])
        dap.send("configurationDone")
        stopped = dap.wait(lambda m: m.get("event") == "stopped", 60)
        frames = dap.answer(dap.send("stackTrace", threadId=stopped["body"]["threadId"]), 10)
        frame_id = frames["body"]["stackFrames"][0]["id"]
        threads = [t["name"] for t in dap.answer(dap.send("threads"), 10)["body"]["threads"]]
        print(f"\n{target}: stopped at line {line}, threads {threads}")
        for expression in expressions:
            start = time.perf_counter()
            seq = dap.send("evaluate", expression=expression, frameId=frame_id, context="repl")
            try:
                reply = dap.answer(seq, timeout)
                text = reply["body"]["result"] if reply.get("success") else reply.get("message", "")
                answers[expression] = (reply.get("success"), text, time.perf_counter() - start)
                print(f"  {expression}\n    -> {time.perf_counter() - start:.2f} s: {text.splitlines()[-1][:100] if text else ''}")
            except TimeoutError:
                answers[expression] = (None, "no answer", timeout)
                print(f"  {expression}\n    -> no answer after {timeout} s")
    finally:
        program.kill()
        server.kill()
    return threads, answers


def check(name, ok):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}")


def main():
    get_me = 'gh.call_tool("get_me", {})'
    threads, answers = pause_and_ask("target_bridge.py", [f"mcp_bridge.text_of({get_me})"])
    ok, text, seconds = answers[f"mcp_bridge.text_of({get_me})"]
    check("bridge: the Debug Console gets an answer while paused", bool(ok) and "tester" in text and seconds < 2)
    check("bridge: the thread list shows mcp-loop", "mcp-loop" in threads)

    _, answers = pause_and_ask("target_async.py", [f"import asyncio; asyncio.run({get_me})", f"await {get_me}"])
    check("all-async: asyncio.run() raises RuntimeError", "RuntimeError" in answers[f"import asyncio; asyncio.run({get_me})"][1])
    check("all-async: await never answers", answers[f"await {get_me}"][0] is None)

    print(f"\n{sum(results)} of {len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

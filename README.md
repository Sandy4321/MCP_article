# MCP verification is the new gold in the AI coding era

This code goes with the tutorial *MCP Verification Is the New Gold in the AI Coding Era*. It shows proper MCP use in Python. The full tutorial text is in [`Proper_MCP_Use_for_Python_Code.docx`](Proper_MCP_Use_for_Python_Code.docx).

The official MCP Python SDK is async-only. When you use it in the usual way, `async` spreads to every function. Also, a stopped VS Code Debug Console cannot send requests to the MCP server.

You cannot fix a bug that you do not know about. To find these bugs, you must stop the program, examine each value and test the result by hand. This is step-by-step verification. This repository shows a different design that makes this possible: **threads outside, asyncio in a box**. One background thread (the messenger) owns the event loop and the MCP session. All other code is plain Python with threads. You can set a breakpoint on any line, and you can call a tool from the Debug Console while the program is stopped.

## Files

| File | What it contains |
| --- | --- |
| `Proper_MCP_Use_for_Python_Code.docx` | The tutorial: why async-only MCP code is difficult to debug, the bridge design, measurements and a checklist |
| `mcp_bridge.py` | The bridge: the class `SyncMCP` and a `github()` helper for GitHub's MCP server |
| `agent_example.py` | A plain, threaded agent that uses the bridge |
| `async_style.py` | The same agent, written in the usual all-async style, for comparison |
| `tests/run_examples.py` | Runs the three examples against a local fake server |
| `tests/debug_console_check.py` | The pause-and-ask test: stops each design under debugpy and calls a tool from the Debug Console |
| `tests/fake_github_server.py` | A local stand-in for GitHub's MCP server, with fake data |

## Requirements

- Python 3.10 or later (tested with 3.11 to 3.13)
- The 2.x MCP Python SDK: `mcp` 2.2 or later. It installs `httpx2` automatically. The code does not work with the 1.x SDK.
- `debugpy`, only for `tests/debug_console_check.py`

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run the agent against GitHub

The bridge uses GitHub's remote MCP server with read-only tools. You need a GitHub token.

```bat
set GITHUB_TOKEN=<your token>
python agent_example.py
python agent_example.py --serial
```

With `--serial`, the jobs run one after the other. Then you can follow one job from start to end in the debugger.

## Run the checks (no token necessary)

```bat
python tests/run_examples.py
python tests/debug_console_check.py
```

`run_examples.py` runs all three examples and examines the bridge: errors, cancellation, threads and clean shutdown. `debug_console_check.py` does the pause-and-ask test for both designs. With the bridge, the Debug Console gets an answer while the program is stopped. With the all-async design, `await` never gets an answer.

## Try the pause-and-ask test in VS Code

1. Open `agent_example.py`.
2. Set a breakpoint on the line `if result.is_error:`.
3. Press F5. VS Code stops in a worker thread.
4. In the Debug Console, type `gh.call_tool("get_me", {})`. You get an answer.
5. Look at the thread list. It shows `MainThread`, `mcp-loop` and the worker threads.

## License

Copyright (c) 2026 Sander Stepanov. All rights reserved. No license is granted: you may not use, copy, modify or share this material without written permission. Read [`LICENSE`](LICENSE).

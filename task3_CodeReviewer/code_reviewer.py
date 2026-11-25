"""Read-only Code Reviewer agent built with the Claude Agent SDK.

Step 1: data set (existing task_project/shop.py + test_shop.py)
Step 2: implement the agent (scout)
Step 3: run it with two prompts and print the results
"""
import asyncio
import os
import sys
import threading

from dotenv import load_dotenv, find_dotenv
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    ToolUseBlock,
)

# ---------------------------------------------------------------- setup
sys.stdout.reconfigure(encoding="utf-8")  # agent text may contain non-cp1252 characters
load_dotenv(find_dotenv())  # finds .env in a parent folder; key is never in code

if not os.environ.get("ANTHROPIC_API_KEY"):
    sys.exit("ANTHROPIC_API_KEY not found. Put it in a .env file.")

MODEL_NAME = "claude-haiku-5-5"  # or "claude-sonnet-5-5" / "claude-opus-5-5"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(BASE_DIR, "task_project")


def run_sync(coro_fn):
    """Run an `async def` function to completion and return its result.

    On Windows the SDK needs a Proactor loop (it spawns the Claude Code CLI
    as a subprocess), so we run on a separate thread with its own loop.
    """
    outcome = {}

    def runner():
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        try:
            outcome["value"] = asyncio.run(coro_fn())
        except Exception as exc:
            outcome["error"] = exc

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()

    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


# step 1: the data set
# Files created at task_project/ (shop.py, test_shop.py)


# step 2: the agent
def scout(prompt):
    """Run a read-only reviewer (Glob, Grep, Read; no Bash).

    Prints each tool name as it is used, then the final report,
    the number of turns and the total cost.
    """

    async def main():
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                tools=["Glob", "Grep", "Read"],
                allowed_tools=["Glob", "Grep", "Read"],
                disallowed_tools=["Bash"],
                cwd=PROJECT_DIR,
                setting_sources=[],  # ignore user/global settings and MCP servers
                mcp_servers={},
                model=MODEL_NAME,
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"  [tool] {block.name}")
            elif isinstance(message, ResultMessage):
                print("\n=== FINAL REPORT ===")
                print(message.result)
                print(f"\nTurns: {message.num_turns}")
                print(f"Total cost: ${message.total_cost_usd or 0:.4f}")

    run_sync(main)


# step 3: run + print
PROMPT_A = (
    "Review the Python project in the current folder. List every function "
    "(grouped by file) and say which ones have no docstring."
)
PROMPT_B = (
    "Report any bugs or security problems in this project. For each one give "
    "the file, the function, and a one-line fix."
)

if __name__ == "__main__":
    scout(PROMPT_A)
    scout(PROMPT_B)

""" IT Support chatbot core: 
        + RAG (VoyageAI) 
        + client tool 
        + server web search 
        + MCP tools.
"""

import asyncio
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import voyageai
from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import Client

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR.parent / ".env")

anthropic_client = Anthropic()
voyage_client = voyageai.Client()
model = "claude-haiku-5-5"
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:3000/mcp")

SYSTEM_PROMPT = """You are an IT support assistant.
- Answer IT questions using the knowledge base context provided in <context> tags when it is relevant.
- If the context does not cover the question, use the web_search tool.
- Use get_current_datetime when the user needs the current date or time.
- Use create_support_ticket when the user wants to open a ticket (ask for any missing title, description or requester), and check_ticket_status when they ask about an existing ticket.
Be concise and practical."""


# --- RAG: VoyageAI embeddings + in-memory index -----------------------------
def generate_embedding(chunks, model="voyage-4-lite", input_type="document"):
    is_list = isinstance(chunks, list)
    for attempt in range(4):  # Voyage free tier: 3 requests/min -> wait and retry
        try:
            result = voyage_client.embed(chunks if is_list else [chunks], model=model, input_type=input_type)
            break
        except voyageai.error.RateLimitError:
            if attempt == 3:
                raise
            time.sleep(21)
    return result.embeddings if is_list else result.embeddings[0]


_index = None  # list of (chunk, embedding)


def retrieve_context(query: str, k: int = 3) -> str:
    global _index
    if _index is None:
        text = (BASE_DIR / "it_sector.txt").read_text(encoding="utf-8")
        chunks = [c.strip() for c in re.split(r"\n## ", "\n" + text) if c.strip()]  # by section
        _index = list(zip(chunks, generate_embedding(chunks)))

    query_vec = generate_embedding(query, input_type="query")
    # Voyage embeddings are normalized, so dot product == cosine similarity.
    ranked = sorted(_index, key=lambda item: -sum(a * b for a, b in zip(query_vec, item[1])))
    return "\n\n---\n\n".join(chunk for chunk, _ in ranked[:k])


# --- Tools --------------------------------------------------------------------
def get_current_datetime(date_format="%Y-%m-%d %H:%M:%S"):
    if not date_format:
        raise ValueError("date_format cannot be empty")
    return datetime.now().strftime(date_format)


# Client tool (we run it)
datetime_schema = {
    "name": "get_current_datetime",
    "description": "Returns the current date and time formatted according to the specified format string.",
    "input_schema": {
        "type": "object",
        "properties": {
            "date_format": {
                "type": "string",
                "description": "A Python strftime format string, e.g. '%H:%M:%S' for just the time.",
            }
        },
        "required": [],
    },
}

# Server tool (Anthropic runs it)
web_search_schema = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}


# MCP tools (create_support_ticket, check_ticket_status): one short connection per call
def _mcp(action):
    async def run():
        async with Client(MCP_SERVER_URL) as mcp_client:
            return await action(mcp_client)

    return asyncio.run(run())


mcp_tools: list = []


def load_mcp_tools() -> list:
    """Fetch tool schemas from the MCP server; empty list if it is unreachable."""
    global mcp_tools
    try:
        result = _mcp(lambda c: c.list_tools())
        mcp_tools = [
            {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
            for t in result.tools
        ]
    except Exception as e:
        print(f"Warning: MCP server unavailable at {MCP_SERVER_URL}: {e}")
        mcp_tools = []
    return mcp_tools


def run_tool(name, tool_input):
    if name == "get_current_datetime":
        return get_current_datetime(**tool_input)
    if name in {t["name"] for t in mcp_tools}:
        result = _mcp(lambda c: c.call_tool(name, tool_input))
        text = "\n".join(b.text for b in result.content if getattr(b, "text", None))
        if result.is_error:
            raise RuntimeError(text or "MCP tool error")
        return text
    raise ValueError(f"Unknown tool: {name}")


# --- Chat ---------------------------------------------------------------------
def chat(messages: list, user_input: str) -> str:
    """Send one user turn (with RAG context); `messages` is the history, updated in place."""
    if not mcp_tools:
        load_mcp_tools()

    context = retrieve_context(user_input)
    messages.append(
        {
            "role": "user",
            "content": f"Use the following knowledge base context if it is relevant.\n\n"
            f"<context>\n{context}\n</context>\n\nQuestion: {user_input}",
        }
    )
    tools = [datetime_schema, web_search_schema, *mcp_tools]

    while True:
        response = anthropic_client.messages.create(
            model=model, max_tokens=1000, system=SYSTEM_PROMPT, messages=messages, tools=tools
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "pause_turn":  # server-side web search still running
            continue
        if response.stop_reason != "tool_use":
            return "\n".join(b.text for b in response.content if b.type == "text")

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                content, is_error = json.dumps(run_tool(block.name, block.input)), False
            except Exception as e:
                content, is_error = f"Error: {e}", True
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error}
            )
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    history: list = []
    print("IT Support bot (type 'exit' to quit)")
    while (user_text := input("$: ").strip()).lower() not in ("exit", "quit"):
        print(chat(history, user_text) + "\n")


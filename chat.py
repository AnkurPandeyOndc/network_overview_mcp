"""Thin Ollama ↔ MCP orchestrator for ONDC Analytics.

Usage:
    poetry run python chat.py                    # qwen2.5:7b (default)
    poetry run python chat.py --model qwen2.5:3b
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
CONFIG_FILE = Path(__file__).parent / "anythingllm_mcp_config.json"

SYSTEM_PROMPT = """\
You are an analyst assistant for ONDC (Open Network for Digital Commerce) data.
You have access to tools that let you:
  - get_schema: discover exact table names, columns, and valid domain/category values
  - run_safe_sql: execute read-only SQL queries against the analytics database
  - get_data_freshness: check the latest available data date
  - search_docs: search indexed ONDC business documents
  - save_message / get_history: persist and retrieve conversation history

Rules:
  1. ALWAYS call get_schema before writing any SQL.
  2. Only use tables and columns that appear in the schema output.
  3. Every SQL WHERE clause must include an order_date filter.
  4. Be concise — summarise results in plain language after showing the data.
"""


def load_server_params() -> StdioServerParameters:
    config = json.loads(CONFIG_FILE.read_text())
    srv = config["mcpServers"]["ondc-analytics"]
    # Merge current env so PATH etc. are preserved
    env = {**os.environ, **srv.get("env", {})}
    return StdioServerParameters(
        command=srv["command"],
        args=srv.get("args", []),
        env=env,
        cwd=srv.get("cwd"),
    )


def tool_to_openai(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


async def ollama_chat(client: httpx.AsyncClient, model: str, messages: list, tools: list) -> dict:
    resp = await client.post(
        OLLAMA_URL,
        json={"model": model, "messages": messages, "tools": tools, "stream": False},
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]


async def agent_loop(
    session: ClientSession,
    client: httpx.AsyncClient,
    model: str,
    tools_openai: list,
    messages: list,
) -> str:
    """Run the inner agent loop until Ollama produces a final text answer."""
    while True:
        msg = await ollama_chat(client, model, messages, tools_openai)

        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            # Final answer — return the text content
            return msg.get("content") or ""

        # Append assistant turn with tool_calls
        messages.append(msg)

        # Execute each tool call and append results
        for tc in tool_calls:
            fn = tc["function"]
            name = fn["name"]
            try:
                raw_args = fn.get("arguments", "{}")
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}

            print(f"  [tool] {name}({json.dumps(args, ensure_ascii=False)})", flush=True)

            try:
                result = await session.call_tool(name, args)
                # result.content is a list of TextContent / other content blocks
                if result.content:
                    content_str = "\n".join(
                        block.text if hasattr(block, "text") else str(block)
                        for block in result.content
                    )
                else:
                    content_str = json.dumps({"status": "ok", "result": None})
            except Exception as exc:
                content_str = json.dumps({"error": str(exc)})

            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", name),
                "content": content_str,
            })


async def chat_repl(model: str) -> None:
    params = load_server_params()

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Fetch and convert tools once
            tools_result = await session.list_tools()
            tools_openai = [tool_to_openai(t) for t in tools_result.tools]
            print(f"Connected — {len(tools_openai)} tools available. Model: {model}")
            print('Type "exit" or Ctrl-D to quit.\n')

            messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

            async with httpx.AsyncClient() as http_client:
                while True:
                    try:
                        user_input = input("You: ").strip()
                    except (EOFError, KeyboardInterrupt):
                        print("\nBye.")
                        break

                    if not user_input:
                        continue
                    if user_input.lower() in {"exit", "quit"}:
                        print("Bye.")
                        break

                    messages.append({"role": "user", "content": user_input})

                    try:
                        answer = await agent_loop(session, http_client, model, tools_openai, messages)
                    except httpx.HTTPError as exc:
                        print(f"[Ollama error] {exc}")
                        messages.pop()  # remove the user turn so state stays consistent
                        continue

                    print(f"\nAssistant: {answer}\n")
                    messages.append({"role": "assistant", "content": answer})


def main() -> None:
    parser = argparse.ArgumentParser(description="ONDC Analytics Chat (Ollama + MCP)")
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model tag")
    args = parser.parse_args()

    try:
        asyncio.run(chat_repl(args.model))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()

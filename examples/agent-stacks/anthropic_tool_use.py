#!/usr/bin/env python3
"""Anthropic Messages API tool use, with tools discovered from gag-mcp over local stdio.

Status: untested. Requires `pip install anthropic`, model API access (ANTHROPIC_API_KEY),
and a model id in ANTHROPIC_MODEL.
"""
import asyncio
import json
import os
import sys

import anthropic
from mcp import Client, StdioServerParameters

SERVER = StdioServerParameters(command=sys.executable, args=["-m", "gag_mcp.server"], env=dict(os.environ))


async def main() -> None:
    api = anthropic.Anthropic()
    async with Client(SERVER) as gag:
        tools = [{"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
                 for t in (await gag.list_tools()).tools]
        messages = [{"role": "user", "content": "Verify the signed-revoked example passport and explain the result."}]
        while True:
            reply = api.messages.create(model=os.environ["ANTHROPIC_MODEL"], max_tokens=1500,
                                        tools=tools, messages=messages)
            messages.append({"role": "assistant", "content": reply.content})
            if reply.stop_reason != "tool_use":
                print("".join(b.text for b in reply.content if b.type == "text"))
                return
            results = []
            for block in reply.content:
                if block.type == "tool_use":
                    r = await gag.call_tool(block.name, block.input)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "is_error": bool(r.is_error),
                                    "content": json.dumps(r.structured_content) if r.structured_content
                                    else r.content[0].text})
            messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    asyncio.run(main())

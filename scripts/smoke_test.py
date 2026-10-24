#!/usr/bin/env python3
"""Smoke test: a real MCP client calls every gaig-mcp tool over stdio and Streamable HTTP.

Usage: python scripts/smoke_test.py [--transcript docs/verification-transcript.md]
Exit code 0 only if every call succeeds and every result carries authority_effect NONE.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

import httpx
from mcp import Client, StdioServerParameters

EVAL = "2026-10-16T00:00:00Z"
CALLS = [
    ("check_inventory", {"use_sample": True, "evaluation_time": EVAL}),
    ("build_decision_pack", {"use_sample": True, "evaluation_time": EVAL}),
    ("validate_passport", {"example": "signed-unrevoked"}),
    ("validate_passport", {"example": "signed-revoked"}),
]
lines: list[str] = []
failures: list[str] = []


def log(s: str = "") -> None:
    print(s)
    lines.append(s)


def summarize(name: str, sc: dict) -> dict:
    r = sc["result"]
    if name == "check_inventory":
        keep = {k: r[k] for k in ("validation_state", "governance_gate_state", "finding_count", "findings_by_severity")}
        keep["first_finding"] = r["findings"][0] if r["findings"] else None
    elif name == "build_decision_pack":
        keep = {"decision_status": r["decision_status"], "integrity_check": r["integrity_check"],
                "generated_files": [f["path"] for f in r["manifest"]["generated_files"]],
                "handoff_authority_effect": r["handoff"]["authority_effect"]}
    else:
        v = r["verification"]
        keep = {k: v.get(k) for k in ("verification_primary_status", "reference_policy_disposition",
                                       "assessment_result_recorded_in_artifact", "fully_validated")}
    return {"authority_effect": sc["authority_effect"], "human_decision_state": sc["human_decision_state"],
            "source": sc["source"], "result_excerpt": keep}


async def exercise(label: str, target) -> None:
    log(f"\n## Transport: {label}\n")
    async with Client(target) as c:
        tools = (await c.list_tools()).tools
        log("`tools/list` →")
        log("```json")
        log(json.dumps([{"name": t.name, "annotations": t.annotations.model_dump(by_alias=True, exclude_none=True)}
                        for t in tools], indent=2))
        log("```")
        for name, args in CALLS:
            r = await c.call_tool(name, args)
            ok = (not r.is_error) and r.structured_content and r.structured_content.get("authority_effect") == "NONE"
            if not ok:
                failures.append(f"{label}:{name}")
            log(f"\n`tools/call {name} {json.dumps(args)}` → {'OK' if ok else 'FAIL'}")
            log("```json")
            log(json.dumps(summarize(name, r.structured_content) if ok else [c.model_dump() for c in r.content], indent=2))
            log("```")
        bad = await c.call_tool("check_inventory", {"inventory_csv": "system_id,system_name\nX,Y\n"})
        log(f"\n`tools/call check_inventory` with a malformed CSV → isError={bad.is_error} (expected True: fail closed)")
        log(f"> {bad.content[0].text[:300]}")
        if not bad.is_error:
            failures.append(f"{label}:fail-closed")


def free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def legacy_handshake(base: str) -> None:
    log("\n## Raw HTTP: handshake-era client (protocol 2025-11-25), as older hosted clients may send\n")
    h = {"content-type": "application/json", "accept": "application/json, text/event-stream"}
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "0"}}}
    r = httpx.post(base + "/mcp", json=init, headers=h).json()
    log(f"- initialize → protocolVersion `{r['result']['protocolVersion']}`, server `{r['result']['serverInfo']['name']}`")
    h["mcp-protocol-version"] = "2025-11-25"
    call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "validate_passport", "arguments": {"example": "signed-revoked"}}}
    r = httpx.post(base + "/mcp", json=call, headers=h).json()
    sc = r["result"].get("structuredContent", {})
    log(f"- tools/call validate_passport → authority_effect `{sc.get('authority_effect')}`, "
        f"status `{sc.get('result', {}).get('verification', {}).get('verification_primary_status')}`")
    if sc.get("authority_effect") != "NONE":
        failures.append("legacy-http")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript")
    a = ap.parse_args()
    log("# gaig-mcp verification transcript")
    log(f"\nGenerated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} on a local machine. "
        "Real MCP client (official Python SDK `mcp` 2.3.0) calling the local server. Results are excerpted.")
    await exercise("stdio (subprocess)", StdioServerParameters(command=sys.executable, args=["-m", "gaig_mcp.server"],
                                                               env=dict(os.environ)))
    port = free_port()
    proc = subprocess.Popen([sys.executable, "-m", "gaig_mcp.server", "--http", "--port", str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(base + "/health").status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        log(f"\n`GET /health` → `{httpx.get(base + '/health').json()}`")
        await exercise(f"Streamable HTTP ({base}/mcp)", base + "/mcp")
        legacy_handshake(base)
    finally:
        proc.terminate()
    log(f"\n**Result:** {'PASS' if not failures else 'FAIL ' + ', '.join(failures)}")
    if a.transcript:
        with open(a.transcript, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

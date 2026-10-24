#!/usr/bin/env python3
"""Fail-closed reachable-history attribution and privacy check.

An optional private JSON denylist may contain `prohibited_literals` and
`prohibited_sha256_lowercase`. The denylist is read at runtime and is never
embedded in public output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

APPROVED = {
    ("Global AI Governance", "288799817+GLOBAL-AI-GOVERNANCE" + "@" + "users.noreply.github.com"),
    ("GitHub", "noreply" + "@" + "github.com"),
    ("GitHub Actions", "actions" + "@" + "github.com"),
    ("github-actions[bot]", "41898282+github-actions[bot]" + "@" + "users.noreply.github.com"),
    ("dependabot[bot]", "49699333+dependabot[bot]" + "@" + "users.noreply.github.com"),
    ("web-flow", "noreply" + "@" + "github.com"),
}
TRAILER = re.compile(r"(?im)^(co-authored-by|signed-off-by|reviewed-by|acked-by):\s*(.+)$")
LOCAL_PATH = re.compile(r"(?i)(?:[a-z]:[\\/]users[\\/][^\\/\s]+|/" r"users/[^/\s]+|/" r"home/[^/\s]+)")
EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)


def git(*args: str, binary: bool = False):
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={Path.cwd().resolve()}", *args],
        text=not binary,
        stderr=subprocess.DEVNULL,
    )


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def private_hit(value: str, policy: dict) -> bool:
    lowered, packed = value.lower(), compact(value)
    if any(x.lower() in lowered or compact(x) in packed for x in policy.get("prohibited_literals", [])):
        return True
    hashes = set(policy.get("prohibited_sha256_lowercase", []))
    values = [value, *EMAIL.findall(value)]
    return any(hashlib.sha256(x.strip().lower().encode()).hexdigest() in hashes for x in values)


def blob_stream(object_ids: list[str]):
    output = subprocess.run(
        ["git", "-c", f"safe.directory={Path.cwd().resolve()}", "cat-file", "--batch"], input=("\n".join(object_ids) + "\n").encode(),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
    ).stdout
    pos = 0
    for _ in object_ids:
        end = output.find(b"\n", pos)
        if end < 0:
            return
        header = output[pos:end].decode(errors="replace").split()
        pos = end + 1
        if len(header) != 3:
            continue
        oid, kind, size = header
        data = output[pos:pos + int(size)]
        pos += int(size) + 1
        if kind == "blob":
            yield oid, data


def main() -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--private-denylist", type=Path)
    args = parser.parse_args()
    policy = json.loads(args.private_denylist.read_text(encoding="utf-8")) if args.private_denylist else {}
    findings: set[tuple[str, str]] = set()
    fmt = "%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B%x00%x1e"
    for record in git("log", "--all", f"--format={fmt}").split("\x1e"):
        fields = record.strip("\x00\r\n").split("\x00", 5)
        if len(fields) != 6:
            continue
        oid, an, ae, cn, ce, message = fields
        if (an, ae) not in APPROVED:
            findings.add(("UNAPPROVED_AUTHOR", oid))
        if (cn, ce) not in APPROVED:
            findings.add(("UNAPPROVED_COMMITTER", oid))
        if private_hit(an + ae + cn + ce + message, policy):
            findings.add(("PRIVATE_DENYLIST", oid))
        if LOCAL_PATH.search(message):
            findings.add(("PERSONAL_PATH", oid))
        for trailer in TRAILER.finditer(message):
            if not any(name in trailer.group(2) and email in trailer.group(2) for name, email in APPROVED):
                findings.add(("UNAPPROVED_TRAILER", oid))
    objects = []
    for line in git("rev-list", "--objects", "--all").splitlines():
        oid, _, path = line.partition(" ")
        objects.append(oid)
        if LOCAL_PATH.search(path) or private_hit(path, policy):
            findings.add(("PROHIBITED_PATH", oid))
    for oid, data in blob_stream(list(dict.fromkeys(objects))):
        if b"\x00" in data:
            continue
        text = data.decode("utf-8", errors="ignore")
        if LOCAL_PATH.search(text):
            findings.add(("PERSONAL_PATH", oid))
        if private_hit(text, policy):
            findings.add(("PRIVATE_DENYLIST", oid))
    for line in git("for-each-ref", "refs/tags", "--format=%(objectname)%00%(objecttype)").splitlines():
        oid, _, kind = line.partition("\x00")
        if kind == "tag":
            data = git("cat-file", "tag", oid)
            if private_hit(data, policy) or LOCAL_PATH.search(data):
                findings.add(("PROHIBITED_TAG", oid))
    if findings:
        print("SAFE_STOP")
        for reason in sorted({reason for reason, _ in findings}):
            print(reason)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

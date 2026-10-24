#!/usr/bin/env python3
"""Copy the pinned upstream files that gag-mcp runs into src/gag_mcp/_upstream.

Run ./scripts/fetch_upstreams.sh first. Only git-tracked files from the exact
source-lock commits in scripts/fetch_upstreams.sh are copied.

Usage: python scripts/bundle_upstreams.py [--check]
  --check  exit 1 if the bundled tree differs from the pinned checkouts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
BUNDLE = ROOT / "src" / "gag_mcp" / "_upstream"
LOCK_FILE = "UPSTREAM_LOCK.json"

UPSTREAMS = {
    "toolkit": {
        "repository": "GLOBAL-AI-GOVERNANCE/global-ai-governance-toolkit",
        "checkout": "global-ai-governance-toolkit",
        "lock_var": "DEFAULT_TOOLKIT_REF",
        "include": ("automation/", "LICENSE"),
        "exclude": ("automation/tests/", "automation/reports/"),
    },
    "agentic": {
        "repository": "GLOBAL-AI-GOVERNANCE/agentic-ai-governance",
        "checkout": "agentic-ai-governance",
        "lock_var": "DEFAULT_AGENTIC_REF",
        "include": ("tools/", "schemas/", "profiles/", "examples/", "governance/", "LICENSE", "NOTICE",
                    "LICENSE_POLICY.md", "LICENSES/"),
        "exclude": (),
    },
}


def locked_refs() -> dict[str, str]:
    script = (ROOT / "scripts" / "fetch_upstreams.sh").read_text(encoding="utf-8")
    refs = {}
    for name, spec in UPSTREAMS.items():
        match = re.search(rf'^{spec["lock_var"]}="([0-9a-f]{{40}})"$', script, re.M)
        if not match:
            sys.exit(f"{spec['lock_var']} not found in scripts/fetch_upstreams.sh")
        refs[name] = match.group(1)
    return refs


def selected(name: str, rel: str) -> bool:
    spec = UPSTREAMS[name]
    if any(rel.startswith(prefix) for prefix in spec["exclude"]):
        return False
    if name == "agentic":
        if rel.startswith("tools/") and Path(rel).name.startswith("test_"):
            return False
        if rel.startswith("governance/") and not rel.endswith(".schema.json"):
            return False
    return any(rel == inc or (inc.endswith("/") and rel.startswith(inc)) for inc in spec["include"])


def tracked(checkout: Path, commit: str) -> list[str]:
    head = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    if head != commit:
        sys.exit(f"{checkout.name} is at {head}, expected {commit}. Run ./scripts/fetch_upstreams.sh")
    out = subprocess.run(["git", "-C", str(checkout), "ls-files", "-z"], check=True, capture_output=True).stdout
    return sorted(p for p in out.decode().split("\0") if p)


def digest(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode() + b"\0" + hashlib.sha256(files[rel]).hexdigest().encode() + b"\n")
    return "sha256:" + h.hexdigest()


def expected_tree() -> tuple[dict[str, bytes], dict]:
    refs = locked_refs()
    files: dict[str, bytes] = {}
    lock = {"generated_by": "scripts/bundle_upstreams.py", "upstreams": {}}
    for name, spec in UPSTREAMS.items():
        checkout = VENDOR / spec["checkout"]
        chosen = {}
        for rel in tracked(checkout, refs[name]):
            if selected(name, rel):
                chosen[f"{name}/{rel}"] = (checkout / rel).read_bytes()
        files.update(chosen)
        lock["upstreams"][name] = {"repository": spec["repository"], "commit": refs[name],
                                   "file_count": len(chosen), "tree_digest": digest(chosen)}
    files[LOCK_FILE] = (json.dumps(lock, indent=2, sort_keys=True) + "\n").encode()
    return files, lock


def current_tree() -> dict[str, bytes]:
    if not BUNDLE.is_dir():
        return {}
    return {p.relative_to(BUNDLE).as_posix(): p.read_bytes() for p in BUNDLE.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files, lock = expected_tree()
    if args.check:
        current = current_tree()
        if current != files:
            missing = sorted(set(files) - set(current))
            extra = sorted(set(current) - set(files))
            changed = sorted(k for k in set(files) & set(current) if files[k] != current[k])
            print(f"bundled upstreams are stale: {len(missing)} missing, {len(extra)} extra, {len(changed)} changed",
                  file=sys.stderr)
            for rel in (missing + extra + changed)[:20]:
                print(f"  {rel}", file=sys.stderr)
            return 1
        print("bundled upstreams match the source lock: "
              + ", ".join(f"{n} @ {v['commit']}" for n, v in lock["upstreams"].items()))
        return 0
    if BUNDLE.exists():
        shutil.rmtree(BUNDLE)
    for rel, data in files.items():
        target = BUNDLE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print(f"bundled {len(files) - 1} files into {BUNDLE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

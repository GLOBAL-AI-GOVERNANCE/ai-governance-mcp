#!/usr/bin/env python3
"""Check that every schema $id is published where it points.

Each absolute $id must have the form
https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/<repo>/<ref>/<path>
where <path> is the file's own repository path and <ref> is a release tag
listed in CHANGELOG.md (or an allowed branch), so the identifier resolves to
this exact document once that tag exists.

--online also fetches every $id and requires the same JSON document.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORG = "GLOBAL-AI-GOVERNANCE"
# (repository the $id names, directory in this checkout that mirrors it)
SOURCES = [("global-ai-governance-toolkit", "")]
ALLOWED_BRANCHES = ()
OTHER_PREFIXES = ()
RELEASE_HEADING = re.compile(r"^##\s+\[?v?(\d+\.\d+(?:\.\d+)?(?:-[0-9A-Za-z.]+)?)\]?(?:\s|$)", re.M)


def release_tags() -> set[str]:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8") if (ROOT / "CHANGELOG.md").exists() else ""
    return {"v" + version for version in RELEASE_HEADING.findall(text)}


def schema_ids() -> list[tuple[Path, str]]:
    listed = subprocess.run(["git", "ls-files", "*.json"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.split()
    found = []
    for name in listed:
        try:
            document = json.loads((ROOT / name).read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        identifier = document.get("$id") if isinstance(document, dict) else None
        if isinstance(identifier, str) and identifier.startswith(("http://", "https://")):
            found.append((ROOT / name, identifier))
    return found


def offline_errors(items: list[tuple[Path, str]]) -> list[str]:
    refs = release_tags() | set(ALLOWED_BRANCHES)
    errors = []
    for path, identifier in items:
        relative = path.relative_to(ROOT).as_posix()
        if any(identifier == prefix + relative[len(local):] for prefix, local in OTHER_PREFIXES if relative.startswith(local)):
            continue
        for repo, local in SOURCES:
            prefix = f"https://raw.githubusercontent.com/{ORG}/{repo}/"
            if relative.startswith(local) and identifier.startswith(prefix):
                ref, _, id_path = identifier[len(prefix):].partition("/")
                if id_path != relative[len(local):]:
                    errors.append(f"{relative}: $id path {id_path} is not the file path")
                elif ref not in refs:
                    errors.append(f"{relative}: $id ref {ref} is not a CHANGELOG release or allowed branch")
                break
        else:
            errors.append(f"{relative}: $id {identifier} is not a published raw URL for this repository")
    return errors


def online_errors(items: list[tuple[Path, str]]) -> list[str]:
    errors = []
    for path, identifier in items:
        local = json.loads(path.read_text(encoding="utf-8"))
        for attempt in range(6):
            try:
                with urllib.request.urlopen(identifier, timeout=20) as response:
                    if json.loads(response.read().decode("utf-8")) == local:
                        break
                    errors.append(f"{identifier}: published document differs from {path.relative_to(ROOT)}")
                    break
            except Exception as error:  # noqa: BLE001 - report any fetch failure after retries
                if attempt == 5:
                    errors.append(f"{identifier}: {error}")
                else:
                    time.sleep(10)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--online", action="store_true", help="fetch every $id and compare it with the local file")
    args = parser.parse_args()
    items = schema_ids()
    errors = offline_errors(items) + (online_errors(items) if args.online else [])
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print(f"schema $id check passed for {len(items)} schema(s){' (online)' if args.online else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

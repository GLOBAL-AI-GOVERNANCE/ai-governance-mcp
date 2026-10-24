#!/usr/bin/env python3
"""Fail-closed public identity check for commits introduced by a pull request."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

CANONICAL = ("Global AI Governance", "288799817+GLOBAL-AI-GOVERNANCE@" + "users.noreply.github.com")
APPROVED_SERVICES = {
    ("GitHub", "noreply@" + "github.com"),
    ("web-flow", "noreply@" + "github.com"),
    ("GitHub Actions", "actions@" + "github.com"),
    ("github-actions[bot]", "41898282+github-actions[bot]@" + "users.noreply.github.com"),
}
DEPENDABOT = ("dependabot[bot]", "49699333+dependabot[bot]@" + "users.noreply.github.com")
DEPENDABOT_SIGNOFF = ("dependabot[bot]", "support@" + "github.com")
TRAILER = re.compile(
    r"(?im)^(co-authored-by|signed-off-by|reviewed-by|acked-by|tested-by|reported-by|helped-by|suggested-by):\s*(.+)$"
)
IDENTITY = re.compile(r"^\s*(.*?)\s*<([^<>]+)>\s*$")


class GateFailure(RuntimeError):
    pass


def authorized_commit_identity(name: str, email: str) -> bool:
    return (name, email) == CANONICAL or (name, email) in APPROVED_SERVICES or (name, email) == DEPENDABOT


def authorized_trailer(trailer: str, name: str, email: str) -> bool:
    identity = (name, email)
    return identity == CANONICAL or identity in APPROVED_SERVICES or (
        trailer.lower() == "signed-off-by" and identity == DEPENDABOT_SIGNOFF
    )


def inspect_commit(record: dict[str, str]) -> list[str]:
    reasons = []
    if not authorized_commit_identity(record["author_name"], record["author_email"]):
        reasons.append("AUTHOR_NOT_AUTHORIZED")
    if not authorized_commit_identity(record["committer_name"], record["committer_email"]):
        reasons.append("COMMITTER_NOT_AUTHORIZED")
    for match in TRAILER.finditer(record["message"]):
        identity = IDENTITY.match(match.group(2))
        if identity is None or not authorized_trailer(match.group(1), identity.group(1), identity.group(2)):
            reasons.append("IDENTITY_TRAILER_NOT_AUTHORIZED")
            break
    return sorted(set(reasons))


def run_git(arguments: list[str]) -> str:
    result = subprocess.run(["git", *arguments], text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode:
        raise GateFailure("REQUIRED_PR_COMMIT_FETCH_FAILED")
    return result.stdout


def api_pr(repository: str, number: int) -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GateFailure("GITHUB_TOKEN_UNAVAILABLE")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/pulls/{number}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except Exception as exc:
        raise GateFailure("PR_METADATA_UNAVAILABLE") from exc


def verify(event: dict, *, runner=run_git, api=api_pr) -> list[str]:
    pull = event.get("pull_request") or {}
    repository = (event.get("repository") or {}).get("full_name")
    number = event.get("number")
    base_sha = (pull.get("base") or {}).get("sha")
    head_sha = (pull.get("head") or {}).get("sha")
    if not all((repository, number, base_sha, head_sha)):
        raise GateFailure("PR_EVENT_METADATA_MALFORMED")
    before = api(repository, int(number))
    if (before.get("head") or {}).get("sha") != head_sha:
        raise GateFailure("PR_HEAD_CHANGED_DURING_INSPECTION")
    runner(["fetch", "--no-tags", "--force", "origin", base_sha, head_sha])
    commits = [sha for sha in runner(["rev-list", f"{base_sha}..{head_sha}"]).splitlines() if sha]
    if not commits:
        raise GateFailure("PR_COMMIT_SET_EMPTY")
    reasons = []
    fmt = "%an%x00%ae%x00%cn%x00%ce%x00%B"
    for sha in commits:
        fields = runner(["show", "-s", f"--format={fmt}", sha]).rstrip("\n").split("\x00", 4)
        if len(fields) != 5:
            raise GateFailure("COMMIT_METADATA_MALFORMED")
        reasons.extend(inspect_commit(dict(zip(("author_name", "author_email", "committer_name", "committer_email", "message"), fields))))
    after = api(repository, int(number))
    if (after.get("head") or {}).get("sha") != head_sha:
        raise GateFailure("PR_HEAD_CHANGED_DURING_INSPECTION")
    return sorted(set(reasons))


def main() -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--event", required=True, type=Path)
    args = parser.parse_args()
    try:
        reasons = verify(json.loads(args.event.read_text(encoding="utf-8")))
    except (OSError, ValueError, GateFailure) as exc:
        reasons = [str(exc)]
    if reasons:
        print("SAFE_STOP")
        for reason in reasons:
            print(reason)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

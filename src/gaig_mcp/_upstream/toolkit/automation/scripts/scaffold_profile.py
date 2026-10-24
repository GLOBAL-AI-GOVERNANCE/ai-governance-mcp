#!/usr/bin/env python3
"""Create a deterministic, non-registered optional-profile development skeleton."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FILES = {
    "claims-boundaries.md": """# Claims boundaries

Machine-only scaffold. This profile does not authorize deployment, accept risk, certify compliance, establish legal sufficiency, attest a provider, or transfer authority. `authority_effect: NONE`.
""",
    "evaluator.py": '''"""Evaluator stub; integrate only after registry and contract review."""\nfrom automation.profiles.common import finding\n\nPROFILE = "{profile_id}"\nVERSION = "0.0.0-dev"\n\ndef evaluate(data, root, evaluation_time):\n    issues = [] if data.get("subject_id") else [finding(PROFILE, "MISSING_SUBJECT_ID", "CRITICAL", "subject_id is required.", "Provide a bounded subject identifier.")]\n    return issues, [], {"subject_id": data.get("subject_id"), "authority_effect": "NONE"}\n''',
    "fixtures/fail.json": '{"authority_effect":"NONE"}\n',
    "fixtures/pass.json": '{"authority_effect":"NONE","subject_id":"SYNTHETIC-001"}\n',
    "input.schema.json": '{"$schema":"https://json-schema.org/draft/2020-12/schema","additionalProperties":false,"properties":{"authority_effect":{"const":"NONE"},"subject_id":{"minLength":1,"type":"string"}},"required":["authority_effect","subject_id"],"title":"{title} Input","type":"object"}\n',
    "integration.json": '{"authority_effect":"NONE","browser_rendering_hook":"web/profile-viewer.mjs#renderProfileResult","ci_test_hook":"automation/tests/test_profiles.py","common_result_schema":"automation/contracts/v1/profile-result.schema.json","profile_id":"{profile_id}","registration_state":"NOT_REGISTERED"}\n',
    "test_profile.py": '''"""Template tests; move into automation/tests only during reviewed integration."""\nimport unittest\n\nclass ScaffoldBoundaryTests(unittest.TestCase):\n    def test_non_authorizing(self):\n        self.assertEqual("NONE", "NONE")\n''',
}


def render(profile_id: str) -> dict[str, bytes]:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", profile_id):
        raise ValueError("profile id must be lowercase kebab-case")
    title = profile_id.replace("-", " ").title()
    rendered = {}
    for name, content in sorted(FILES.items()):
        value = content.replace("{profile_id}", profile_id).replace("{title}", title)
        rendered[name] = value.encode("utf-8")
    return rendered


def generate(profile_id: str, destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("destination must be absent or empty")
    for relative, content in render(profile_id).items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a non-registered Profile Development Kit skeleton.")
    parser.add_argument("profile_id")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        generate(args.profile_id, args.destination)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()

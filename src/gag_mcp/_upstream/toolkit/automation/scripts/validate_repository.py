#!/usr/bin/env python3
"""
Validate release-critical repository integrity.

Checks:
- required public files
- Python syntax
- JSON syntax
- local Markdown links
- immutable GitHub Actions pins
- Decision Pack manifest hashes
- generated-bytecode hygiene
- current documentation truth boundaries
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlsplit


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
MARKDOWN_LINK = re.compile(
    r"!?\[[^\]]*\]\((?P<destination>[^)\n]+)\)"
)
FENCED_CODE = re.compile(
    r"```.*?```|~~~.*?~~~",
    re.DOTALL,
)
ACTION_PIN = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@"
    r"[0-9a-fA-F]{40}$"
)
REQUIRED_FILES = (
    "README.md",
    "SECURITY.md",
    "LICENSE",
    "pyproject.toml",
    ".github/workflows/ai-governance-checks.yml",
    ".github/workflows/pages.yml",
    "automation/scripts/run_governance_checks.py",
    "automation/scripts/schema_validator.py",
    "automation/scripts/governance_validator.py",
    "automation/scripts/generate_decision_pack.py",
    "automation/scripts/build_decision_pack_example.py",
    "automation/schemas/ai-system-inventory.schema.json",
    "automation/policy-as-code/governance-rules.yaml",
    "automation/contracts/v1/canonical-inventory-record.schema.json",
    "automation/contracts/v1/normalized-inventory.schema.json",
    "automation/contracts/v1/governance-findings.schema.json",
    "automation/contracts/v1/governance-result.schema.json",
    "automation/contracts/v1/decision-pack-manifest.schema.json",
    "automation/scripts/inventory_normalizer.py",
    "automation/scripts/contract_verifier.py",
    "automation/scripts/machine_contracts.py",
    "gag_toolkit/cli.py",
    "web/index.html",
    "web/governance-engine.mjs",
    "web/finding-guidance.mjs",
    "web/contracts.generated.mjs",
    "web/machine-interface.json",
    "web/ai-system-inventory-template.csv",
    "web/sample-ai-inventory.csv",
    "examples/decision-pack/valid-system/manifest.json",
)
CURRENT_ENTRY_DOCS = (
    "README.md",
    "automation/README.md",
    "docs/automation-layer.md",
)
IGNORED_LINK_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "tel:",
    "data:",
    "www.",
)


class ValidationFailure(ValueError):
    """Raised when repository validation finds a blocking defect."""


def tracked_files() -> list[Path]:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={REPOSITORY_ROOT}",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    names = [
        name.decode("utf-8")
        for name in completed.stdout.split(b"\0")
        if name
    ]
    return [REPOSITORY_ROOT / name for name in names]


def normalize_lf(content: bytes) -> bytes:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content
    return (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .encode("utf-8")
    )


def sha256_lf(path: Path) -> str:
    return hashlib.sha256(
        normalize_lf(path.read_bytes())
    ).hexdigest()


def validate_required_files(errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        path = REPOSITORY_ROOT / relative
        if not path.is_file():
            errors.append(
                f"Missing required file: {relative}"
            )


def validate_python(files: Iterable[Path], errors: list[str]) -> None:
    for path in files:
        if path.suffix != ".py":
            continue
        try:
            compile(
                path.read_text(encoding="utf-8"),
                str(path),
                "exec",
            )
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append(
                f"Python syntax failure in "
                f"{path.relative_to(REPOSITORY_ROOT)}: {exc}"
            )


def validate_json(files: Iterable[Path], errors: list[str]) -> None:
    for path in files:
        if path.suffix != ".json":
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(
                f"JSON validation failure in "
                f"{path.relative_to(REPOSITORY_ROOT)}: {exc}"
            )

    policy = (
        REPOSITORY_ROOT
        / "automation"
        / "policy-as-code"
        / "governance-rules.yaml"
    )
    try:
        json.loads(policy.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(
            "Runtime policy must remain JSON-compatible YAML: "
            f"{exc}"
        )


def extract_destination(raw: str) -> str:
    value = raw.strip()

    if value.startswith("<") and ">" in value:
        return value[1:value.index(">")].strip()

    if not value:
        return ""

    return value.split()[0].strip()


def should_ignore_link(destination: str) -> bool:
    lower = destination.lower()
    if not destination or destination.startswith("#"):
        return True
    if lower.startswith(IGNORED_LINK_PREFIXES):
        return True
    if destination.startswith(("{", "$", "*")):
        return True
    if destination.upper() in {"URL", "LINK", "TBD"}:
        return True
    return False


def validate_markdown_links(
    files: Iterable[Path],
    errors: list[str],
) -> None:
    for markdown in files:
        if markdown.suffix.lower() != ".md":
            continue

        try:
            text = markdown.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(
                f"Cannot read Markdown file "
                f"{markdown.relative_to(REPOSITORY_ROOT)}: {exc}"
            )
            continue

        without_code = FENCED_CODE.sub("", text)

        for match in MARKDOWN_LINK.finditer(without_code):
            destination = extract_destination(
                match.group("destination")
            )

            if should_ignore_link(destination):
                continue

            parsed = urlsplit(destination)
            path_part = unquote(parsed.path)

            if not path_part:
                continue

            if path_part.startswith("/"):
                target = (
                    REPOSITORY_ROOT
                    / path_part.lstrip("/")
                )
            else:
                target = markdown.parent / path_part

            if not target.exists():
                errors.append(
                    "Broken local Markdown link in "
                    f"{markdown.relative_to(REPOSITORY_ROOT)}: "
                    f"{destination}"
                )


def validate_action_pins(errors: list[str]) -> None:
    workflows = (
        REPOSITORY_ROOT / ".github" / "workflows"
    )

    for path in sorted(workflows.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")

        if "\t" in text:
            errors.append(
                f"Workflow contains tab indentation: "
                f"{path.relative_to(REPOSITORY_ROOT)}"
            )

        for line_number, line in enumerate(
            text.splitlines(),
            start=1,
        ):
            stripped = line.strip()
            if not stripped.startswith("uses:"):
                continue

            reference = stripped.split(":", 1)[1].strip()
            reference = reference.split("#", 1)[0].strip()

            if reference.startswith(("./", "docker://")):
                continue

            if not ACTION_PIN.fullmatch(reference):
                errors.append(
                    "Unpinned external action in "
                    f"{path.relative_to(REPOSITORY_ROOT)}:"
                    f"{line_number}: {reference}"
                )


def validate_decision_pack_manifest(errors: list[str]) -> None:
    pack = (
        REPOSITORY_ROOT
        / "examples"
        / "decision-pack"
        / "valid-system"
    )
    manifest_path = pack / "manifest.json"

    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(
            f"Cannot validate Decision Pack manifest: {exc}"
        )
        return

    expected_status = "pending_human_decision"
    if manifest.get("decision_status") != expected_status:
        errors.append(
            "Decision Pack manifest does not preserve "
            "pending human decision status."
        )

    if manifest.get("hash_mode") != "sha256-text-lf":
        errors.append(
            "Decision Pack manifest has an unexpected hash mode."
        )

    for key, expected in (
        ("manifest_schema_version", "1.0.0"),
        ("generator_version", "1.0.0"),
        ("normalization_version", "1.0.0"),
    ):
        if manifest.get(key) != expected:
            errors.append(f"Decision Pack manifest has invalid {key}.")
    generated = manifest.get("generated_files")
    if not isinstance(generated, list) or not generated:
        errors.append(
            "Decision Pack manifest has no generated_files list."
        )
        return

    manifest_names: set[str] = set()

    for entry in generated:
        if not isinstance(entry, dict):
            errors.append(
                "Decision Pack manifest contains an invalid entry."
            )
            continue

        relative = entry.get("path")
        expected_hash = entry.get("sha256")

        if not isinstance(relative, str):
            errors.append(
                "Decision Pack manifest entry has no valid path."
            )
            continue

        manifest_names.add(relative)
        target = pack / relative

        if not target.is_file():
            errors.append(
                f"Decision Pack manifest references missing file: "
                f"{relative}"
            )
            continue

        actual_hash = sha256_lf(target)
        if actual_hash != expected_hash:
            errors.append(
                f"Decision Pack hash mismatch: {relative}"
            )

    actual_names = {
        path.name
        for path in pack.iterdir()
        if path.is_file() and path.name != "manifest.json"
    }

    if manifest_names != actual_names:
        errors.append(
            "Decision Pack manifest file list does not match "
            "the generated Markdown files."
        )


def validate_generated_templates(errors: list[str]) -> None:
    from automation.scripts.generate_inventory_templates import render

    for path, expected in render().items():
        try:
            actual = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        except OSError as exc:
            errors.append(f"Cannot read generated template: {exc}")
            continue
        if actual != expected:
            errors.append(f"Generated template drift: {path.relative_to(REPOSITORY_ROOT)}")

    from automation.scripts.generate_browser_contract_bundle import build

    browser_bundle = REPOSITORY_ROOT / "web" / "contracts.generated.mjs"
    if not browser_bundle.is_file() or browser_bundle.read_text(encoding="utf-8") != build():
        errors.append("Generated browser contract bundle drift: web/contracts.generated.mjs")


def validate_network_free_runtime(errors: list[str]) -> None:
    forbidden = ("import socket", "import requests", "urllib.request", "http.client")
    names = (
        "run_governance_checks.py", "inventory_normalizer.py", "machine_contracts.py",
        "schema_validator.py", "risk_tier_calculator.py", "governance_validator.py",
        "generate_governance_report.py", "generate_decision_pack.py",
    )
    for name in names:
        text = (REPOSITORY_ROOT / "automation" / "scripts" / name).read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                errors.append(f"Core runtime network import found in {name}: {token}")

    browser_tokens = (
        "fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon",
        "navigator.serviceWorker",
    )
    for path in sorted((REPOSITORY_ROOT / "web").glob("*.mjs")):
        text = path.read_text(encoding="utf-8")
        for token in browser_tokens:
            if token in text:
                errors.append(
                    f"Static browser network capability found in {path.name}: {token}"
                )


def validate_hygiene(files: Iterable[Path], errors: list[str]) -> None:
    for path in files:
        relative = path.relative_to(REPOSITORY_ROOT)
        if "__pycache__" in relative.parts:
            errors.append(
                f"Tracked Python cache directory: {relative}"
            )
        if path.suffix in {".pyc", ".pyo"}:
            errors.append(
                f"Tracked Python bytecode: {relative}"
            )

    for path in REPOSITORY_ROOT.rglob("__pycache__"):
        errors.append(
            "Generated Python cache directory present: "
            f"{path.relative_to(REPOSITORY_ROOT)}"
        )

    for pattern in ("*.pyc", "*.pyo"):
        for path in REPOSITORY_ROOT.rglob(pattern):
            errors.append(
                "Generated Python bytecode present: "
                f"{path.relative_to(REPOSITORY_ROOT)}"
            )


def validate_current_documentation(errors: list[str]) -> None:
    combined = ""

    for relative in CURRENT_ENTRY_DOCS:
        path = REPOSITORY_ROOT / relative
        combined += path.read_text(encoding="utf-8") + "\n"

    lowered = combined.lower()

    for stale in (
        "workflow scaffold",
        "workflow scaffolding",
        ".github: issue templates",
        "not yet consumed by the python runtime",
    ):
        if stale in lowered:
            errors.append(
                f"Current entry documentation contains stale claim: "
                f"{stale}"
            )

    required_phrases = (
        "pending human decision",
        "does not approve deployment",
        "fail-closed",
        "decision pack",
    )

    for phrase in required_phrases:
        if phrase not in lowered:
            errors.append(
                f"Current entry documentation is missing boundary: "
                f"{phrase}"
            )


def main() -> None:
    errors: list[str] = []
    files = tracked_files()

    validate_required_files(errors)
    validate_python(files, errors)
    validate_json(files, errors)
    validate_markdown_links(files, errors)
    validate_action_pins(errors)
    validate_decision_pack_manifest(errors)
    validate_generated_templates(errors)
    validate_network_free_runtime(errors)
    validate_hygiene(files, errors)
    validate_current_documentation(errors)

    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print(
        "Repository validation passed: "
        f"{len(files)} tracked files checked."
    )


if __name__ == "__main__":
    main()

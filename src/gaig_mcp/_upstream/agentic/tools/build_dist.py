#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Distribution:
    name: str
    target: str
    title: str
    version: str
    status: str
    source_label: str
    order: tuple[str, ...]


ALPHA1 = Distribution(
    name="alpha1",
    target="dist/AGENTIC_AI_GOVERNANCE_SPEC.md",
    title="Agentic AI Governance Framework",
    version="v0.1.0-alpha.1",
    status="Experimental public alpha. Specification and schemas are not frozen.",
    source_label="spec/",
    order=(
        "00-status-and-scope.md",
        "01-normative-conventions.md",
        "02-data-and-encoding.md",
        "03-assessment-model.md",
        "04-verification-model.md",
        "05-agent-trust-passport.md",
        "06-signature-profile.md",
        "07-revocation.md",
        "08-action-authority.md",
        "09-data-authority-interop.md",
        "10-conformance.md",
        "references.md",
    ),
)

DISTRIBUTIONS = {ALPHA1.name: ALPHA1}


def build_distribution(root: Path, distribution: Distribution) -> str:
    parts = [
        "<!-- SPDX-License-Identifier: CC-BY-4.0 -->\n",
        f"# {distribution.title}\n\n",
        "> **GENERATED FILE - DO NOT EDIT DIRECTLY**  \n",
        f"> Source: `{distribution.source_label}`  \n",
        f"> Version: `{distribution.version}`  \n",
        f"> Status: {distribution.status}\n\n",
    ]
    for name in distribution.order:
        text = (root / "spec" / name).read_text(encoding="utf-8")
        lines = text.splitlines()
        lines = [line for line in lines if not line.startswith("<!-- SPDX-License-Identifier:")]
        for idx, line in enumerate(lines):
            if line.startswith("# "):
                lines[idx] = "## " + line[2:]
                break
        parts.append("\n".join(lines).strip() + "\n\n")
    return "".join(parts)


def build(root: Path) -> str:
    """Backward-compatible Alpha.1 builder used by the existing test suite."""
    return build_distribution(root, ALPHA1)


def selected_distributions(name: str) -> list[Distribution]:
    if name == "all":
        return list(DISTRIBUTIONS.values())
    return [DISTRIBUTIONS[name]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--distribution", choices=["all", *DISTRIBUTIONS], default="all")
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    stale: list[str] = []
    written: list[Path] = []
    for distribution in selected_distributions(args.distribution):
        target = root / distribution.target
        expected = build_distribution(root, distribution)
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != expected:
                stale.append(distribution.name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(expected, encoding="utf-8", newline="\n")
            written.append(target)
    if args.check:
        if stale:
            print("generated distribution is stale:", ", ".join(stale))
            return 1
        print("generated distributions are current:", ", ".join(DISTRIBUTIONS))
        return 0
    for target in written:
        print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

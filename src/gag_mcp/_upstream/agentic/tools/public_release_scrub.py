#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

SCRUB_POLICY_VERSION = "1.1.0"
IGNORED_PARTS = {".git", ".pytest_cache", "__pycache__"}
CANONICAL_IDENTITY_STATEMENT = (
    "Public architecture, ownership, schemas, specifications, claims, decisions, "
    "requirements, and release materials use **GLOBAL AI GOVERNANCE** as the sole "
    "public project identity."
)
PUBLIC_LIMITATION = (
    "bounded exact-term scan; unknown aliases, paraphrases, steganography, and every "
    "possible credential form are not established as detected"
)


def _tracked_paths(root: Path) -> list[Path]:
    """Return Git-tracked paths, or a deterministic file-tree fallback for tests."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return sorted(
            (
                path.relative_to(root)
                for path in root.rglob("*")
                if path.is_file()
                and not any(part in IGNORED_PARTS for part in path.relative_to(root).parts)
            ),
            key=lambda item: item.as_posix(),
        )
    return sorted(
        (Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item),
        key=lambda item: item.as_posix(),
    )


def classify_tracked_files(root: Path) -> tuple[list[Path], list[Path]]:
    """Classify every tracked file by strict UTF-8 decodability.

    Public text selection is content-based rather than extension-based. The only
    excluded tracked files are those that do not decode as UTF-8 text.
    """
    root = root.resolve()
    text_files: list[Path] = []
    non_utf8_files: list[Path] = []
    for relative in _tracked_paths(root):
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        path = root / relative
        if not path.is_file():
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            non_utf8_files.append(path)
        else:
            text_files.append(path)
    return text_files, non_utf8_files


def iter_public_text_files(root: Path):
    text_files, _ = classify_tracked_files(root)
    yield from text_files


def load_private_denylist(path: Path) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        term = raw_line.strip()
        if not term or term.startswith("#"):
            continue
        folded = term.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        terms.append(term)
    if not terms:
        raise ValueError("private denylist contains no terms")
    return terms


def canonical_identity_errors(root: Path) -> list[str]:
    path = root / "requirements/deferred-requirements.md"
    if not path.is_file():
        return ["requirements/deferred-requirements.md is missing"]
    text = path.read_text(encoding="utf-8")
    if CANONICAL_IDENTITY_STATEMENT not in text:
        return ["canonical sole-public-project-identity statement is missing"]
    lines = [
        line
        for line in text.splitlines()
        if "sole public project identity" in line.casefold()
    ]
    if lines != [f"- {CANONICAL_IDENTITY_STATEMENT}"]:
        return ["canonical sole-public-project-identity statement is not unique"]
    return []


def private_denylist_errors(root: Path, denylist_path: Path) -> list[str]:
    root = root.resolve()
    denylist_path = denylist_path.resolve()
    try:
        denylist_path.relative_to(root)
    except ValueError:
        pass
    else:
        return ["private denylist must remain outside the public repository"]

    terms = load_private_denylist(denylist_path)
    folded_terms = [term.casefold() for term in terms]
    errors: list[str] = []
    for path in iter_public_text_files(root):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8").casefold()
        if any(folded in text for folded in folded_terms):
            errors.append(f"private denylist match found in {relative}")
    return errors


def validate_public_release_scrub(root: Path, denylist_path: Path | None = None) -> list[str]:
    errors = canonical_identity_errors(root)
    if denylist_path is not None:
        try:
            errors.extend(private_denylist_errors(root, denylist_path))
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the canonical public project identity and optionally scan "
            "every tracked UTF-8 text file using a private denylist stored outside "
            "the repository."
        )
    )
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--denylist", type=Path)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors = validate_public_release_scrub(root, args.denylist)
    text_files, non_utf8_files = classify_tracked_files(root)
    tracked_file_count = len(text_files) + len(non_utf8_files)
    if errors:
        print("PUBLIC RELEASE SCRUB FAILED")
        for error in errors:
            print("-", error)
        return 1

    print("PUBLIC RELEASE SCRUB PASSED")
    print("scrub_policy_version:", SCRUB_POLICY_VERSION)
    print("canonical_identity: PASS")
    print("tracked_files_evaluated:", tracked_file_count)
    print("tracked_utf8_text_files_scanned:", len(text_files))
    print("tracked_non_utf8_files_excluded:", len(non_utf8_files))
    print("private_evidence_retained:", "YES" if args.denylist is not None else "NO")
    print("limitations:", PUBLIC_LIMITATION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

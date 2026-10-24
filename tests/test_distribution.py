"""Distribution metadata, README links, and publish gating for the ``gaig-mcp`` package."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp"


def _project() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def test_distribution_metadata() -> None:
    project = _project()
    assert project["name"] == "gaig-mcp"
    assert project["scripts"] == {"gaig-mcp": "gaig_mcp.server:main"}
    assert project["license"] == "Apache-2.0"
    assert set(project["urls"]) == {"Homepage", "Repository", "Documentation"}
    assert not any(c.startswith("License ::") for c in project["classifiers"])


def test_readme_links_are_absolute_and_pinned_to_the_release_tag() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert re.findall(r"\]\((?!https?:|#|mailto:)([^)\s]+)\)", readme) == []
    refs = set(re.findall(re.escape(REPO_URL) + r"/(?:blob|tree)/([^/)#\s]+)", readme))
    assert refs == {f"v{_project()['version']}"}


def test_publish_jobs_stay_skipped_until_enabled() -> None:
    workflow = (ROOT / ".github/workflows/release-assets.yml").read_text(encoding="utf-8")
    assert "vars.PYPI_PUBLISH_ENABLED == 'true'" in workflow
    assert "vars.TESTPYPI_PUBLISH_ENABLED == 'true'" in workflow
    assert workflow.count("cp dist/*.whl dist/*.tar.gz upload/") == 2
    assert re.search(r"pypa/gh-action-pypi-publish@[0-9a-f]{40} ", workflow)

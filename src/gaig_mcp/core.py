"""Transport-independent logic for gaig-mcp.

Every public function returns a dict wrapped by ``envelope()`` so that each
response carries ``authority_effect: "NONE"`` and the review boundary text.
Nothing here approves, certifies, authorizes, or accepts risk.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from . import __version__

AUTHORITY_EFFECT = "NONE"
REVIEW_BOUNDARY = (
    "Automated checks support human review. They do not approve deployment, "
    "certify compliance, grant authorization, or accept risk. An accountable "
    "human retains approval, risk acceptance, rollback, and shutdown."
)
MAX_INPUT_BYTES = 1_000_000  # 1 MB cap on caller-supplied CSV/JSON
MAX_FINDINGS_RETURNED = 200
MAX_DOCUMENT_CHARS = 20_000

PASSPORT_EXAMPLES = {
    "signed-unrevoked": "examples/passports/signed-unrevoked.json",
    "signed-revoked": "examples/passports/signed-revoked.json",
}
EXAMPLE_KEY = "examples/trusted-keys/test-ed25519-key.json"
EXAMPLE_REVOCATION = "examples/revocation/valid-revocation-list.json"
EXAMPLE_BUNDLE = "examples/bundles/valid-bundle-manifest.json"
EXAMPLE_AT_TIME = "2026-07-18T12:00:00Z"

# Upstream field names that an agent could paraphrase as an authorization are
# relabeled; values are preserved verbatim.
_RELABEL = {
    "operating_disposition": "reference_policy_disposition",
    "issued_assessment_result": "assessment_result_recorded_in_artifact",
}


class GaigInputError(ValueError):
    """Caller input was rejected (fail closed)."""


GagInputError = GaigInputError  # Deprecated alias of GaigInputError.


class ConfigurationError(ValueError):
    """Server configuration is inconsistent; the server refuses to start or run."""


# --------------------------------------------------------------------------- environment
ENV_PREFIX = "GAIG_"
DEPRECATED_ENV_PREFIX = "GAG_"
ENV_SETTINGS = ("MCP_ALLOWED_HOSTS", "MCP_BEARER_TOKEN", "MCP_CORS_ORIGINS", "TOOLKIT_PATH", "AGENTIC_PATH")
_warned: set[str] = set()


def env_setting(suffix: str) -> str:
    """Return ``GAIG_<suffix>``, falling back to the deprecated ``GAG_<suffix>``.

    The deprecated name is honored (never silently ignored) with a one-time warning on stderr.
    Both names set to different values is a configuration error. Values are never echoed.
    """
    new_name, old_name = ENV_PREFIX + suffix, DEPRECATED_ENV_PREFIX + suffix
    new, old = os.environ.get(new_name), os.environ.get(old_name)
    if new is not None and old is not None and new != old:
        raise ConfigurationError(f"{new_name} and the deprecated {old_name} are both set to different values. "
                                 f"Unset {old_name} and keep {new_name}.")
    if new is not None:
        return new
    if old is not None:
        if old_name not in _warned:
            _warned.add(old_name)
            print(f"gaig-mcp: {old_name} is deprecated; set {new_name} instead.", file=sys.stderr)
        return old
    return ""


def check_environment() -> None:
    """Raise ConfigurationError if any GAIG_*/GAG_* pair conflicts."""
    for suffix in ENV_SETTINGS:
        env_setting(suffix)


# Toolkit validation errors keep these diagnostic fields only; supplied values never leave the server.
_SAFE_TOOLKIT_ERROR_FIELDS = ("code", "source_column", "expected", "remediation")


def _toolkit_rejection(exc: Exception) -> str:
    try:
        detail = json.loads(str(exc)).get("error")
    except (ValueError, AttributeError):
        detail = None
    if not isinstance(detail, dict):
        return ("Inventory rejected by toolkit validation (invalid_inventory). Check the CSV against the toolkit "
                "template columns and allowed values, and evaluation_time against YYYY-MM-DDTHH:MM:SSZ.")
    safe = {k: detail[k] for k in _SAFE_TOOLKIT_ERROR_FIELDS if k in detail}
    if safe.get("code") == "UNKNOWN_COLUMN":
        safe.pop("source_column", None)  # the unknown header is caller-supplied text
    return f"Inventory rejected by toolkit validation: {json.dumps({'error': safe}, sort_keys=True)}"


# --------------------------------------------------------------------------- paths
_BUNDLED = Path(__file__).resolve().parent / "_upstream"


def bundled_lock() -> dict[str, Any]:
    """Source lock for the upstream files bundled in this package."""
    try:
        return json.loads((_BUNDLED / "UPSTREAM_LOCK.json").read_text(encoding="utf-8"))["upstreams"]
    except (OSError, ValueError, KeyError):
        return {}


def toolkit_root() -> Path:
    override = env_setting("TOOLKIT_PATH")
    p = Path(override) if override else _BUNDLED / "toolkit"
    if not (p / "automation" / "scripts" / "run_governance_checks.py").is_file():
        raise RuntimeError(f"Toolkit not found at {p}. Reinstall gaig-mcp or set GAIG_TOOLKIT_PATH to a toolkit checkout.")
    return p


def agentic_root() -> Path:
    override = env_setting("AGENTIC_PATH")
    p = Path(override) if override else _BUNDLED / "agentic"
    if not (p / "tools" / "validate_artifact.py").is_file():
        raise RuntimeError(f"agentic-ai-governance not found at {p}. Reinstall gaig-mcp or set GAIG_AGENTIC_PATH to a checkout.")
    return p


def _git_commit(path: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:  # pragma: no cover - git missing in some hosts
        return None


def _source_commit(name: str, env_suffix: str, root: Path) -> str | None:
    if env_setting(env_suffix):
        return _git_commit(root)
    commit = bundled_lock().get(name, {}).get("commit")
    return commit[:7] if commit else None


def _import_toolkit():
    root = str(toolkit_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from automation.scripts.run_governance_checks import run_pipeline  # type: ignore
    from automation.scripts.contract_verifier import verify_output_directory  # type: ignore
    return run_pipeline, verify_output_directory


# --------------------------------------------------------------------------- envelope
def envelope(tool: str, result: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
    return {
        "authority_effect": AUTHORITY_EFFECT,
        "review_boundary": REVIEW_BOUNDARY,
        "human_decision_state": "PENDING_HUMAN_DECISION",
        "tool": tool,
        "server": {"name": "gaig-mcp", "version": __version__},
        "source": source,
        "result": result,
    }


def _toolkit_source() -> dict[str, Any]:
    root = toolkit_root()
    return {"repository": "GLOBAL-AI-GOVERNANCE/global-ai-governance-toolkit", "commit": _source_commit("toolkit", "TOOLKIT_PATH", root)}


# --------------------------------------------------------------------------- inventory
def _resolve_inventory(inventory_csv: str | None, use_sample: bool) -> tuple[Path, bool, tempfile.TemporaryDirectory | None]:
    if inventory_csv and use_sample:
        raise GaigInputError("Provide inventory_csv or use_sample=true, not both.")
    if use_sample or not inventory_csv:
        if not use_sample:
            raise GaigInputError("inventory_csv is empty. Supply CSV text or set use_sample=true.")
        return toolkit_root() / "automation" / "sample-data" / "sample-ai-inventory.csv", True, None
    data = inventory_csv.encode("utf-8")
    if len(data) > MAX_INPUT_BYTES:
        raise GaigInputError(f"inventory_csv exceeds {MAX_INPUT_BYTES} bytes.")
    tmp = tempfile.TemporaryDirectory(prefix="gaig-mcp-in-")
    path = Path(tmp.name) / "inventory.csv"
    path.write_bytes(data)
    return path, False, tmp


def _run(inventory_csv: str | None, use_sample: bool, evaluation_time: str | None) -> tuple[Path, tempfile.TemporaryDirectory, bool]:
    run_pipeline, _ = _import_toolkit()
    src, sample, tmp_in = _resolve_inventory(inventory_csv, use_sample)
    out = tempfile.TemporaryDirectory(prefix="gaig-mcp-out-")
    try:
        # The toolkit prints progress to stdout; on stdio transport stdout is the
        # JSON-RPC channel, so all of it is redirected to stderr.
        with contextlib.redirect_stdout(sys.stderr):
            run_pipeline(src, Path(out.name), fail_on="none", evaluation_time=evaluation_time)
    except SystemExit as exc:  # fail_on=none should not exit, but stay fail-closed
        out.cleanup()
        code = exc.code if isinstance(exc.code, int) else 1
        raise GaigInputError(f"Toolkit pipeline stopped (exit {code}).") from exc
    except (OSError, ValueError) as exc:
        out.cleanup()
        raise GaigInputError(_toolkit_rejection(exc)) from exc
    finally:
        if tmp_in is not None:
            tmp_in.cleanup()
    return Path(out.name), out, sample


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check_inventory(inventory_csv: str | None = None, use_sample: bool = False,
                    evaluation_time: str | None = None) -> dict[str, Any]:
    outdir, handle, sample = _run(inventory_csv, use_sample, evaluation_time)
    try:
        result = _load(outdir / "governance-result.json")
        findings = _load(outdir / "governance-findings.json").get("findings", [])
    finally:
        handle.cleanup()
    by_sev: dict[str, int] = {}
    for f in findings:
        by_sev[f.get("severity", "UNKNOWN")] = by_sev.get(f.get("severity", "UNKNOWN"), 0) + 1
    body = {
        "input": "toolkit sample inventory (synthetic)" if sample else "caller-supplied CSV",
        "validation_state": result.get("validation_state"),
        "governance_gate_state": result.get("governance_gate_state"),
        "governance_gate_note": "Gate state is a policy-check outcome for human review, not an approval or denial of deployment.",
        "finding_count": result.get("finding_count", len(findings)),
        "findings_by_severity": by_sev,
        "findings": findings[:MAX_FINDINGS_RETURNED],
        "findings_truncated": len(findings) > MAX_FINDINGS_RETURNED,
        "system_ids": result.get("system_ids", []),
        "input_digest": result.get("input_digest"),
        "policy": {"id": result.get("policy_id"), "version": result.get("policy_version")},
        "evaluation_time": result.get("evaluation_time"),
        "next_human_step": "An accountable owner reviews each finding and records a decision. Use build_decision_pack to prepare the review bundle.",
    }
    return envelope("check_inventory", body, source=_toolkit_source())


def build_decision_pack(inventory_csv: str | None = None, use_sample: bool = False,
                        evaluation_time: str | None = None, include_documents: bool = False) -> dict[str, Any]:
    _, verify_output_directory = _import_toolkit()
    outdir, handle, sample = _run(inventory_csv, use_sample, evaluation_time)
    try:
        manifest = _load(outdir / "decision-pack" / "manifest.json")
        handoff = _load(outdir / "governance-handoff.json")
        try:
            with contextlib.redirect_stdout(sys.stderr):
                verify_output_directory(outdir)
            integrity = "VERIFIED"
        except Exception as exc:  # fail closed and report the category only
            integrity = f"FAILED ({type(exc).__name__})"
        docs: dict[str, str] = {}
        if include_documents:
            for item in manifest.get("generated_files", []):
                p = outdir / "decision-pack" / item["path"]
                if p.suffix == ".md" and p.is_file():
                    docs[item["path"]] = p.read_text(encoding="utf-8")[:MAX_DOCUMENT_CHARS]
    finally:
        handle.cleanup()
    body = {
        "input": "toolkit sample inventory (synthetic)" if sample else "caller-supplied CSV",
        "decision_status": manifest.get("decision_status"),
        "decision_status_note": "The pack prepares a decision. It is not the decision.",
        "governance_gate_result": manifest.get("governance_gate_result"),
        "integrity_check": integrity,
        "manifest": {
            "manifest_schema_version": manifest.get("manifest_schema_version"),
            "hash_mode": manifest.get("hash_mode"),
            "canonical_inventory_digest": manifest.get("canonical_inventory_digest"),
            "evaluation_time": manifest.get("evaluation_time"),
            "generated_files": manifest.get("generated_files", []),
            "source_artifacts": manifest.get("source_artifacts", []),
        },
        "handoff": {
            "target_repository": handoff.get("target_repository"),
            "authority_effect": handoff.get("authority_effect", AUTHORITY_EFFECT),
            "note": "Reference-only handoff. A receiving system must apply its own human authority.",
        },
        "documents": docs,
        "reproduce_locally": "pip install the toolkit, then: gaig check inventory.csv --outdir out/ --fail-on none"
                             + (f" --evaluation-time {evaluation_time}" if evaluation_time else "")
                             + " && gaig verify out/",
    }
    return envelope("build_decision_pack", body, source=_toolkit_source())


# --------------------------------------------------------------------------- passport
def _relabel(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {_RELABEL.get(k, k): _relabel(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_relabel(v) for v in obj]
    return obj


def _write_json(dirpath: Path, name: str, value: Any) -> Path:
    if isinstance(value, str):
        value = json.loads(value)
    data = json.dumps(value).encode("utf-8")
    if len(data) > MAX_INPUT_BYTES:
        raise GaigInputError(f"{name} exceeds {MAX_INPUT_BYTES} bytes.")
    p = dirpath / f"{name}.json"
    p.write_bytes(data)
    return p


def validate_passport(example: str | None = None, passport: dict | str | None = None,
                      trusted_key: dict | str | None = None, revocation_list: dict | str | None = None,
                      at_time: str | None = None) -> dict[str, Any]:
    root = agentic_root()
    tmp = tempfile.TemporaryDirectory(prefix="gaig-mcp-pp-")
    try:
        if example:
            if passport is not None:
                raise GaigInputError("Provide example or passport, not both.")
            if example not in PASSPORT_EXAMPLES:
                raise GaigInputError(f"Unknown example. Use one of {sorted(PASSPORT_EXAMPLES)}.")
            args = ["--trusted-key", EXAMPLE_KEY, "--revocation-list", EXAMPLE_REVOCATION,
                    "--bundle-manifest", EXAMPLE_BUNDLE, "--bundle-root", ".",
                    "--at-time", at_time or EXAMPLE_AT_TIME, PASSPORT_EXAMPLES[example]]
            mode = f"synthetic example '{example}' (test-only keys)"
        else:
            if passport is None or trusted_key is None:
                raise GaigInputError("Provide example, or both passport and trusted_key.")
            d = Path(tmp.name)
            args = ["--trusted-key", str(_write_json(d, "trusted_key", trusted_key))]
            if revocation_list is not None:
                args += ["--revocation-list", str(_write_json(d, "revocation_list", revocation_list))]
            if at_time:
                args += ["--at-time", at_time]
            args.append(str(_write_json(d, "passport", passport)))
            mode = "caller-supplied passport (no evidence bundle supplied; full binding checks cannot complete)"
        proc = subprocess.run([sys.executable, "tools/validate_artifact.py", "--kind", "passport", *args],
                              cwd=root, capture_output=True, text=True, timeout=60)
    except json.JSONDecodeError as exc:
        raise GaigInputError(f"Invalid JSON input (line {exc.lineno}, column {exc.colno}).") from exc
    finally:
        tmp.cleanup()
    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise GaigInputError(f"Validator produced no result (exit {proc.returncode}).") from exc
    raw.pop("artifact", None)  # drop local temp paths
    body = {
        "mode": mode,
        "validator_exit_code": proc.returncode,
        "verification": _relabel(raw),
        "interpretation": (
            "verification_primary_status describes whether the passport verified at the evaluation time. "
            "reference_policy_disposition is what the agentic-ai-governance reference policy computes for these "
            "artifacts. Neither is an authorization issued by gaig-mcp; the receiving platform's accountable human "
            "and its own policy decide whether any action may proceed."
        ),
    }
    source = {"repository": "GLOBAL-AI-GOVERNANCE/agentic-ai-governance", "commit": _source_commit("agentic", "AGENTIC_PATH", root),
              "maturity": "experimental public alpha (v0.1.0-alpha.2 line; main may be ahead)"}
    return envelope("validate_passport", body, source=source)

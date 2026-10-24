#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed verification of passport-bound Alpha.1 input bundles."""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from tools.canonical_json import canonicalize
from tools.reference_policy import (
    AGENT_CAPABILITY_MIN_LEVEL,
    CURRENT_ASSESSMENT_POLICY_ID,
    CURRENT_ASSESSMENT_POLICY_VERSION,
    CURRENT_EVALUATOR_ID,
    CURRENT_EVALUATOR_VERSION,
    CURRENT_PROFILE_ID,
    CURRENT_PROFILE_VERSION,
    DATA_AUTHORITY_SCHEME_POLICIES,
    MCP_SCOPE_MIN_LEVEL,
    REFERENCE_PROFILE_ANCHOR,
    SUPPORTED_CONTROL_IDS,
    SUPPORTED_DATA_AUTHORITY_SCHEMES,
    TOOL_EFFECT_MIN_LEVEL,
    TRUSTED_DATA_AUTHORITY_ISSUERS,
)
from tools.semantic_rules import (
    compute_action_level,
    parse_time,
    validate_action_authority_semantics,
    validate_agent_inventory_semantics,
    validate_assessment_semantics,
    validate_bundle_semantics,
    validate_data_authority_semantics,
    validate_mcp_inventory_semantics,
    validate_profile_descriptor_semantics,
    validate_tool_inventory_semantics,
)
from tools.strict_json import StrictJSONError, load_strict
from tools.verify_repository import domain_id, id_errors, validate_value_schema

ASSESSMENT_MEDIA = "application/agentic-ai-assessment+json"
ACTION_AUTHORITY_MEDIA = "application/agentic-ai-action-authority+json"
AGENT_INVENTORY_MEDIA = "application/agent-inventory+json"
MCP_INVENTORY_MEDIA = "application/mcp-inventory+json"
TOOL_INVENTORY_MEDIA = "application/tool-inventory+json"
CONTROL_PROFILE_MEDIA = "application/agentic-ai-control-profile+markdown"
PROFILE_DESCRIPTOR_MEDIA = "application/agentic-ai-control-profile-descriptor+json"
DATA_AUTHORITY_MEDIA = "application/agentic-ai-data-authority+json"

_REQUIRED_SINGLETONS = {
    ASSESSMENT_MEDIA: "assessment",
    ACTION_AUTHORITY_MEDIA: "action-authority graph",
    AGENT_INVENTORY_MEDIA: "agent inventory",
    MCP_INVENTORY_MEDIA: "MCP inventory",
    TOOL_INVENTORY_MEDIA: "tool inventory",
    CONTROL_PROFILE_MEDIA: "control profile",
    PROFILE_DESCRIPTOR_MEDIA: "control-profile descriptor",
}

_SCHEMA_AND_SEMANTICS: dict[str, tuple[str, Callable[[dict[str, Any]], list[str]]]] = {
    ASSESSMENT_MEDIA: ("assessment-result.schema.json", validate_assessment_semantics),
    ACTION_AUTHORITY_MEDIA: ("action-authority.schema.json", validate_action_authority_semantics),
    AGENT_INVENTORY_MEDIA: ("agent-inventory.schema.json", validate_agent_inventory_semantics),
    MCP_INVENTORY_MEDIA: ("mcp-inventory.schema.json", validate_mcp_inventory_semantics),
    TOOL_INVENTORY_MEDIA: ("tool-inventory.schema.json", validate_tool_inventory_semantics),
    PROFILE_DESCRIPTOR_MEDIA: (
        "control-profile-descriptor.schema.json",
        validate_profile_descriptor_semantics,
    ),
    DATA_AUTHORITY_MEDIA: ("data-authority-evidence.schema.json", validate_data_authority_semantics),
}


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _hash_path(path: Path, canonicalization: str) -> str:
    raw = path.read_bytes()
    if canonicalization == "EXACT_BYTES":
        return _sha256(raw)
    if canonicalization != "JCS":
        raise ValueError(f"unsupported canonicalization: {canonicalization}")
    value = load_strict(path, require_object=True)
    return _sha256(canonicalize(value))


def _data_authority_artifact_hash(value: dict[str, Any]) -> str:
    source = {key: item for key, item in value.items() if key != "artifact_hash"}
    return domain_id(
        "global-ai-governance.data-authority-evidence.artifact.v1",
        "evidence",
        source,
    )


def _entry_map(manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_media: dict[str, list[dict[str, Any]]] = {}
    for entry in manifest.get("files", []):
        if isinstance(entry, dict):
            by_media.setdefault(str(entry.get("media_type")), []).append(entry)
    return by_media


def _single_entry(
    by_media: dict[str, list[dict[str, Any]]],
    media_type: str,
    label: str,
    incomplete: list[str],
) -> dict[str, Any] | None:
    matches = by_media.get(media_type, [])
    if len(matches) != 1:
        incomplete.append(f"bundle must contain exactly one {label}; found {len(matches)}")
        return None
    return matches[0]


def _resolved_file(root: Path, entry: dict[str, Any]) -> Path:
    rel = PurePosixPath(entry["path"])
    candidate = root.joinpath(*rel.parts)
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve(strict=True)
    if root_resolved != candidate_resolved and root_resolved not in candidate_resolved.parents:
        raise ValueError(f"bundle path escapes root: {entry['path']}")
    if candidate.is_symlink() or not candidate_resolved.is_file():
        raise ValueError(f"bundle entry is not a regular file: {entry['path']}")
    return candidate_resolved


def _load_bound_json(
    *,
    media_type: str,
    entry: dict[str, Any],
    file_by_path: dict[str, Path],
    repository_root: Path,
    schema_store: Any,
    incomplete: list[str],
) -> dict[str, Any] | None:
    path = file_by_path.get(entry["path"])
    if path is None:
        incomplete.append(f"{entry['path']} was not available after bundle verification")
        return None
    try:
        value = load_strict(path, require_object=True)
    except StrictJSONError as exc:
        incomplete.append(f"{entry['path']} is invalid JSON: {exc}")
        return None
    schema_name, semantic = _SCHEMA_AND_SEMANTICS[media_type]
    for message in validate_value_schema(repository_root, schema_name, value, schema_store):
        incomplete.append(f"{entry['path']} schema: {message}")
    for message in semantic(value):
        incomplete.append(f"{entry['path']} semantics: {message}")
    return value


def _scope_covers(evidence: dict[str, Any], agent_inventory: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scope = evidence.get("scope", {})
    requested = agent_inventory.get("data_use", {})
    for field in ("data_classes", "purposes", "systems", "jurisdictions"):
        admitted = set(scope.get(field, []))
        wanted = set(requested.get(field, []))
        missing = sorted(wanted - admitted)
        if missing:
            errors.append(f"data-authority scope does not cover data_use.{field}: {missing}")
    prohibited = set(scope.get("prohibited_uses", []))
    prohibited_requested = sorted(set(requested.get("purposes", [])) & prohibited)
    if prohibited_requested:
        errors.append(f"data-authority scope prohibits requested purposes: {prohibited_requested}")
    return errors



def _minimum_level(values: list[str], mapping: dict[str, int]) -> int:
    return max((mapping.get(value, 6) for value in values), default=0)


def _canonical_profile_anchor_errors(
    descriptor: dict[str, Any],
    *,
    descriptor_hash: str,
    document_hash: str,
) -> list[str]:
    errors: list[str] = []
    anchor = REFERENCE_PROFILE_ANCHOR
    if descriptor_hash != anchor["descriptor_sha256"]:
        errors.append("bound profile descriptor does not match the independently pinned descriptor hash")
    if document_hash != anchor["document_sha256"]:
        errors.append("bound profile document does not match the independently pinned document hash")
    if descriptor.get("profile_id") != anchor["profile_id"]:
        errors.append("profile_id differs from the independently pinned profile")
    if descriptor.get("profile_version") != anchor["profile_version"]:
        errors.append("profile_version differs from the independently pinned profile")
    if set(descriptor.get("supported_control_ids", [])) != set(anchor["supported_control_ids"]):
        errors.append("supported controls differ from the independently pinned profile")
    if set(descriptor.get("trusted_data_authority_issuers", [])) != set(
        anchor["trusted_data_authority_issuers"]
    ):
        errors.append("trusted data-authority issuers differ from the independently pinned profile")
    actual_schemes = {
        (item.get("scheme"), item.get("scheme_version")): {
            "requires_signature": item.get("requires_signature")
        }
        for item in descriptor.get("supported_data_authority_schemes", [])
        if isinstance(item, dict)
    }
    if actual_schemes != anchor["data_authority_scheme_policies"]:
        errors.append("data-authority scheme policy differs from the independently pinned profile")
    evaluator = descriptor.get("evaluator", {})
    if evaluator.get("id") != anchor["evaluator_id"] or evaluator.get("version") != anchor["evaluator_version"]:
        errors.append("evaluator differs from the independently pinned profile")
    policy = descriptor.get("assessment_policy", {})
    if policy.get("id") != anchor["assessment_policy_id"] or policy.get("version") != anchor["assessment_policy_version"]:
        errors.append("assessment policy differs from the independently pinned profile")
    if descriptor.get("production_use_permitted") is not anchor["production_use_permitted"]:
        errors.append("production-use posture differs from the independently pinned profile")
    return errors

def _status_from_issues(
    *,
    incomplete: list[str],
    mismatch: list[str],
    data_invalid: list[str],
    data_unknown: list[str],
    unsupported_profile: list[str],
    unsupported_evaluator: list[str],
    unsupported_policy: list[str],
) -> tuple[str, list[str]] | None:
    priorities = (
        ("UNSUPPORTED_PROFILE", unsupported_profile),
        ("UNSUPPORTED_EVALUATOR", unsupported_evaluator),
        ("UNSUPPORTED_POLICY", unsupported_policy),
        ("DATA_AUTHORITY_INVALID", data_invalid),
        ("DATA_AUTHORITY_UNKNOWN", data_unknown),
        ("BOUND_INPUTS_INCOMPLETE", incomplete),
        ("INPUT_MISMATCH", mismatch),
    )
    for status, issues in priorities:
        if issues:
            return status, issues
    return None


def verify_passport_bindings(
    passport: dict[str, Any],
    *,
    manifest_path: Path,
    bundle_root: Path,
    repository_root: Path,
    schema_store: Any,
    at_time: datetime,
) -> tuple[str, list[str]]:
    """Return PASS or a normative binding status plus deterministic diagnostics."""
    incomplete: list[str] = []
    mismatch: list[str] = []
    data_invalid: list[str] = []
    data_unknown: list[str] = []
    unsupported_profile: list[str] = []
    unsupported_evaluator: list[str] = []
    unsupported_policy: list[str] = []

    try:
        manifest = load_strict(manifest_path, require_object=True)
    except StrictJSONError as exc:
        return "BOUND_INPUTS_INCOMPLETE", [f"bundle manifest is invalid JSON: {exc}"]

    schema_errors = validate_value_schema(
        repository_root,
        "bundle-manifest.schema.json",
        manifest,
        schema_store,
    )
    if schema_errors:
        return "BOUND_INPUTS_INCOMPLETE", [f"bundle manifest schema: {msg}" for msg in schema_errors]

    semantic_errors = validate_bundle_semantics(manifest)
    if semantic_errors:
        return "BOUND_INPUTS_INCOMPLETE", [f"bundle manifest semantics: {msg}" for msg in semantic_errors]

    identifier_errors = id_errors("bundle", manifest)
    if identifier_errors:
        return "INPUT_MISMATCH", [f"bundle manifest identifier: {msg}" for msg in identifier_errors]

    if passport.get("bindings", {}).get("assessment_bundle") != manifest.get("bundle_id"):
        mismatch.append("passport assessment_bundle does not equal the supplied manifest bundle_id")

    root = bundle_root.resolve()
    file_by_path: dict[str, Path] = {}
    for entry in manifest.get("files", []):
        path_text = entry.get("path")
        if not isinstance(path_text, str):
            incomplete.append("bundle contains an entry without a valid path")
            continue
        try:
            path = _resolved_file(root, entry)
        except (FileNotFoundError, OSError, ValueError) as exc:
            incomplete.append(str(exc))
            continue
        file_by_path[path_text] = path
        actual_size = path.stat().st_size
        if actual_size != entry.get("size_bytes"):
            mismatch.append(
                f"bundle file size mismatch for {path_text}: expected {entry.get('size_bytes')}, got {actual_size}"
            )
        try:
            actual_hash = _hash_path(path, entry.get("canonicalization"))
        except (OSError, StrictJSONError, ValueError) as exc:
            mismatch.append(f"bundle file hash could not be calculated for {path_text}: {exc}")
            continue
        if actual_hash != entry.get("hash"):
            mismatch.append(
                f"bundle file hash mismatch for {path_text}: expected {entry.get('hash')}, got {actual_hash}"
            )

    by_media = _entry_map(manifest)
    selected: dict[str, dict[str, Any]] = {}
    for media_type, label in _REQUIRED_SINGLETONS.items():
        entry = _single_entry(by_media, media_type, label, incomplete)
        if entry is not None:
            selected[media_type] = entry

    data_entries = by_media.get(DATA_AUTHORITY_MEDIA, [])
    if not data_entries:
        incomplete.append("bundle must contain at least one data-authority evidence artifact")

    early = _status_from_issues(
        incomplete=incomplete,
        mismatch=mismatch,
        data_invalid=data_invalid,
        data_unknown=data_unknown,
        unsupported_profile=unsupported_profile,
        unsupported_evaluator=unsupported_evaluator,
        unsupported_policy=unsupported_policy,
    )
    if early:
        return early

    values: dict[str, dict[str, Any]] = {}
    for media_type, entry in selected.items():
        if media_type == CONTROL_PROFILE_MEDIA:
            continue
        value = _load_bound_json(
            media_type=media_type,
            entry=entry,
            file_by_path=file_by_path,
            repository_root=repository_root,
            schema_store=schema_store,
            incomplete=incomplete,
        )
        if value is not None:
            values[media_type] = value

    evidence_values: list[dict[str, Any]] = []
    for entry in data_entries:
        value = _load_bound_json(
            media_type=DATA_AUTHORITY_MEDIA,
            entry=entry,
            file_by_path=file_by_path,
            repository_root=repository_root,
            schema_store=schema_store,
            incomplete=data_invalid,
        )
        if value is not None:
            evidence_values.append(value)

    early = _status_from_issues(
        incomplete=incomplete,
        mismatch=mismatch,
        data_invalid=data_invalid,
        data_unknown=data_unknown,
        unsupported_profile=unsupported_profile,
        unsupported_evaluator=unsupported_evaluator,
        unsupported_policy=unsupported_policy,
    )
    if early:
        return early

    bindings = passport.get("bindings", {})
    comparisons = {
        "action_authority_graph": selected[ACTION_AUTHORITY_MEDIA]["hash"],
        "agent_inventory": selected[AGENT_INVENTORY_MEDIA]["hash"],
        "mcp_inventory": selected[MCP_INVENTORY_MEDIA]["hash"],
        "tool_inventory": selected[TOOL_INVENTORY_MEDIA]["hash"],
        "control_profile": selected[CONTROL_PROFILE_MEDIA]["hash"],
        "control_profile_descriptor": selected[PROFILE_DESCRIPTOR_MEDIA]["hash"],
    }
    for field, expected in comparisons.items():
        if bindings.get(field) != expected:
            mismatch.append(f"passport {field} binding does not match the supplied bundle")

    evidence_hashes = sorted(entry["hash"] for entry in data_entries)
    if bindings.get("data_authority_evidence") != evidence_hashes:
        mismatch.append("passport data_authority_evidence bindings do not match the supplied bundle")

    assessment = values[ASSESSMENT_MEDIA]
    graph = values[ACTION_AUTHORITY_MEDIA]
    agent_inventory = values[AGENT_INVENTORY_MEDIA]
    mcp_inventory = values[MCP_INVENTORY_MEDIA]
    tool_inventory = values[TOOL_INVENTORY_MEDIA]
    descriptor = values[PROFILE_DESCRIPTOR_MEDIA]

    for message in id_errors("assessment", assessment):
        mismatch.append(f"assessment identifier: {message}")

    unsupported_profile.extend(
        _canonical_profile_anchor_errors(
            descriptor,
            descriptor_hash=selected[PROFILE_DESCRIPTOR_MEDIA]["hash"],
            document_hash=selected[CONTROL_PROFILE_MEDIA]["hash"],
        )
    )

    profile = passport.get("profile", {})
    if descriptor.get("profile_id") != CURRENT_PROFILE_ID or profile.get("id") != CURRENT_PROFILE_ID:
        unsupported_profile.append("Alpha.1 supports only global-ai-governance.mcp-governance")
    if descriptor.get("profile_version") != CURRENT_PROFILE_VERSION or profile.get("version") != CURRENT_PROFILE_VERSION:
        unsupported_profile.append("passport and descriptor profile versions must equal 0.1.0-alpha.1")
    if descriptor.get("profile_id") != profile.get("id") or descriptor.get("profile_version") != profile.get("version"):
        mismatch.append("passport profile does not match the bound profile descriptor")

    descriptor_evaluator = descriptor.get("evaluator", {})
    if (
        descriptor_evaluator.get("id") != CURRENT_EVALUATOR_ID
        or descriptor_evaluator.get("version") != CURRENT_EVALUATOR_VERSION
    ):
        unsupported_evaluator.append("bound profile descriptor names an unsupported evaluator")
    if (
        bindings.get("evaluator_id") != descriptor_evaluator.get("id")
        or bindings.get("evaluator_version") != descriptor_evaluator.get("version")
    ):
        mismatch.append("passport evaluator binding does not match the bound profile descriptor")

    descriptor_policy = descriptor.get("assessment_policy", {})
    if (
        descriptor_policy.get("id") != CURRENT_ASSESSMENT_POLICY_ID
        or descriptor_policy.get("version") != CURRENT_ASSESSMENT_POLICY_VERSION
    ):
        unsupported_policy.append("bound profile descriptor names an unsupported assessment policy")
    if (
        bindings.get("assessment_policy_id") != descriptor_policy.get("id")
        or bindings.get("assessment_policy_version") != descriptor_policy.get("version")
    ):
        mismatch.append("passport assessment-policy binding does not match the bound profile descriptor")

    if bindings.get("evaluator_id") != CURRENT_EVALUATOR_ID or bindings.get("evaluator_version") != CURRENT_EVALUATOR_VERSION:
        unsupported_evaluator.append("passport names an unsupported evaluator")
    if (
        bindings.get("assessment_policy_id") != CURRENT_ASSESSMENT_POLICY_ID
        or bindings.get("assessment_policy_version") != CURRENT_ASSESSMENT_POLICY_VERSION
    ):
        unsupported_policy.append("passport names an unsupported assessment policy")

    profile_hash = selected[CONTROL_PROFILE_MEDIA]["hash"]
    if descriptor.get("control_profile", {}).get("hash") != profile_hash:
        mismatch.append("profile descriptor content hash does not match the bound control profile")

    subject_agent = passport.get("subject", {}).get("agent_id")
    for label, inventory in (
        ("agent inventory", agent_inventory),
        ("MCP inventory", mcp_inventory),
        ("tool inventory", tool_inventory),
    ):
        if inventory.get("agent_id") != subject_agent:
            mismatch.append(f"{label} agent_id does not match passport subject")
        if inventory.get("production_use") and not descriptor.get("production_use_permitted"):
            unsupported_profile.append(f"{label} declares production use under a non-production Alpha.1 profile")

    if graph.get("agent_id") != subject_agent:
        mismatch.append("action-authority graph agent_id does not match passport subject")
    calculated_level = compute_action_level(graph)
    if graph.get("computed_level") != calculated_level:
        mismatch.append("action-authority graph computed_level is not reproducible")
    if graph.get("requested_level") != assessment.get("requested_action_level"):
        mismatch.append("action-authority requested_level does not match the assessment")
    if graph.get("computed_level") > assessment.get("maximum_action_level", -1):
        mismatch.append("action-authority computed_level exceeds the assessment maximum")
    if graph.get("computed_level") > passport.get("issued_assessment", {}).get("maximum_action_level", -1):
        mismatch.append("action-authority computed_level exceeds the passport maximum")
    if graph.get("computed_level") == 5 and passport.get("issued_assessment", {}).get("result") in {
        "APPROVED",
        "APPROVED_WITH_CONDITIONS",
    }:
        mismatch.append("Level 5 action authority cannot receive a permitted Alpha.1 result")

    condition_maxima = [
        condition.get("temporary_restriction", {}).get("maximum_action_level")
        for condition in assessment.get("conditions", [])
        if isinstance(condition, dict)
    ]
    effective_maximum = min(
        [assessment.get("maximum_action_level", 5), passport.get("issued_assessment", {}).get("maximum_action_level", 5)]
        + [value for value in condition_maxima if isinstance(value, int)]
    )
    if graph.get("computed_level", 6) > effective_maximum:
        mismatch.append(
            "action-authority computed_level exceeds the effective maximum after active condition restrictions"
        )

    capability_level = _minimum_level(
        agent_inventory.get("declared_capabilities", []), AGENT_CAPABILITY_MIN_LEVEL
    )
    if capability_level > graph.get("computed_level", -1):
        mismatch.append("agent capabilities require a higher action level than the graph provides")

    graph_nodes = {
        node.get("node_id"): node
        for node in graph.get("nodes", [])
        if isinstance(node, dict)
    }
    inventory_mcp_ids = {
        server.get("server_id")
        for server in mcp_inventory.get("servers", [])
        if isinstance(server, dict)
    }
    graph_mcp_ids = {
        node.get("node_id")
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("node_type") == "MCP_SERVER"
    }
    undeclared_graph_servers = sorted(graph_mcp_ids - inventory_mcp_ids)
    missing_graph_servers = sorted(inventory_mcp_ids - graph_mcp_ids)
    if undeclared_graph_servers:
        mismatch.append(
            "action graph references MCP servers absent from inventory: "
            f"{undeclared_graph_servers}"
        )
    if missing_graph_servers:
        mismatch.append(
            "MCP inventory servers are absent from the action graph: "
            f"{missing_graph_servers}"
        )

    for server in mcp_inventory.get("servers", []):
        server_id = server.get("server_id")
        node = graph_nodes.get(server_id)
        if not isinstance(node, dict) or node.get("node_type") != "MCP_SERVER":
            mismatch.append(f"MCP server {server_id} is not represented by a reachable MCP_SERVER graph node")
            continue
        scope_level = _minimum_level(server.get("declared_scope", []), MCP_SCOPE_MIN_LEVEL)
        if node.get("base_level", -1) < scope_level:
            mismatch.append(f"MCP server {server_id} graph level does not cover its declared scopes")
        if graph.get("computed_level", -1) < scope_level:
            mismatch.append(f"MCP scope on {server_id} exceeds the graph computed level")

    graph_tools = {
        node.get("node_id"): node.get("base_level")
        for node in graph.get("nodes", [])
        if node.get("node_type") == "TOOL"
    }
    inventory_tools: dict[str, int] = {}
    for tool in tool_inventory.get("tools", []):
        tool_id = tool.get("tool_id")
        effect_level = _minimum_level(tool.get("effects", []), TOOL_EFFECT_MIN_LEVEL)
        declared_level = tool.get("action_level", -1)
        if declared_level < effect_level:
            mismatch.append(f"tool {tool_id} action_level is below the minimum required by its effects")
        inventory_tools[tool_id] = max(declared_level, effect_level)
    if graph_tools != inventory_tools:
        mismatch.append("tool inventory effects and action-authority graph TOOL nodes do not match")
    if inventory_tools and max(inventory_tools.values()) > graph.get("computed_level", -1):
        mismatch.append("tool effects exceed the graph computed level")

    supported_controls = set(SUPPORTED_CONTROL_IDS)
    assessment_controls = {item.get("control_id") for item in assessment.get("control_results", [])}
    unsupported_controls = sorted(assessment_controls - supported_controls)
    if unsupported_controls:
        unsupported_policy.append(f"assessment uses controls not supported by the profile: {unsupported_controls}")

    issued = passport.get("issued_assessment", {})
    projection_checks = {
        "assessment_id": assessment.get("assessment_id"),
        "result": assessment.get("result"),
        "evaluated_at": assessment.get("evaluated_at"),
        "data_authority_status": assessment.get("data_authority_status"),
        "maximum_action_level": assessment.get("maximum_action_level"),
    }
    for field, expected in projection_checks.items():
        if issued.get(field) != expected:
            mismatch.append(f"passport issued_assessment.{field} does not match the bound assessment")

    counts = {name: 0 for name in ("PASS", "FAIL", "NOT_APPLICABLE", "NOT_EVALUATED", "ERROR")}
    for control in assessment.get("control_results", []):
        outcome = control.get("outcome")
        if outcome in counts:
            counts[outcome] += 1
    if issued.get("control_summary") != counts:
        mismatch.append("passport control_summary does not match the bound assessment")
    if canonicalize(passport.get("conditions", [])) != canonicalize(assessment.get("conditions", [])):
        mismatch.append("passport conditions do not exactly match the bound assessment conditions")

    descriptor_schemes = set(DATA_AUTHORITY_SCHEME_POLICIES)
    trusted_issuers = set(TRUSTED_DATA_AUTHORITY_ISSUERS)
    evidence_by_id: dict[str, dict[str, Any]] = {}
    for evidence in evidence_values:
        evidence_id = evidence.get("evidence_id")
        if evidence_id in evidence_by_id:
            data_invalid.append(f"duplicate admitted evidence_id: {evidence_id}")
        else:
            evidence_by_id[evidence_id] = evidence

        expected_artifact_hash = _data_authority_artifact_hash(evidence)
        if evidence.get("artifact_hash") != expected_artifact_hash:
            data_invalid.append(f"{evidence_id}: artifact_hash is not content-derived from the evidence")

        scheme_key = (evidence.get("scheme"), evidence.get("scheme_version"))
        scheme_policy = DATA_AUTHORITY_SCHEME_POLICIES.get(scheme_key)
        if scheme_key not in SUPPORTED_DATA_AUTHORITY_SCHEMES or scheme_key not in descriptor_schemes:
            data_unknown.append(f"{evidence_id}: unsupported data-authority scheme or version")
        elif scheme_policy and scheme_policy.get("requires_signature") and not evidence.get("proof"):
            data_unknown.append(f"{evidence_id}: the anchored data-authority scheme requires a signature")
        if evidence.get("issuer_id") not in trusted_issuers:
            data_unknown.append(f"{evidence_id}: data-authority issuer is not trusted by the profile")
        if evidence.get("subject", {}).get("agent_id") != subject_agent:
            data_invalid.append(f"{evidence_id}: evidence subject does not match passport subject")
        try:
            not_before = parse_time(evidence["validity"]["not_before"])
            expires_at = parse_time(evidence["validity"]["expires_at"])
            assessment_time = parse_time(assessment["evaluated_at"])
            if assessment_time < not_before or assessment_time >= expires_at:
                data_invalid.append(f"{evidence_id}: evidence was not valid when the assessment was evaluated")
            if at_time < not_before or at_time >= expires_at:
                data_invalid.append(f"{evidence_id}: evidence is not valid at the verifier evaluation time")
        except (KeyError, TypeError, ValueError) as exc:
            data_invalid.append(f"{evidence_id}: invalid evidence validity: {exc}")
        data_invalid.extend(f"{evidence_id}: {message}" for message in _scope_covers(evidence, agent_inventory))

    admitted_ids = set(evidence_by_id)
    unresolved: set[str] = set()
    for control in assessment.get("control_results", []):
        unresolved.update(set(control.get("evidence_refs", [])) - admitted_ids)
    for condition in assessment.get("conditions", []):
        unresolved.update(set(condition.get("required_evidence", [])) - admitted_ids)
    if unresolved:
        mismatch.append(f"assessment references evidence not admitted by the bundle: {sorted(unresolved)}")

    if assessment.get("data_authority_status") == "VERIFIED" and not evidence_values:
        data_unknown.append("VERIFIED data authority requires admitted evidence")
    if assessment.get("data_authority_status") in {"UNKNOWN", "INVALID"} and issued.get("result") in {
        "APPROVED",
        "APPROVED_WITH_CONDITIONS",
    }:
        mismatch.append("bound assessment data-authority status cannot support the passport result")

    final = _status_from_issues(
        incomplete=incomplete,
        mismatch=mismatch,
        data_invalid=data_invalid,
        data_unknown=data_unknown,
        unsupported_profile=unsupported_profile,
        unsupported_evaluator=unsupported_evaluator,
        unsupported_policy=unsupported_policy,
    )
    if final:
        return final
    return "PASS", []

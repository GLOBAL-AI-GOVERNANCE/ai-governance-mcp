#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import re
import unicodedata
from typing import Any

from tools.reference_policy import EDGE_REQUIRED_DIMENSION, EDGE_TYPE_MIN_LEVEL

_RFC3339_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
SUPPORTED_CRITICAL_EXTENSIONS: frozenset[str] = frozenset()


def parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not _RFC3339_UTC.fullmatch(value):
        raise ValueError("timestamp must use YYYY-MM-DDTHH:MM:SSZ")
    if value[17:19] == "60":
        raise ValueError("leap seconds are prohibited in Alpha.1")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"invalid calendar timestamp: {value}") from exc
    return parsed.replace(tzinfo=timezone.utc)


def validate_timestamp(value: Any, field: str) -> list[str]:
    try:
        parse_time(value)
    except (TypeError, ValueError) as exc:
        return [f"{field}: {exc}"]
    return []


def validate_bundle_path(path: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(path, str) or not path:
        return ["bundle path must be a non-empty string"]
    if unicodedata.normalize("NFC", path) != path:
        errors.append("bundle path must already be Unicode NFC")
    if path.startswith("/") or _DRIVE_PREFIX.match(path):
        errors.append("bundle path must be relative and must not use a drive prefix")
    if "\\" in path:
        errors.append("bundle path must use forward slashes only")
    if any(ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F for ch in path):
        errors.append("bundle path must not contain control characters")
    if any(segment in {"", ".", ".."} for segment in path.split("/")):
        errors.append("bundle path must not contain empty, dot, or dot-dot segments")
    return errors


def validate_bundle_tree(root: Path, paths: list[str]) -> list[str]:
    errors: list[str] = []
    for rel in paths:
        candidate = root / PurePosixPath(rel)
        if candidate.is_symlink():
            errors.append(f"bundle entry is a symlink: {rel}")
    return errors


def validate_protected_header(header: dict[str, Any], *, content_type: str, type_value: str = "atp+jws") -> list[str]:
    errors: list[str] = []
    required = {"alg", "kid", "typ", "cty"}
    if set(header) != required:
        errors.append("protected header must contain exactly alg, kid, typ, and cty")
    if header.get("alg") != "Ed25519": errors.append("alg must be Ed25519")
    if not isinstance(header.get("kid"), str) or not header.get("kid"): errors.append("kid must be a non-empty string")
    if header.get("typ") != type_value: errors.append("unexpected typ")
    if header.get("cty") != content_type: errors.append("unexpected cty")
    if "b64" in header or "crit" in header: errors.append("RFC 7797 mode is prohibited")
    return errors


def validate_bundle_semantics(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    files=value.get("files", [])
    paths = [f.get("path") for f in files if isinstance(f, dict)]
    for path in paths: errors.extend(validate_bundle_path(path))
    if paths != sorted(paths, key=lambda p: p.encode("utf-16-be")): errors.append("files must be sorted by UTF-16 canonical path order")
    if len(paths) != len(set(paths)): errors.append("duplicate paths")
    folded = [unicodedata.normalize("NFC", p).casefold() for p in paths if isinstance(p,str)]
    if len(folded) != len(set(folded)): errors.append("Unicode case-folded path collision")
    return errors


def validate_passport_semantics(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    attestation = value.get("assurance", {}).get("attestation_status")
    if attestation == "NONE" and "proof" in value:
        errors.append("unsigned passport must omit proof")
    if attestation == "ISSUER_SIGNED" and "proof" not in value:
        errors.append("signed passport requires proof")
    if "proof" in value and set(value["proof"]) != {"jws"}:
        errors.append("proof may contain only jws")

    conditions = value.get("conditions", [])
    ids = [condition.get("condition_id") for condition in conditions]
    if ids != sorted(ids):
        errors.append("conditions must be sorted by condition_id")
    if len(ids) != len(set(ids)):
        errors.append("duplicate condition_id")

    bindings = value.get("bindings", {})
    hashes = bindings.get("data_authority_evidence", [])
    if hashes != sorted(hashes):
        errors.append("data_authority_evidence must be sorted")
    if len(hashes) != len(set(hashes)):
        errors.append("duplicate data_authority_evidence")
    if bindings.get("evaluator_version") == "not-implemented":
        errors.append("evaluator_version must identify the evaluator that produced the assessment")

    critical = value.get("critical_extensions", [])
    if critical != sorted(critical):
        errors.append("critical_extensions must be sorted")
    extensions = value.get("extensions", {})
    for key in critical:
        if key not in extensions:
            errors.append(f"critical extension {key} is not present")

    issued = value.get("issued_assessment", {})
    errors.extend(validate_timestamp(issued.get("evaluated_at"), "issued_assessment.evaluated_at"))
    result = issued.get("result")
    summary = issued.get("control_summary", {})
    maximum = issued.get("maximum_action_level")
    fail_count = summary.get("FAIL", 0)
    error_count = summary.get("ERROR", 0)
    not_evaluated_count = summary.get("NOT_EVALUATED", 0)

    if result == "APPROVED":
        if any((fail_count, error_count, not_evaluated_count)):
            errors.append("APPROVED requires FAIL, ERROR, and NOT_EVALUATED counts to be zero")
        if conditions:
            errors.append("APPROVED requires no conditions")
        if maximum == 5:
            errors.append("APPROVED cannot authorize Level 5 in Alpha.1")
    elif result == "APPROVED_WITH_CONDITIONS":
        if not conditions:
            errors.append("APPROVED_WITH_CONDITIONS requires at least one condition")
        if any((fail_count, error_count)):
            errors.append("APPROVED_WITH_CONDITIONS cannot contain FAIL or ERROR controls")
        if maximum == 5:
            errors.append("APPROVED_WITH_CONDITIONS cannot authorize Level 5 in Alpha.1")

    validity = value.get("validity", {})
    if validity:
        time_errors: list[str] = []
        time_errors.extend(validate_timestamp(validity.get("not_before"), "validity.not_before"))
        time_errors.extend(validate_timestamp(validity.get("expires_at"), "validity.expires_at"))
        errors.extend(time_errors)
        if not time_errors:
            not_before = parse_time(validity["not_before"])
            expires_at = parse_time(validity["expires_at"])
            if not_before >= expires_at:
                errors.append("not_before must precede expires_at")
            for condition in conditions:
                try:
                    deadline = parse_time(condition["deadline"])
                except (KeyError, ValueError) as exc:
                    errors.append(f"condition deadline: {exc}")
                    continue
                if expires_at > deadline:
                    errors.append("passport expires after a condition deadline")
    return errors


def validate_assessment_semantics(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_timestamp(value.get("evaluated_at"), "evaluated_at"))
    requested=value.get("requested_action_level"); maximum=value.get("maximum_action_level"); result=value.get("result")
    data_authority_status=value.get("data_authority_status")
    if data_authority_status == "UNKNOWN" and result not in {"RESTRICTED", "REJECTED"}: errors.append("UNKNOWN data authority cannot exceed RESTRICTED")
    if data_authority_status == "INVALID" and result != "REJECTED": errors.append("INVALID data authority requires REJECTED")
    if requested == 5 and result in {"APPROVED", "APPROVED_WITH_CONDITIONS"}: errors.append("requested Level 5 cannot receive APPROVED or APPROVED_WITH_CONDITIONS in Alpha.1")
    if isinstance(maximum,int) and isinstance(requested,int) and maximum > requested: errors.append("maximum_action_level cannot exceed requested_action_level")
    controls=value.get("control_results",[])
    control_ids=[c.get("control_id") for c in controls]
    if len(control_ids)!=len(set(control_ids)): errors.append("duplicate control_id")
    for c in controls:
        outcome=c.get("outcome"); applicable=c.get("applicable")
        if outcome=="NOT_APPLICABLE" and applicable is not False: errors.append(f"{c.get('control_id')}: NOT_APPLICABLE requires applicable=false")
        if outcome!="NOT_APPLICABLE" and applicable is not True: errors.append(f"{c.get('control_id')}: applicable=false requires NOT_APPLICABLE")
    conditions=value.get("conditions",[])
    condition_ids=[c.get("condition_id") for c in conditions]
    if len(condition_ids)!=len(set(condition_ids)): errors.append("duplicate condition_id")
    for c in conditions:
        errors.extend(validate_timestamp(c.get("deadline"), f"condition {c.get('condition_id')}.deadline"))
        if c.get("control_id") not in control_ids: errors.append(f"condition {c.get('condition_id')} references unknown control_id")
    bad={c.get("outcome") for c in controls} & {"FAIL","NOT_EVALUATED","ERROR"}
    if result=="APPROVED":
        if conditions: errors.append("APPROVED requires no conditions")
        if bad: errors.append("APPROVED requires every applicable control to PASS")
    if result=="APPROVED_WITH_CONDITIONS":
        if not conditions: errors.append("APPROVED_WITH_CONDITIONS requires at least one condition")
        if {c.get("outcome") for c in controls} & {"FAIL","ERROR"}: errors.append("APPROVED_WITH_CONDITIONS cannot contain FAIL or ERROR outcomes")
    return errors


def validate_verification_semantics(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_timestamp(value.get("verified_at"), "verified_at"))
    status=value.get("primary_status"); disposition=value.get("operating_disposition"); attestation=value.get("attestation_status"); issued=value.get("issued_assessment_result")
    components=value.get("components",{})
    if status != "VALID" and disposition != "NOT_PERMITTED": errors.append("non-VALID status must map to NOT_PERMITTED under the reference policy")
    if status == "VALID":
        common_pass={"structure","version","identifier","critical_extensions","bindings","validity","conditions"}
        for name in common_pass:
            if components.get(name)!="PASS": errors.append(f"VALID requires components.{name}=PASS")
        if attestation=="NONE":
            expected={"signature":"NOT_PRESENT","signing_key":"NOT_APPLICABLE","issuer_authentication":"NOT_ESTABLISHED","revocation":"NOT_APPLICABLE"}
            for name,want in expected.items():
                if components.get(name)!=want: errors.append(f"unsigned VALID requires components.{name}={want}")
        elif attestation=="ISSUER_SIGNED":
            for name in {"signature","signing_key","issuer_authentication","revocation"}:
                if components.get(name)!="PASS": errors.append(f"signed VALID requires components.{name}=PASS")
        if issued=="REJECTED" and disposition!="NOT_PERMITTED": errors.append("REJECTED assessment must map to NOT_PERMITTED")
        elif issued=="RESTRICTED" and disposition!="RESTRICTED": errors.append("RESTRICTED assessment must map to RESTRICTED")
        elif attestation=="NONE" and disposition!="INDETERMINATE": errors.append("VALID unsigned passport must map to INDETERMINATE by default")
        elif issued=="APPROVED" and attestation=="ISSUER_SIGNED" and disposition!="PERMITTED": errors.append("signed APPROVED + VALID must map to PERMITTED")
        elif issued=="APPROVED_WITH_CONDITIONS" and attestation=="ISSUER_SIGNED" and disposition!="PERMITTED_WITH_CONDITIONS": errors.append("signed APPROVED_WITH_CONDITIONS + VALID must map to PERMITTED_WITH_CONDITIONS")
    return errors


def compute_action_level(value: dict[str, Any]) -> int:
    nodes = value.get("nodes", [])
    edges = value.get("edges", [])
    agent = value.get("agent_id")
    by_id = {node.get("node_id"): node for node in nodes if isinstance(node, dict)}
    adjacency = {node_id: [] for node_id in by_id}
    for edge in edges:
        if edge.get("from") in adjacency:
            adjacency[edge["from"]].append(edge.get("to"))
    reachable: set[str] = set()
    queue = deque([agent])
    while queue:
        node = queue.popleft()
        if node in reachable or node not in by_id:
            continue
        reachable.add(node)
        queue.extend(adjacency.get(node, []))
    level = max(
        [value.get("requested_level", 0)]
        + [by_id[node].get("base_level", 0) for node in reachable]
        + [
            EDGE_TYPE_MIN_LEVEL.get(edge.get("edge_type"), 0)
            for edge in edges
            if edge.get("from") in reachable and edge.get("to") in reachable
        ]
    )
    dimensions = value.get("dimensions", {})
    if any(dimensions.get(key) for key in ("delegation", "unattended", "code_execution")):
        level = max(level, 3)
    if any(
        dimensions.get(key)
        for key in ("credential_change", "identity_change", "external_publication", "data_movement")
    ):
        level = max(level, 4)
    if dimensions.get("self_modification"):
        level = max(level, 5)
    if dimensions.get("reversibility") == "PARTIAL":
        level = max(level, 3)
    if dimensions.get("reversibility") == "NONE":
        level = max(level, 4)
    level = max(
        level,
        {"LOCAL": 0, "TEAM": 3, "ORGANIZATION": 4, "EXTERNAL": 4, "CRITICAL": 5}.get(
            dimensions.get("blast_radius"), 0
        ),
    )
    return min(level, 5)

def validate_action_authority_semantics(value: dict[str, Any]) -> list[str]:
    errors=[]; nodes=value.get("nodes",[]); edges=value.get("edges",[])
    ids=[n.get("node_id") for n in nodes]
    if len(ids)!=len(set(ids)): errors.append("duplicate node_id")
    by_id={n.get("node_id"):n for n in nodes}
    agent=value.get("agent_id")
    if agent not in by_id or by_id.get(agent,{}).get("node_type")!="AGENT": errors.append("agent_id must identify an AGENT node")
    edge_keys=[]
    for e in edges:
        if e.get("from") not in by_id: errors.append("edge references unknown from node")
        if e.get("to") not in by_id: errors.append("edge references unknown to node")
        edge_keys.append((e.get("from"),e.get("to"),e.get("edge_type")))
    if len(edge_keys)!=len(set(edge_keys)): errors.append("duplicate edge")
    dimensions = value.get("dimensions", {})
    for edge in edges:
        required_dimension = EDGE_REQUIRED_DIMENSION.get(edge.get("edge_type"))
        if required_dimension and not dimensions.get(required_dimension):
            errors.append(
                f"edge_type {edge.get('edge_type')} requires dimensions.{required_dimension}=true"
            )
    if agent in by_id:
        adjacency={i:[] for i in ids}
        for e in edges:
            if e.get("from") in adjacency and e.get("to") in by_id: adjacency[e["from"]].append(e["to"])
        seen=set(); q=deque([agent])
        while q:
            n=q.popleft()
            if n in seen: continue
            seen.add(n); q.extend(adjacency.get(n,[]))
        if seen != set(ids): errors.append("every node must be reachable from agent_id")
    expected=compute_action_level(value)
    if value.get("computed_level")!=expected: errors.append(f"computed_level must equal {expected}")
    return errors


def validate_revocation_semantics(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sequence = value.get("sequence_number")
    previous = value.get("previous_list_hash")
    if sequence == 1 and previous is not None:
        errors.append("sequence 1 requires previous_list_hash null")
    if isinstance(sequence, int) and sequence > 1 and previous is None:
        errors.append("sequence greater than 1 requires previous_list_hash")

    entries = value.get("entries", [])
    expected = sorted(entries, key=lambda entry: (entry.get("passport_id"), entry.get("revocation_id")))
    if entries != expected:
        errors.append("entries must be sorted")
    passports = [entry.get("passport_id") for entry in entries]
    if len(passports) != len(set(passports)):
        errors.append("duplicate passport revocation")

    for field in ("issued_at", "next_update"):
        errors.extend(validate_timestamp(value.get(field), field))
    for index, entry in enumerate(entries):
        errors.extend(validate_timestamp(entry.get("revoked_at"), f"entries[{index}].revoked_at"))
        if entry.get("authority") != value.get("issuer_id"):
            errors.append(f"entries[{index}].authority must equal the revocation-list issuer")

    top_time_errors = any(message.startswith(("issued_at:", "next_update:")) for message in errors)
    if not top_time_errors:
        issued_at = parse_time(value["issued_at"])
        next_update = parse_time(value["next_update"])
        if issued_at >= next_update:
            errors.append("issued_at must precede next_update")
        for index, entry in enumerate(entries):
            try:
                revoked_at = parse_time(entry["revoked_at"])
            except (KeyError, ValueError):
                continue
            if revoked_at > issued_at:
                errors.append(f"entries[{index}].revoked_at must not be later than issued_at")
            if revoked_at >= next_update:
                errors.append(f"entries[{index}].revoked_at must precede next_update")
    return errors


def validate_data_authority_semantics(value: dict[str, Any]) -> list[str]:
    errors=[]
    for name,items in value.get("scope",{}).items():
        if isinstance(items,list):
            if items!=sorted(items): errors.append(f"scope.{name} must be sorted")
            if len(items)!=len(set(items)): errors.append(f"scope.{name} contains duplicates")
    validity=value.get("validity",{})
    errors.extend(validate_timestamp(validity.get("not_before"),"validity.not_before"))
    errors.extend(validate_timestamp(validity.get("expires_at"),"validity.expires_at"))
    if not errors and parse_time(validity["not_before"])>=parse_time(validity["expires_at"]): errors.append("data-authority validity interval is empty")
    return errors


def _sorted_unique_strings(values: Any, field: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(values, list):
        return errors
    if values != sorted(values):
        errors.append(f"{field} must be sorted")
    if len(values) != len(set(values)):
        errors.append(f"{field} contains duplicates")
    return errors


def validate_agent_inventory_semantics(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(_sorted_unique_strings(value.get("declared_capabilities"), "declared_capabilities"))
    data_use = value.get("data_use", {})
    if isinstance(data_use, dict):
        for field in ("data_classes", "purposes", "systems", "jurisdictions"):
            errors.extend(_sorted_unique_strings(data_use.get(field), f"data_use.{field}"))
    return errors


def validate_mcp_inventory_semantics(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    servers = value.get("servers", [])
    ids = [item.get("server_id") for item in servers if isinstance(item, dict)]
    if ids != sorted(ids):
        errors.append("servers must be sorted by server_id")
    if len(ids) != len(set(ids)):
        errors.append("duplicate server_id")
    for server in servers:
        if isinstance(server, dict):
            errors.extend(
                _sorted_unique_strings(
                    server.get("declared_scope"),
                    f"server {server.get('server_id')}.declared_scope",
                )
            )
    return errors


def validate_tool_inventory_semantics(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tools = value.get("tools", [])
    ids = [item.get("tool_id") for item in tools if isinstance(item, dict)]
    if ids != sorted(ids):
        errors.append("tools must be sorted by tool_id")
    if len(ids) != len(set(ids)):
        errors.append("duplicate tool_id")
    for tool in tools:
        if isinstance(tool, dict):
            errors.extend(
                _sorted_unique_strings(
                    tool.get("effects"),
                    f"tool {tool.get('tool_id')}.effects",
                )
            )
    return errors


def validate_profile_descriptor_semantics(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(_sorted_unique_strings(value.get("supported_control_ids"), "supported_control_ids"))
    errors.extend(
        _sorted_unique_strings(
            value.get("trusted_data_authority_issuers"),
            "trusted_data_authority_issuers",
        )
    )
    schemes = value.get("supported_data_authority_schemes", [])
    keys = [
        (item.get("scheme"), item.get("scheme_version"))
        for item in schemes
        if isinstance(item, dict)
    ]
    if keys != sorted(keys):
        errors.append("supported_data_authority_schemes must be sorted")
    if len(keys) != len(set(keys)):
        errors.append("duplicate supported data-authority scheme")
    return errors

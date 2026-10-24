#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import base64
import hashlib
import re
from datetime import datetime
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from tools.canonical_json import canonicalize
from tools.semantic_rules import parse_time, validate_protected_header
from tools.strict_json import loads_strict


def b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def b64d(value: str) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("malformed base64url")
    decoded = base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))
    if b64e(decoded) != value:
        raise ValueError("non-canonical base64url")
    return decoded


def jwk_thumbprint_kid(jwk: dict[str, Any]) -> str:
    members = {"crv": jwk.get("crv"), "kty": jwk.get("kty"), "x": jwk.get("x")}
    thumbprint = b64e(hashlib.sha256(canonicalize(members)).digest())
    return "urn:ietf:params:oauth:jwk-thumbprint:sha-256:" + thumbprint


def verify_jws(
    document: dict[str, Any],
    key: dict[str, Any],
    *,
    typ: str,
    cty: str,
) -> list[str]:
    errors: list[str] = []
    try:
        protected_b64, detached_payload, signature_b64 = document["proof"]["jws"].split(".")
        if detached_payload != "":
            raise ValueError("payload segment must be empty")
        protected_bytes = b64d(protected_b64)
        header = loads_strict(protected_bytes, require_object=True)
        if protected_bytes != canonicalize(header):
            errors.append("protected header must use JCS encoding")
        errors.extend(validate_protected_header(header, content_type=cty, type_value=typ))
        if header.get("kid") != key.get("kid"):
            errors.append("protected header kid does not match trusted key")
        payload = {name: value for name, value in document.items() if name != "proof"}
        payload_b64 = b64e(canonicalize(payload))
        public_bytes = b64d(key["jwk"]["x"])
        signature = b64d(signature_b64)
        signing_input = (protected_b64 + "." + payload_b64).encode("ascii")
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, signing_input)
    except Exception as exc:
        errors.append(f"detached JWS verification failed: {exc}")
    return errors


def trusted_key_errors(
    key: dict[str, Any],
    *,
    expected_issuer: str | None,
    at_time: datetime,
) -> list[str]:
    errors: list[str] = []
    if expected_issuer is not None and key.get("issuer_id") != expected_issuer:
        errors.append("trusted key issuer does not match artifact issuer")

    jwk = key.get("jwk", {})
    try:
        public_bytes = b64d(jwk.get("x"))
        if len(public_bytes) != 32:
            raise ValueError("Ed25519 x must decode to exactly 32 bytes")
        Ed25519PublicKey.from_public_bytes(public_bytes)
    except Exception as exc:
        errors.append(f"trusted key JWK x is unusable: {exc}")

    try:
        expected_kid = jwk_thumbprint_kid(jwk)
    except Exception as exc:
        errors.append(f"unable to calculate JWK thumbprint: {exc}")
    else:
        if key.get("kid") != expected_kid:
            errors.append("trusted key kid does not match its RFC 7638 JWK thumbprint")
        if "kid" in jwk and jwk.get("kid") != key.get("kid"):
            errors.append("JWK kid does not match trusted-key kid")

    if jwk.get("alg") != "Ed25519" or key.get("allowed_algorithms") != ["Ed25519"]:
        errors.append("trusted key does not permit Ed25519")
    if jwk.get("use") != "sig" or jwk.get("key_ops") != ["verify"]:
        errors.append("trusted key is not restricted to signature verification")

    status = key.get("status")
    if status == "RETIRED":
        errors.append("RETIRED keys are not accepted by the Alpha.1 reference validator")
    elif status in {"REVOKED", "COMPROMISED", "NOT_YET_VALID", "EXPIRED"}:
        errors.append(f"trusted key status is {status}")
    elif status != "ACTIVE":
        errors.append("trusted key status is not recognized")

    try:
        not_before = parse_time(key.get("not_before"))
        expires_at = parse_time(key.get("expires_at"))
        if at_time < not_before:
            errors.append("trusted key is not yet valid at the evaluation time")
        if at_time >= expires_at:
            errors.append("trusted key is expired at the evaluation time")
        if not_before >= expires_at:
            errors.append("trusted key validity interval is empty")
    except Exception as exc:
        errors.append(f"trusted key validity: {exc}")
    return errors

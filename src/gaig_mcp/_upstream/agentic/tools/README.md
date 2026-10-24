<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Tools

- `validate_artifact.py` performs structural, artifact, and trust validation for external inputs.
- `strict_json.py` provides the shared I-JSON input loader.
- `crypto.py` verifies detached Ed25519 JWS proofs and signing-key trust properties.
- `binding_verification.py` verifies the canonical bundle, profile descriptor, inventories, action-authority graph, data-authority evidence, assessment projection, and cross-artifact references.
- `reference_policy.py` defines the exact Alpha.1 profile, evaluator, policy, and data-authority adapter identifiers accepted by the reference validator.
- `canonical_json.py` implements the restricted RFC 8785 profile used by identifiers and signatures.
- `verify_repository.py` checks schemas, examples, identifiers, signatures, negative fixtures, release hygiene, and the end-user validation path.
- `build_dist.py` regenerates the aggregate specification.
- `public_release_scrub.py` validates the canonical public project identity and optionally scans every tracked UTF-8 text file using a private denylist stored outside the repository. Public output is limited to result, accurate scope, scrub-policy version, bounded limitations, and whether private evidence is retained.

Run `python tools/validate_artifact.py --help` for supported artifact types and trust inputs.

These utilities are interoperability references, not a production policy engine or certification service.

Passport trust validation requires `--bundle-manifest` and `--bundle-root`. The CLI fails closed when required materials are missing, contradictory, unsupported, expired, untrusted, or semantically inconsistent.

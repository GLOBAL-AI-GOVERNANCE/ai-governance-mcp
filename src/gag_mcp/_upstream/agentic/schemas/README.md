<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Schemas

This directory contains versioned JSON Schemas used by Agentic AI Governance.

Existing Alpha.1 schema identifiers and raw-file SHA-256 digests are immutable. New versions may coexist only when listed in `schema-catalog.json` with an explicit immutable identifier, content digest, artifact version, lifecycle status, and supersession relationship.

`schema-catalog.schema.json` is the fixed repository-governance root used to validate the catalog before other catalog entries are loaded. The catalog is repository metadata, not a protocol artifact.

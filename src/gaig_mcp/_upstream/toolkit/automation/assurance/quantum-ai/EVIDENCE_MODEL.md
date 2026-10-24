# Evidence Model

This current-main v0.1 development profile separates four dimensions that must not be collapsed into one maturity label:

| Dimension | Positive-fixture value | Meaning |
|---|---|---|
| Evidence basis | `E1_REPRODUCIBLE_SYNTHETIC_RUN` | Deterministic project-authored synthetic run; E0 is design evidence and E2-E5 remain reserved. |
| Provenance | `PROJECT_GENERATED_FIXTURE` | Project-generated fixture and controls, not vendor, laboratory, policy-body, or real-hardware evidence. |
| Publication status | `PUBLISHED_TOOLKIT_PROFILE` | The Quantum-AI profile family is published in tagged Toolkit releases. This field does not claim that an arbitrary working-tree revision is itself a release. Pin a Toolkit tag for exact implementation identity. |
| Replication status | `DETERMINISTIC_ARTIFACT_REPLAY_VERIFIED` | Tests reproduce identical canonical result bytes from the checked-in fixture. |

These dimensions appear under `details.evidence_dimensions`, which the common Profile Result contract already permits. The common contract and schema version are unchanged. No dimension carries certification, authority, operational-validity, quantum-advantage, or real-hardware semantics.

The run records a seed, synthetic input snapshot, deterministic classical algorithm, quality and measurement boundaries, bounded confidence, stable evidence identifier, and SHA-256 digest of canonical run evidence. The evaluator separately detects a digest mismatch and disagreement between run evidence and evaluated inputs.

## Replay taxonomy

- **Deterministic artifact replay — `VERIFIED`:** the same fixture and fixed evaluation context produce byte-identical canonical `profile-result.json` artifacts.
- **Statistical repeatability — `NOT_ASSESSED`:** repeated sampling and distributional analysis are outside this deterministic fixture.
- **Independent external reproducibility — `NOT_REPORTED`:** no independent organization or external environment is claimed to have reproduced the result.

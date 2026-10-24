# Requirements Traceability

The Quantum-AI profile family is published in tagged Toolkit releases. Status here describes the current source. Pin a Toolkit tag for exact implementation identity. Independent external reproducibility remains `NOT_REPORTED`.

| ID | Source concern / location | Requirement origin | Design response | Verification method | Acceptance evidence | Status |
|---|---|---|---|---|---|---|
| QAI-01 | Deterministic scope; `SCOPE.md`, `NON_GOALS.md` | Frozen v0.1 synthetic/emulated boundary | Seed, pinned classical algorithm, fixture-only thresholds, prohibited-claim scanner | Positive replay and claim mutations | Byte-identical result; `UNSUPPORTED_CLAIM_*` | Implemented |
| QAI-02 | Measurement integrity; threat model | Missing/malformed measurements | Validate list, ids, finite values, declared missing count | Remove list; corrupt value/count | Three measurement findings | Implemented |
| QAI-03 | Bias; threat model | Constant and step bias | Residual checks against fixture `bias_limit` | Constant and split-step mutations | `CONSTANT_BIAS`, `STEP_BIAS` | Implemented |
| QAI-04 | Quality; threat model | Saturation and clock drift | Require false saturation and finite zero drift | Toggle each field | `SATURATION`, `CLOCK_DRIFT` | Implemented |
| QAI-05 | Reference integrity; threat model | Corrupted map | Require finite values and unique non-empty labels | Malform value; duplicate label | `CORRUPTED_REFERENCE_MAP` | Implemented |
| QAI-06 | Baseline identity; `SCOPE.md` | Algorithm substitution | Pin `classical-nearest-map-value-v1` | Replace identifier | `ALGORITHM_SUBSTITUTION` | Implemented |
| QAI-07 | Calibration/confidence; threat model | Stale calibration; false high confidence | Fixture calibration and bounded fixture-only confidence | Mark stale; declare high | Two stable findings | Implemented |
| QAI-08 | Integrity; `EVIDENCE_MODEL.md` | Digest mismatch; evidence tampering | Digest run evidence; compare snapshot to input | Corrupt digest; alter snapshot and re-digest | Two integrity findings | Implemented |
| QAI-09 | Claim containment; `NON_GOALS.md` | No unsupported claim classes | Bounded deterministic phrase patterns | One mutation per class | Corresponding `UNSUPPORTED_CLAIM_*` | Implemented |
| QAI-10 | Human authority; review protocol | Human boundary; non-authorizing handoff | Require review, no autonomous action, `authority_effect: NONE` | Remove/change declarations | Two authority findings | Implemented |
| QAI-11 | Fallback; threat model | Fallback available when required | Require fixture fallback available | Set false | `FALLBACK_UNAVAILABLE` | Implemented |
| QAI-12 | Semantics; evidence/source models | Separate basis, provenance, publication, replication | Four fields in contract-permitted `details` | Contract and exact assertions | Four distinct dimensions | Implemented |
| QAI-13 | Replay; evidence model | Distinguish three replay concepts | `VERIFIED`, `NOT_ASSESSED`, `NOT_REPORTED` taxonomy | Exact assertions | No external reproduction claim | Implemented |
| QAI-14 | Common contract/browser boundary | No breaking result change or competing evaluator | Existing profile remains evaluator; browser remains reader; schema `1.0.0` | Full validation and parity tests | `authority_effect: NONE`; `certification_semantics: NONE` | Implemented |

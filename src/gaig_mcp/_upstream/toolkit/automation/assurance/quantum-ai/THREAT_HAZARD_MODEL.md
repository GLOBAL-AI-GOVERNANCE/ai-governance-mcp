# Threat and Hazard Model

Design Gate 0 is a frozen synthetic/emulated assurance exercise. The following fail-closed conditions are machine-enforced by deterministic mutations in `automation/tests/test_profiles.py`; they demonstrate record and control behavior, not mitigation effectiveness in an operational system.

| Hazard | Stable finding |
|---|---|
| Missing or malformed measurements | `MISSING_MEASUREMENTS`, `MALFORMED_MEASUREMENT`, `MISSING_MEASUREMENT_DECLARED` |
| Constant or step bias | `CONSTANT_BIAS`, `STEP_BIAS` |
| Saturation or clock drift | `SATURATION`, `CLOCK_DRIFT` |
| Corrupted reference map | `CORRUPTED_REFERENCE_MAP` |
| Algorithm substitution | `ALGORITHM_SUBSTITUTION` |
| Stale calibration | `STALE_CALIBRATION` |
| False high confidence | `FALSE_HIGH_CONFIDENCE` |
| Evidence-digest mismatch or run-evidence tampering | `EVIDENCE_DIGEST_MISMATCH`, `RUN_EVIDENCE_TAMPERING` |
| Unsupported operational, autonomous, counter-detection, certification, real-hardware, or quantum-advantage claim | `UNSUPPORTED_CLAIM_*` |
| Missing human boundary or authority-changing handoff | `MISSING_HUMAN_BOUNDARY`, `AUTHORITY_CHANGING_HANDOFF` |
| Required fallback unavailable | `FALLBACK_UNAVAILABLE` |

Passing these gates does not authorize action, certify a system, establish an operational threshold, support counter-detection, demonstrate quantum advantage, or provide evidence about real hardware.

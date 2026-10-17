# gag-mcp verification transcript

Generated 2026-10-16 21:49 PDT on the Grok Bot box. Real MCP client (official Python SDK `mcp` 2.3.0) calling the local server. Results are excerpted.

## Transport: stdio (subprocess)

`tools/list` →
```json
[
  {
    "name": "check_inventory",
    "annotations": {
      "title": "Check AI inventory for governance gaps",
      "readOnlyHint": true,
      "destructiveHint": false,
      "idempotentHint": true,
      "openWorldHint": false
    }
  },
  {
    "name": "build_decision_pack",
    "annotations": {
      "title": "Prepare a Decision Pack for human review",
      "readOnlyHint": true,
      "destructiveHint": false,
      "idempotentHint": true,
      "openWorldHint": false
    }
  },
  {
    "name": "validate_passport",
    "annotations": {
      "title": "Verify an Agent Trust Passport",
      "readOnlyHint": true,
      "destructiveHint": false,
      "idempotentHint": true,
      "openWorldHint": false
    }
  }
]
```

`tools/call check_inventory {"use_sample": true, "evaluation_time": "2026-10-16T00:00:00Z"}` → OK
```json
{
  "authority_effect": "NONE",
  "human_decision_state": "PENDING_HUMAN_DECISION",
  "source": {
    "repository": "GLOBAL-AI-GOVERNANCE/global-ai-governance-toolkit",
    "commit": "cf906ef"
  },
  "result_excerpt": {
    "validation_state": "VALID",
    "governance_gate_state": "BLOCKED",
    "finding_count": 5,
    "findings_by_severity": {
      "CRITICAL": 2,
      "HIGH": 3
    },
    "first_finding": {
      "finding_id": "sha256:2c4734bd1421567bab678ca803b9d4aeb200240b545f87aefc15deb642051746",
      "message": "Missing named owner. No owner, no deployment.",
      "rule_id": "GAI-AUTO-001",
      "severity": "CRITICAL",
      "system_id": "AI-004",
      "system_name": "Frontier Operations Agent"
    }
  }
}
```

`tools/call build_decision_pack {"use_sample": true, "evaluation_time": "2026-10-16T00:00:00Z"}` → OK
```json
{
  "authority_effect": "NONE",
  "human_decision_state": "PENDING_HUMAN_DECISION",
  "source": {
    "repository": "GLOBAL-AI-GOVERNANCE/global-ai-governance-toolkit",
    "commit": "cf906ef"
  },
  "result_excerpt": {
    "decision_status": "pending_human_decision",
    "integrity_check": "VERIFIED",
    "generated_files": [
      "action-plan.md",
      "decision-record.md",
      "evidence-and-ownership.md",
      "executive-summary.md",
      "risk-and-findings.md",
      "system-profile.md"
    ],
    "handoff_authority_effect": "NONE"
  }
}
```

`tools/call validate_passport {"example": "signed-unrevoked"}` → OK
```json
{
  "authority_effect": "NONE",
  "human_decision_state": "PENDING_HUMAN_DECISION",
  "source": {
    "repository": "GLOBAL-AI-GOVERNANCE/agentic-ai-governance",
    "commit": "2124aea",
    "maturity": "experimental public alpha (v0.1.0-alpha.2 line; main may be ahead)"
  },
  "result_excerpt": {
    "verification_primary_status": "VALID",
    "reference_policy_disposition": "PERMITTED",
    "assessment_result_recorded_in_artifact": "APPROVED",
    "fully_validated": true
  }
}
```

`tools/call validate_passport {"example": "signed-revoked"}` → OK
```json
{
  "authority_effect": "NONE",
  "human_decision_state": "PENDING_HUMAN_DECISION",
  "source": {
    "repository": "GLOBAL-AI-GOVERNANCE/agentic-ai-governance",
    "commit": "2124aea",
    "maturity": "experimental public alpha (v0.1.0-alpha.2 line; main may be ahead)"
  },
  "result_excerpt": {
    "verification_primary_status": "REVOKED",
    "reference_policy_disposition": "NOT_PERMITTED",
    "assessment_result_recorded_in_artifact": "APPROVED",
    "fully_validated": false
  }
}
```

`tools/call check_inventory` with a malformed CSV → isError=True (expected True: fail closed)
> Error executing tool check_inventory: Inventory rejected by toolkit validation: {"error": {"code": "MISSING_REQUIRED_COLUMN", "expected": ["owner", "business_unit", "vendor_internal", "use_case", "data_sensitivity", "impact_people", "impact_money", "impact_security", "impact_rights", "impact_safety"

`GET /health` → `{'status': 'ok', 'server': 'gag-mcp', 'version': '0.1.0', 'authority_effect': 'NONE'}`

## Transport: Streamable HTTP (http://127.0.0.1:55627/mcp)

`tools/list` →
```json
[
  {
    "name": "check_inventory",
    "annotations": {
      "title": "Check AI inventory for governance gaps",
      "readOnlyHint": true,
      "destructiveHint": false,
      "idempotentHint": true,
      "openWorldHint": false
    }
  },
  {
    "name": "build_decision_pack",
    "annotations": {
      "title": "Prepare a Decision Pack for human review",
      "readOnlyHint": true,
      "destructiveHint": false,
      "idempotentHint": true,
      "openWorldHint": false
    }
  },
  {
    "name": "validate_passport",
    "annotations": {
      "title": "Verify an Agent Trust Passport",
      "readOnlyHint": true,
      "destructiveHint": false,
      "idempotentHint": true,
      "openWorldHint": false
    }
  }
]
```

`tools/call check_inventory {"use_sample": true, "evaluation_time": "2026-10-16T00:00:00Z"}` → OK
```json
{
  "authority_effect": "NONE",
  "human_decision_state": "PENDING_HUMAN_DECISION",
  "source": {
    "repository": "GLOBAL-AI-GOVERNANCE/global-ai-governance-toolkit",
    "commit": "cf906ef"
  },
  "result_excerpt": {
    "validation_state": "VALID",
    "governance_gate_state": "BLOCKED",
    "finding_count": 5,
    "findings_by_severity": {
      "CRITICAL": 2,
      "HIGH": 3
    },
    "first_finding": {
      "finding_id": "sha256:2c4734bd1421567bab678ca803b9d4aeb200240b545f87aefc15deb642051746",
      "message": "Missing named owner. No owner, no deployment.",
      "rule_id": "GAI-AUTO-001",
      "severity": "CRITICAL",
      "system_id": "AI-004",
      "system_name": "Frontier Operations Agent"
    }
  }
}
```

`tools/call build_decision_pack {"use_sample": true, "evaluation_time": "2026-10-16T00:00:00Z"}` → OK
```json
{
  "authority_effect": "NONE",
  "human_decision_state": "PENDING_HUMAN_DECISION",
  "source": {
    "repository": "GLOBAL-AI-GOVERNANCE/global-ai-governance-toolkit",
    "commit": "cf906ef"
  },
  "result_excerpt": {
    "decision_status": "pending_human_decision",
    "integrity_check": "VERIFIED",
    "generated_files": [
      "action-plan.md",
      "decision-record.md",
      "evidence-and-ownership.md",
      "executive-summary.md",
      "risk-and-findings.md",
      "system-profile.md"
    ],
    "handoff_authority_effect": "NONE"
  }
}
```

`tools/call validate_passport {"example": "signed-unrevoked"}` → OK
```json
{
  "authority_effect": "NONE",
  "human_decision_state": "PENDING_HUMAN_DECISION",
  "source": {
    "repository": "GLOBAL-AI-GOVERNANCE/agentic-ai-governance",
    "commit": "2124aea",
    "maturity": "experimental public alpha (v0.1.0-alpha.2 line; main may be ahead)"
  },
  "result_excerpt": {
    "verification_primary_status": "VALID",
    "reference_policy_disposition": "PERMITTED",
    "assessment_result_recorded_in_artifact": "APPROVED",
    "fully_validated": true
  }
}
```

`tools/call validate_passport {"example": "signed-revoked"}` → OK
```json
{
  "authority_effect": "NONE",
  "human_decision_state": "PENDING_HUMAN_DECISION",
  "source": {
    "repository": "GLOBAL-AI-GOVERNANCE/agentic-ai-governance",
    "commit": "2124aea",
    "maturity": "experimental public alpha (v0.1.0-alpha.2 line; main may be ahead)"
  },
  "result_excerpt": {
    "verification_primary_status": "REVOKED",
    "reference_policy_disposition": "NOT_PERMITTED",
    "assessment_result_recorded_in_artifact": "APPROVED",
    "fully_validated": false
  }
}
```

`tools/call check_inventory` with a malformed CSV → isError=True (expected True: fail closed)
> Error executing tool check_inventory: Inventory rejected by toolkit validation: {"error": {"code": "MISSING_REQUIRED_COLUMN", "expected": ["owner", "business_unit", "vendor_internal", "use_case", "data_sensitivity", "impact_people", "impact_money", "impact_security", "impact_rights", "impact_safety"

## Raw HTTP: handshake-era client (protocol 2025-11-25), as older hosted clients may send

- initialize → protocolVersion `2025-11-25`, server `gag-mcp`
- tools/call validate_passport → authority_effect `NONE`, status `REVOKED`

**Result:** PASS

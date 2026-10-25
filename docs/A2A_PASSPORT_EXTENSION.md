# Agent Trust Passport reference for A2A Agent Cards

Extension URI: `https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/main/docs/A2A_PASSPORT_EXTENSION.md`

An [A2A](https://a2a-protocol.org/) agent publishes an Agent Card at `/.well-known/agent-card.json`. This extension adds one entry to `capabilities.extensions` so a delegating agent can find the remote agent's Agent Trust Passport before it sends a task.

```json
{
  "uri": "https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/main/docs/A2A_PASSPORT_EXTENSION.md",
  "description": "Agent Trust Passport: verify before delegating; a verified passport is not an authorization.",
  "required": false,
  "params": {
    "passportUrl": "https://agents.example.com/research/passport.json",
    "trustedKeyUrl": "https://agents.example.com/keys/passport-signing.pub.pem",
    "revocationListUrl": "https://agents.example.com/revocations.json",
    "maxActionLevel": 3,
    "authorityEffect": "NONE"
  }
}
```

| Param | Meaning |
|---|---|
| `passportUrl` | The signed Agent Trust Passport for this agent |
| `trustedKeyUrl` | Public key the delegating agent should trust for that passport (pin it; do not trust a key only because the card names it) |
| `revocationListUrl` | Signed revocation list to check at delegation time |
| `maxActionLevel` | Highest Action Level (0-5) the passport claims; a delegator denies skills above it |
| `authorityEffect` | Always `NONE`: the pointer and the passport are preconditions, not authorizations |

## Before delegating

1. Fetch the card and read this extension. No extension: treat the remote agent like an unknown tool (Level 4, ask or route to the operator's approver).
2. Verify the passport with the pinned key and the revocation list at the current time, for example with the `gaig-mcp` `validate_passport` tool, or `gaig_mcp.core.check_tool_call` in Python.
3. Map the skill to an Action Level with your policy. Level 0-3 run unattended, Level 4 asks (or goes to the operator's automated approver if listed), Level 5 is denied.

Reference code: [`examples/agent-stacks/a2a_passport_card.py`](../examples/agent-stacks/a2a_passport_card.py). Status: TESTED for card shape with `a2a-sdk` 1.2.3; no A2A server or client was run.

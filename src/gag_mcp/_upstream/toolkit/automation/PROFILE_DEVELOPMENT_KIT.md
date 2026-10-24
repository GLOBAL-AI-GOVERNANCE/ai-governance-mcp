# Profile Development Kit

Run `python -B automation/scripts/scaffold_profile.py example-profile PATH` to create a deterministic development skeleton. It includes an input schema, evaluator stub, positive and negative fixtures, common Profile Result binding, claims boundaries, browser rendering hook, and CI/test hook.

The output is intentionally `NOT_REGISTERED`. Generation does not edit `automation/profiles/registry.json`, `automation/scripts/run_profile.py`, Contract v1, browser runtime, or CI. A generated profile therefore cannot run through `gag profile` until maintainers separately review its claims, evaluator, schema, fixtures, registry entry, runtime allow-list entry, and tests. The scaffold never authorizes anything and fixes `authority_effect` to `NONE`.

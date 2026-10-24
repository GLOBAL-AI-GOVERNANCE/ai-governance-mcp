import pytest

from gaig_mcp import core
from conftest import EVAL_TIME, assert_non_authorizing


def test_check_inventory_sample_has_findings():
    out = core.check_inventory(use_sample=True, evaluation_time=EVAL_TIME)
    assert_non_authorizing(out)
    r = out["result"]
    assert r["validation_state"] == "VALID"
    assert r["finding_count"] == len(r["findings"]) > 0
    assert r["findings_by_severity"].get("CRITICAL", 0) >= 1
    assert r["evaluation_time"] == EVAL_TIME


def test_check_inventory_caller_csv_flags_gaps(gap_csv):
    out = core.check_inventory(inventory_csv=gap_csv, evaluation_time=EVAL_TIME)
    assert_non_authorizing(out)
    rules = {f["rule_id"] for f in out["result"]["findings"]}
    assert "GAI-AUTO-001" in rules  # missing owner
    assert "GAI-AUTO-003" in rules  # missing shutdown path
    assert out["result"]["input"] == "caller-supplied CSV"


def test_check_inventory_is_reproducible(gap_csv):
    a = core.check_inventory(inventory_csv=gap_csv, evaluation_time=EVAL_TIME)
    b = core.check_inventory(inventory_csv=gap_csv, evaluation_time=EVAL_TIME)
    assert a["result"] == b["result"]


def test_check_inventory_rejects_bad_csv():
    with pytest.raises(core.GaigInputError):
        core.check_inventory(inventory_csv="system_id,system_name\nX,Y\n")


def test_check_inventory_requires_input():
    with pytest.raises(core.GaigInputError):
        core.check_inventory()
    with pytest.raises(core.GaigInputError):
        core.check_inventory(inventory_csv="a,b\n", use_sample=True)


def test_check_inventory_size_cap():
    with pytest.raises(core.GaigInputError):
        core.check_inventory(inventory_csv="x" * (core.MAX_INPUT_BYTES + 1))


def test_build_decision_pack_verified_and_digest_listed():
    out = core.build_decision_pack(use_sample=True, evaluation_time=EVAL_TIME, include_documents=True)
    assert_non_authorizing(out)
    r = out["result"]
    assert r["integrity_check"] == "VERIFIED"
    assert r["decision_status"] == "pending_human_decision"
    files = r["manifest"]["generated_files"]
    assert files and all(len(f["sha256"]) == 64 for f in files)
    assert "decision-record.md" in r["documents"]
    assert r["handoff"]["authority_effect"] == "NONE"


def test_build_decision_pack_deterministic():
    a = core.build_decision_pack(use_sample=True, evaluation_time=EVAL_TIME)
    b = core.build_decision_pack(use_sample=True, evaluation_time=EVAL_TIME)
    assert a["result"]["manifest"] == b["result"]["manifest"]


def test_validate_passport_unrevoked_example():
    out = core.validate_passport(example="signed-unrevoked")
    assert_non_authorizing(out)
    v = out["result"]["verification"]
    assert v["verification_primary_status"] == "VALID"
    assert v["reference_policy_disposition"] == "PERMITTED"
    assert "operating_disposition" not in v


def test_validate_passport_revoked_example():
    out = core.validate_passport(example="signed-revoked")
    assert_non_authorizing(out)
    v = out["result"]["verification"]
    assert v["verification_primary_status"] == "REVOKED"
    assert v["reference_policy_disposition"] == "NOT_PERMITTED"


def test_validate_passport_caller_supplied_tampered_fails_closed():
    import json
    root = core.agentic_root()
    passport = json.loads((root / core.PASSPORT_EXAMPLES["signed-unrevoked"]).read_text())
    key = (root / core.EXAMPLE_KEY).read_text()
    passport["agent"] = {"tampered": True} if "agent" in passport else passport.get("agent")
    passport["_tamper"] = "x"
    out = core.validate_passport(passport=json.dumps(passport), trusted_key=key, at_time=core.EXAMPLE_AT_TIME)
    assert_non_authorizing(out)
    v = out["result"]["verification"]
    assert v["valid"] is False
    assert v.get("reference_policy_disposition") != "PERMITTED"


def test_validate_passport_input_errors():
    with pytest.raises(core.GaigInputError):
        core.validate_passport()
    with pytest.raises(core.GaigInputError):
        core.validate_passport(example="nope")
    with pytest.raises(core.GaigInputError):
        core.validate_passport(passport="{not json", trusted_key="{}")

import json
import pytest

EVAL_TIME = "2026-10-16T00:00:00Z"

GAP_CSV = (
    "system_id,system_name,owner,business_unit,vendor_internal,use_case,data_sensitivity,impact_people,"
    "impact_money,impact_security,impact_rights,impact_safety,autonomy_level,public_facing,monitoring_active,"
    "shutdown_path_exists,evidence_complete\n"
    "LAB-1,Agent Tool Router,,Platform,Internal,Routes agent tool calls,Regulated,Yes,No,Yes,No,Yes,Full,No,No,No,No\n"
)

FORBIDDEN_KEYS = {"authorized", "authorization", "approved", "approval", "decision", "operating_disposition",
                  "issued_assessment_result"}


def walk(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path + (k,), k, v
            yield from walk(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, path + (i,))


def assert_non_authorizing(out: dict):
    assert out["authority_effect"] == "NONE"
    assert "do not approve" in out["review_boundary"]
    assert out["human_decision_state"] == "PENDING_HUMAN_DECISION"
    text = json.dumps(out)
    assert "conditionally_authorized" not in text
    for path, key, value in walk(out):
        assert str(key).lower() not in FORBIDDEN_KEYS, f"authorization-like key at {path}"
        if key == "authority_effect":
            assert value == "NONE", f"non-NONE authority_effect at {path}"
        if value == "PERMITTED":
            assert key == "reference_policy_disposition", f"PERMITTED outside relabeled field at {path}"


@pytest.fixture
def gap_csv():
    return GAP_CSV

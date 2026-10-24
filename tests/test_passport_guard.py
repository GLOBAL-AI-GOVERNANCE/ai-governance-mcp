"""Combined pre-call guard: passport validity, revocation, and reachable Action Level at the server clock."""
import inspect
import json
import pathlib
import subprocess
import sys

import pytest

from gaig_mcp import core
from conftest import assert_non_authorizing

ROOT = pathlib.Path(__file__).parents[1]
STACKS = ROOT / "examples" / "agent-stacks"
sys.path.insert(0, str(STACKS))

import passport_tool_call_hook as hook  # noqa: E402

INSIDE_WINDOW = core.EXAMPLE_AT_TIME  # within the synthetic passports' validity and the list's freshness


@pytest.fixture
def clock(monkeypatch):
    def set_clock(value):
        monkeypatch.setattr(core, "server_clock", lambda: value)
    return set_clock


def _agentic(rel):
    return (core.agentic_root() / rel).read_text(encoding="utf-8")


def _caller_inputs():
    return {"passport": _agentic(core.PASSPORT_EXAMPLES["signed-unrevoked"]),
            "trusted_key": _agentic(core.EXAMPLE_KEY),
            "revocation_list": _agentic(core.EXAMPLE_REVOCATION)}


def _bundle():
    root = core.agentic_root()
    return {"bundle_manifest": root / core.EXAMPLE_BUNDLE, "bundle_root": root}


def test_no_caller_time_input():
    params = inspect.signature(core.check_tool_call).parameters
    assert "at_time" not in params and "evaluation_time" not in params


def test_valid_unrevoked_passport_allows_level_within_ceiling(clock):
    clock(INSIDE_WINDOW)
    out = core.check_tool_call("read_ticket", example="signed-unrevoked", tool_level=1)
    assert_non_authorizing(out)
    r = out["result"]
    assert r["call_disposition"] == "allow"
    assert r["passport_action_ceiling"] == 2
    assert r["evaluated_at"] == INSIDE_WINDOW and r["time_basis"] == "server_clock"
    assert r["passport_check"]["verification_primary_status"] == "VALID"
    assert r["passport_check"]["revocation"] == "PASS"


def test_level_above_passport_ceiling_is_denied(clock):
    clock(INSIDE_WINDOW)
    r = core.check_tool_call("update_record", example="signed-unrevoked", tool_level=3)["result"]
    assert r["call_disposition"] == "deny"
    assert any("above the passport's reachable Action Level 2" in x for x in r["reasons"])


def test_unknown_tool_level_defaults_to_4_and_is_denied_above_ceiling(clock):
    clock(INSIDE_WINDOW)
    r = core.check_tool_call("brand_new_tool", example="signed-unrevoked")["result"]
    assert (r["tool_level"], r["tool_level_source"], r["call_disposition"]) == (4, "unknown-tool default", "deny")


def test_revoked_passport_is_denied(clock):
    clock(INSIDE_WINDOW)
    r = core.check_tool_call("read_ticket", example="signed-revoked", tool_level=1)["result"]
    assert r["call_disposition"] == "deny"
    assert r["passport_check"]["verification_primary_status"] != "VALID"


def test_real_server_clock_is_used_and_expired_passport_is_denied():
    out = core.check_tool_call("read_ticket", example="signed-unrevoked", tool_level=1)
    r = out["result"]
    assert r["evaluated_at"] != INSIDE_WINDOW
    assert r["evaluated_at"] == r["passport_check"]["evaluated_at"]
    assert r["call_disposition"] == "deny"  # synthetic passport expired 2026-08-17


def test_caller_passport_with_bundle_allows(clock):
    clock(INSIDE_WINDOW)
    r = core.check_tool_call("read_ticket", tool_level=0, **_caller_inputs(), **_bundle())["result"]
    assert r["call_disposition"] == "allow", r["reasons"]


def test_caller_passport_without_bundle_is_denied(clock):
    clock(INSIDE_WINDOW)
    r = core.check_tool_call("read_ticket", tool_level=0, **_caller_inputs())["result"]
    assert r["call_disposition"] == "deny"
    assert "BOUND_INPUTS_UNAVAILABLE" in r["passport_check"]["errors"]


def test_missing_revocation_list_is_denied(clock):
    clock(INSIDE_WINDOW)
    inputs = _caller_inputs()
    inputs.pop("revocation_list")
    r = core.check_tool_call("read_ticket", tool_level=0, **inputs, **_bundle())["result"]
    assert r["call_disposition"] == "deny"
    assert any("revocation" in x for x in r["reasons"])


def test_stale_revocation_list_is_denied(clock):
    clock("2026-07-20T12:00:00Z")  # passport still in window; list next_update 2026-07-19 has passed
    r = core.check_tool_call("read_ticket", example="signed-unrevoked", tool_level=1)["result"]
    assert r["call_disposition"] == "deny"


def _fake_valid(monkeypatch, at):
    raw = {"verification_primary_status": "VALID", "evaluated_at": at,
           "checks": {"validity": "PASS", "revocation": "PASS"}, "errors": []}
    monkeypatch.setattr(core, "_run_passport_validator", lambda *a, **k: (raw, 0, "test"))


@pytest.mark.parametrize("level,expected", [(3, "allow"), (4, "ask"), (5, "deny")])
def test_level_mapping_after_checks_pass(monkeypatch, clock, level, expected):
    clock(INSIDE_WINDOW)
    _fake_valid(monkeypatch, INSIDE_WINDOW)
    passport = {"issued_assessment": {"maximum_action_level": 5}}
    r = core.check_tool_call("t", passport=passport, trusted_key={}, revocation_list={}, tool_level=level)["result"]
    assert r["call_disposition"] == expected


def test_validator_time_mismatch_is_denied(monkeypatch, clock):
    clock(INSIDE_WINDOW)
    _fake_valid(monkeypatch, "2020-01-01T00:00:00Z")
    passport = {"issued_assessment": {"maximum_action_level": 5}}
    r = core.check_tool_call("t", passport=passport, trusted_key={}, revocation_list={}, tool_level=1)["result"]
    assert r["call_disposition"] == "deny"


def test_temporary_restriction_lowers_ceiling():
    passport = {"issued_assessment": {"maximum_action_level": 4},
                "conditions": [{"temporary_restriction": {"maximum_action_level": 1}}, {}]}
    assert core.passport_action_ceiling(passport) == 1
    assert core.passport_action_ceiling({"issued_assessment": {}}) is None
    assert core.passport_action_ceiling({"issued_assessment": {"maximum_action_level": True}}) is None


@pytest.mark.parametrize("bad", [6, -1, True, "2", 1.5])
def test_invalid_tool_level_rejected(bad):
    with pytest.raises(core.GaigInputError):
        core.check_tool_call("t", example="signed-unrevoked", tool_level=bad)


def test_input_errors():
    with pytest.raises(core.GaigInputError):
        core.check_tool_call("")
    with pytest.raises(core.GaigInputError):
        core.check_tool_call("t")
    with pytest.raises(core.GaigInputError):
        core.check_tool_call("t", example="nope")


def test_validate_passport_reports_time_basis():
    assert core.validate_passport(example="signed-unrevoked")["result"]["time_basis"].startswith("example_fixed_time")
    hist = core.validate_passport(example="signed-unrevoked", at_time="2026-07-18T12:00:00Z")["result"]
    assert hist["time_basis"].startswith("caller_at_time")
    inputs = _caller_inputs()
    assert core.validate_passport(**inputs)["result"]["time_basis"] == "server_clock"
    assert core.validate_passport(**inputs, at_time=INSIDE_WINDOW)["result"]["time_basis"].startswith("caller_at_time")


def _write_inputs(tmp_path):
    paths = {}
    for key, flag in (("passport", "--passport"), ("trusted_key", "--trusted-key"),
                      ("revocation_list", "--revocation-list")):
        p = tmp_path / f"{key}.json"
        p.write_text(_caller_inputs()[key])
        paths[flag] = str(p)
    b = _bundle()
    paths["--bundle-manifest"], paths["--bundle-root"] = str(b["bundle_manifest"]), str(b["bundle_root"])
    return paths


def test_hook_contracts_in_window(tmp_path, clock):
    clock(INSIDE_WINDOW)
    levels = tmp_path / "levels.json"
    levels.write_text(json.dumps({"read_ticket": 1, "send_external_email": 4}))
    opts = {**_write_inputs(tmp_path), "--policy": str(levels)}
    assert hook.decide({"tool_name": "mcp__crm__read_ticket"}, opts) == ({}, 0)
    out, code = hook.decide({"tool_name": "mcp__crm__send_external_email"}, opts)
    assert code == 0 and out["hookSpecificOutput"]["permissionDecision"] == "deny"  # above passport ceiling 2
    out, code = hook.decide({"toolName": "crm__send_external_email"}, opts)
    assert code == 2 and out["decision"] == "deny"


def _run_hook(event, *args):
    return subprocess.run([sys.executable, str(STACKS / "passport_tool_call_hook.py"), *args],
                          input=json.dumps(event), capture_output=True, text=True, timeout=60)


def test_hook_process_denies_expired_passport_at_real_clock(tmp_path):
    args = [x for kv in _write_inputs(tmp_path).items() for x in kv]
    proc = _run_hook({"toolName": "gaig__check_inventory"}, *args)
    assert proc.returncode == 2 and json.loads(proc.stdout)["decision"] == "deny"


def test_hook_process_fails_closed_without_inputs():
    proc = _run_hook({"tool_name": "mcp__gaig__check_inventory"})
    out = json.loads(proc.stdout)
    assert proc.returncode == 2 and out["hookSpecificOutput"]["permissionDecision"] == "deny"

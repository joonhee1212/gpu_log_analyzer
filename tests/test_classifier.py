"""
Classifier tests — verifies enrichment fields, fallback behavior, and
end-to-end parse→classify on both synthetic fixtures and real samples.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gpu_log_analyzer.classifier import classify_incidents, load_xid_reference
from gpu_log_analyzer.generator import _KITCHEN_SINK_XIDS
from gpu_log_analyzer.models import Incident, XidEvent
from gpu_log_analyzer.parser import parse_file

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "real"

_VALID_SEVERITIES = {"low", "medium", "high", "critical", "unknown"}
_VALID_ACTIONS = {
    "INVESTIGATE_SOFTWARE", "MONITOR", "IGNORE", "RESET_GPU", "RMA_HARDWARE",
    "RESTART_APP", "RESTART_VM", "CHECK_HARDWARE", "CHECK_MECHANICALS",
    "CHECK_FABRIC", "CHECK_RECOVERY_ACTION", "CHECK_UVM",
    "UPDATE_SWFW", "MANUAL_LOOKUP",
}


@pytest.fixture(scope="module")
def ref():
    return load_xid_reference()


# --- reference table tests ---

def test_reference_loads(ref):
    assert len(ref) >= 67   # 67 real codes + fallback; will only grow


def test_all_codes_have_required_fields(ref):
    required = {"name", "category", "severity", "likely_cause", "action", "notes"}
    from gpu_log_analyzer.models import XidInfo
    for code, info in ref.items():
        for field in required:
            assert getattr(info, field, None) is not None, f"Xid {code} missing {field}"


def test_all_severities_are_valid(ref):
    for code, info in ref.items():
        assert info.severity in _VALID_SEVERITIES, f"Xid {code}: unexpected severity {info.severity!r}"


def test_all_actions_are_valid(ref):
    for code, info in ref.items():
        assert info.action in _VALID_ACTIONS, f"Xid {code}: unexpected action {info.action!r}"


# --- unknown Xid fallback ---

def test_unknown_xid_falls_back_to_entry_0(ref):
    dummy = Incident(
        pci_addr="0000:ff:00",
        gpu_uuid=None,
        events=[XidEvent(xid=9999, pci_addr="0000:ff:00", timestamp="", pid=None, process_name=None, detail="")],
        source_file="test",
    )
    [ci] = classify_incidents([dummy], ref)
    info = ci.classified_events[0].info
    assert info.category == "unknown_uncategorized"
    assert info.action == "MANUAL_LOOKUP"


# --- classify all single-code fixtures ---

def test_all_fixtures_classify_non_fallback(ref):
    """Every xid_NNN.log should classify to the correct non-fallback entry."""
    real_codes = sorted(k for k in ref if k != 0)
    for xid in real_codes:
        path = FIXTURE_DIR / f"xid_{xid:03d}.log"
        incidents = parse_file(path)
        classified = classify_incidents(incidents, ref)
        first_ce = classified[0].classified_events[0]
        assert first_ce.info.category != "unknown_uncategorized", (
            f"Xid {xid} classified as unknown — missing from reference?"
        )
        assert first_ce.event.xid == xid


# --- spot-check specific category/action mappings ---

@pytest.mark.parametrize("xid,expected_category,expected_action", [
    (79,  "gpu_fallen_off_bus",   "RESET_GPU"),
    (48,  "memory_ecc",           "RESET_GPU"),
    (31,  "illegal_memory_access","RESTART_APP"),
    (119, "gsp_firmware_error",   "RESET_GPU"),
    (74,  "nvlink_nvswitch",      "CHECK_FABRIC"),
    (64,  "memory_ecc",           "RMA_HARDWARE"),
    (54,  "thermal_power",        "CHECK_MECHANICALS"),
    (45,  "driver_software",      "IGNORE"),
])
def test_specific_xid_category_and_action(xid, expected_category, expected_action, ref):
    path = FIXTURE_DIR / f"xid_{xid:03d}.log"
    incidents = parse_file(path)
    [ci] = classify_incidents(incidents, ref)
    info = ci.classified_events[0].info
    assert info.category == expected_category
    assert info.action == expected_action


# --- kitchen sink end-to-end ---

def test_kitchen_sink_classified(ref):
    incidents = parse_file(FIXTURE_DIR / "kitchen_sink.log")
    classified = classify_incidents(incidents, ref)
    assert len(classified) >= len(_KITCHEN_SINK_XIDS)
    for ci in classified:
        for ce in ci.classified_events:
            assert ce.info.severity in _VALID_SEVERITIES
            assert ce.info.action in _VALID_ACTIONS


# --- real samples end-to-end ---

def test_real_samples_classified_correctly(ref):
    incidents = []
    for name in ["incident1_first_occurrence.log", "incident2_recurrence.log"]:
        incidents.extend(parse_file(SAMPLES_DIR / name))
    classified = classify_incidents(incidents, ref)

    all_xids_and_cats = [
        (ce.event.xid, ce.info.category)
        for ci in classified
        for ce in ci.classified_events
    ]
    assert ("79", "gpu_fallen_off_bus") not in all_xids_and_cats  # xid is int, not str
    assert (79, "gpu_fallen_off_bus") in all_xids_and_cats
    assert (154, "driver_software") in all_xids_and_cats

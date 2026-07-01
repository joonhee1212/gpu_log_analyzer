"""
Parser tests against both synthetic fixtures and the real sample logs.
"""
from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

import pytest

from datetime import datetime

from gpu_log_analyzer.classifier import load_xid_reference
from gpu_log_analyzer.generator import (
    _FORMATS,
    _KITCHEN_SINK_XIDS,
    generate_burst,
    make_gpu,
    single_code_file,
    _TimestampCursor,
)
from gpu_log_analyzer.parser import parse_file, INCIDENT_GAP_SECS

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "real"


# --- helpers ---

def _write_and_parse(tmp_path, content: str, name: str = "test.log"):
    p = tmp_path / name
    p.write_text(content)
    return parse_file(p)


# --- single-code fixture tests ---

@pytest.fixture(scope="module")
def ref():
    return load_xid_reference()


def test_all_single_code_fixtures_parse_one_incident(ref):
    """Every xid_NNN.log should produce exactly one incident."""
    real_codes = sorted(k for k in ref if k != 0)
    for xid in real_codes:
        path = FIXTURE_DIR / f"xid_{xid:03d}.log"
        incidents = parse_file(path)
        assert len(incidents) == 1, f"Xid {xid}: expected 1 incident, got {len(incidents)}"


def test_all_single_code_fixtures_have_correct_xid(ref):
    """The first event in each xid_NNN.log must have the matching Xid code."""
    real_codes = sorted(k for k in ref if k != 0)
    for xid in real_codes:
        path = FIXTURE_DIR / f"xid_{xid:03d}.log"
        incidents = parse_file(path)
        first_xid = incidents[0].events[0].xid
        assert first_xid == xid, f"xid_{xid:03d}.log: first event has Xid {first_xid}"


def test_all_single_code_fixtures_have_uuid(ref):
    """UUID should be populated for every synthetic fixture (generator always emits UUID line)."""
    real_codes = sorted(k for k in ref if k != 0)
    for xid in real_codes:
        path = FIXTURE_DIR / f"xid_{xid:03d}.log"
        incidents = parse_file(path)
        assert incidents[0].gpu_uuid is not None, f"Xid {xid}: gpu_uuid is None"
        assert incidents[0].gpu_uuid.startswith("GPU-"), f"Xid {xid}: unexpected UUID format"


# --- timestamp format tests ---

@pytest.mark.parametrize("fmt", ["iso8601", "syslog", "dmesg"])
def test_timestamp_formats_all_parse(tmp_path, fmt):
    """All three timestamp formats must be parsed without dropping the Xid line."""
    content = single_code_file(79, fmt=fmt)
    p = tmp_path / f"fmt_{fmt}.log"
    p.write_text(content)
    incidents = parse_file(p)
    assert len(incidents) >= 1
    assert incidents[0].events[0].xid == 79


def test_syslog_burst_shares_timestamp(tmp_path):
    """Syslog lines in a burst share the same second — parser must group them as one incident."""
    content = single_code_file(79, fmt="syslog")
    incidents = _write_and_parse(tmp_path, content)
    assert len(incidents) == 1


# --- repeated-line collapsing ---

def test_repeated_lines_not_counted_as_separate_incidents(tmp_path):
    """'message repeated N times:' should not produce extra incidents or events."""
    # Xid 79 burst contains a repeated-line collapse in its noise
    content = single_code_file(79, fmt="iso8601")
    incidents = _write_and_parse(tmp_path, content)
    # should be exactly 1 incident (79 + 154 follow-up = 2 events, not 2 incidents)
    assert len(incidents) == 1

def test_repeated_lines_absorbed_into_raw_lines(tmp_path):
    """The 'message repeated' line should be in raw_lines of the event, not silently dropped."""
    content = single_code_file(79, fmt="iso8601")
    incidents = _write_and_parse(tmp_path, content)
    all_raw = "\n".join("\n".join(ev.raw_lines) for ev in incidents[0].events)
    assert "message repeated" in all_raw


# --- 79 → 154 burst grouping ---

def test_xid79_burst_contains_154_followup(tmp_path):
    """Xid 79 bursts should include a Xid 154 follow-up as a second event in the same incident."""
    content = single_code_file(79, fmt="iso8601")
    incidents = _write_and_parse(tmp_path, content)
    xids_in_incident = [ev.xid for ev in incidents[0].events]
    assert 79 in xids_in_incident
    assert 154 in xids_in_incident
    assert len(incidents) == 1, "79 and 154 should be one incident, not two"


# --- kitchen sink ---

def test_kitchen_sink_has_multiple_incidents():
    incidents = parse_file(FIXTURE_DIR / "kitchen_sink.log")
    assert len(incidents) >= len(_KITCHEN_SINK_XIDS)


def test_kitchen_sink_recurrence_detectable():
    """First Xid in the kitchen sink is repeated — should appear in 2+ incidents."""
    incidents = parse_file(FIXTURE_DIR / "kitchen_sink.log")
    counts = Counter(
        (inc.pci_addr, ev.xid)
        for inc in incidents
        for ev in inc.events
    )
    recurring = {k: v for k, v in counts.items() if v > 1}
    assert len(recurring) >= 1, f"no recurring (pci, xid) found; counts={dict(counts)}"


def test_kitchen_sink_all_incidents_same_gpu():
    """Kitchen sink uses one GPU — all incidents should share the same PCI address and UUID."""
    incidents = parse_file(FIXTURE_DIR / "kitchen_sink.log")
    pci_addrs = {inc.pci_addr for inc in incidents}
    uuids = {inc.gpu_uuid for inc in incidents}
    assert len(pci_addrs) == 1
    assert len(uuids) == 1
    assert None not in uuids


# --- INCIDENT_GAP_SECS boundary tests ---
#
# The 61/62 escalation sample uses dmesg format, so its timestamps never go through
# _parse_ts_for_gap — the gap is invisible to the parser and both Xids land in the
# same incident. The tests below document that known behavior, then separately test
# the actual gap boundary using iso8601 format where gap detection runs.

SYNTHETIC_DIR = Path(__file__).parent.parent / "samples" / "synthetic"


def test_61_62_escalation_is_one_incident_two_events():
    """dmesg timestamps aren't parseable, so the 12s gap between Xid 61 and 62
    bypasses INCIDENT_GAP_SECS entirely — both land in one incident as two events."""
    incidents = parse_file(SYNTHETIC_DIR / "xid_061_062_microcontroller_escalation.log")
    assert len(incidents) == 1, "dmesg-format gap should not split into two incidents"
    xids = [ev.xid for ev in incidents[0].events]
    assert xids == [61, 62], f"expected [61, 62] in order, got {xids}"


def _two_burst_iso8601(tmp_path, gap_secs: int) -> list:
    """Helper: write a file with two Xid 61 bursts on the same GPU separated by gap_secs,
    using iso8601 format so the parser can actually measure the gap."""
    rng = random.Random(99)
    gpu = make_gpu(rng=rng)
    base = datetime(2026, 5, 1, 12, 0, 0)
    cursor = _TimestampCursor(base, "iso8601")
    lines = generate_burst(61, gpu, cursor, rng, add_154_followup=False)
    cursor.advance(gap_secs)
    lines.extend(generate_burst(61, gpu, cursor, rng, include_uuid_line=False, add_154_followup=False))
    p = tmp_path / "gap_test.log"
    p.write_text("\n".join(lines) + "\n")
    return parse_file(p)


def test_gap_within_threshold_is_same_incident(tmp_path):
    """Gap well inside INCIDENT_GAP_SECS should be treated as the same incident.
    Note: the measured gap is advance_secs + burst noise duration (sub-second ticks),
    so testing at exactly INCIDENT_GAP_SECS is ambiguous — use a value clearly under."""
    incidents = _two_burst_iso8601(tmp_path, gap_secs=INCIDENT_GAP_SECS - 2)
    assert len(incidents) == 1, (
        f"gap of {INCIDENT_GAP_SECS - 2}s should stay as one incident, got {len(incidents)}"
    )


def test_gap_over_threshold_is_new_incident(tmp_path):
    """Gap over INCIDENT_GAP_SECS should open a new incident."""
    incidents = _two_burst_iso8601(tmp_path, gap_secs=INCIDENT_GAP_SECS + 1)
    assert len(incidents) == 2, (
        f"gap of {INCIDENT_GAP_SECS + 1}s should split into two incidents, got {len(incidents)}"
    )


def test_gap_well_over_threshold_is_new_incident(tmp_path):
    """Large gap (1 hour) should always produce two separate incidents."""
    incidents = _two_burst_iso8601(tmp_path, gap_secs=3600)
    assert len(incidents) == 2


# --- real sample log regression tests ---

def test_real_incident1_parses_correctly():
    path = SAMPLES_DIR / "incident1_first_occurrence.log"
    incidents = parse_file(path)
    assert len(incidents) == 1
    xids = [ev.xid for ev in incidents[0].events]
    assert 79 in xids
    assert 154 in xids
    assert incidents[0].gpu_uuid == "GPU-a13e0a3a-e4d7-0a3c-ccf2-29c1f34b9812"


def test_real_incident2_uuid_carried_forward():
    """incident2 has no UUID line before Xid 154 — UUID must be carried forward from Xid 79."""
    path = SAMPLES_DIR / "incident2_recurrence.log"
    incidents = parse_file(path)
    assert len(incidents) == 1
    for ev in incidents[0].events:
        assert incidents[0].gpu_uuid is not None

def test_real_samples_recurrence_across_files():
    """Parsing both files together should reveal Xid 79 recurring on the same GPU."""
    incidents = []
    for name in ["incident1_first_occurrence.log", "incident2_recurrence.log"]:
        incidents.extend(parse_file(SAMPLES_DIR / name))
    counts = Counter((inc.pci_addr, ev.xid) for inc in incidents for ev in inc.events)
    assert counts[("0000:01:00", 79)] == 2

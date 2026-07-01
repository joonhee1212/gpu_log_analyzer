from __future__ import annotations

import json
from pathlib import Path

from .models import ClassifiedEvent, ClassifiedIncident, Incident, XidInfo

_DEFAULT_REF_PATH = Path(__file__).parent.parent / "data" / "xid_reference.json"


def load_xid_reference(path: str | Path = _DEFAULT_REF_PATH) -> dict[int, XidInfo]:
    with open(path) as f:
        raw = json.load(f)
    return {
        int(code): XidInfo(
            name=entry["name"],
            category=entry["category"],
            severity=entry["severity"],
            likely_cause=entry["likely_cause"],
            action=entry["action"],
            notes=entry["notes"],
        )
        for code, entry in raw.items()
    }


def classify_incidents(
    incidents: list[Incident],
    ref: dict[int, XidInfo] | None = None,
) -> list[ClassifiedIncident]:
    if ref is None:
        ref = load_xid_reference()

    fallback = ref[0]  # "Unknown / Unmapped Xid" entry

    result = []
    for incident in incidents:
        classified_events = [
            ClassifiedEvent(
                event=ev,
                info=ref.get(ev.xid, fallback),
            )
            for ev in incident.events
        ]
        result.append(ClassifiedIncident(incident=incident, classified_events=classified_events))

    return result

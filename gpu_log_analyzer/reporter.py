from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .models import ClassifiedIncident

_DIVIDER = "-" * 60
_HEADER  = "=" * 60


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        pass
    try:
        return datetime.strptime(ts, "%b %d %H:%M:%S")
    except ValueError:
        pass
    return None


def _incident_sort_key(ci: ClassifiedIncident) -> tuple:
    if ci.classified_events:
        parsed = _parse_ts(ci.classified_events[0].event.timestamp)
        if parsed:
            # month/day/time tuple — good enough for same-year logs
            return (parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second, parsed.microsecond)
    return (13, 0, 0, 0, 0, 0)  # sorts after any real timestamp


def generate_report(classified_incidents: list[ClassifiedIncident]) -> str:
    # --- recurrence counts: (pci_addr, xid) -> occurrence count across all incidents ---
    xid_counts: dict[tuple[str, int], int] = defaultdict(int)
    for ci in classified_incidents:
        for ce in ci.classified_events:
            xid_counts[(ci.incident.pci_addr, ce.event.xid)] += 1

    # group by PCI address, sort each GPU's incidents chronologically
    by_pci: dict[str, list[ClassifiedIncident]] = defaultdict(list)
    for ci in classified_incidents:
        by_pci[ci.incident.pci_addr].append(ci)
    for incidents in by_pci.values():
        incidents.sort(key=_incident_sort_key)

    out: list[str] = []

    file_count = len({ci.incident.source_file for ci in classified_incidents})
    out.append("GPU Log Analysis Report")
    out.append(f"Source files: {file_count}")
    out.append(_HEADER)

    for pci, incidents in sorted(by_pci.items()):
        uuid = incidents[0].incident.gpu_uuid or "unknown"
        out.append("")
        out.append(f"GPU {pci}  [UUID: {uuid}]")
        out.append(_DIVIDER)

        for idx, ci in enumerate(incidents, 1):
            ts = ci.classified_events[0].event.timestamp if ci.classified_events else "unknown"
            src = Path(ci.incident.source_file).name
            out.append("")
            out.append(f"  Incident {idx}  [{ts}]  ({src})")

            for ce in ci.classified_events:
                ev, info = ce.event, ce.info
                count = xid_counts[(pci, ev.xid)]
                recur_tag = f"  [RECURRING x{count}]" if count > 1 else ""

                out.append("")
                out.append(f"    Xid {ev.xid}  {info.name}{recur_tag}")
                out.append(f"      severity : {info.severity.upper()}")
                out.append(f"      category : {info.category}")
                out.append(f"      action   : {info.action}")
                if ev.detail:
                    out.append(f"      detail   : {ev.detail}")

        out.append("")

    # --- recurrence summary ---
    recurring = [(k, v) for k, v in xid_counts.items() if v > 1]
    if recurring:
        out.append(_HEADER)
        out.append("RECURRENCE SUMMARY")

        # collect xid info (name, notes) from classified events — only need one lookup per (pci, xid)
        xid_meta: dict[tuple[str, int], tuple[str, str]] = {}
        for ci in classified_incidents:
            for ce in ci.classified_events:
                key = (ci.incident.pci_addr, ce.event.xid)
                if key not in xid_meta:
                    xid_meta[key] = (ce.info.name, ce.info.notes)

        for (pci, xid), count in sorted(recurring):
            name, notes = xid_meta.get((pci, xid), ("unknown", ""))
            out.append("")
            out.append(f"  Xid {xid}  ({name})  —  {count}x on {pci}")
            if notes:
                out.append(f"  Note: {notes}")

        out.append("")

    return "\n".join(out)

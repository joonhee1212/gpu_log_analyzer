from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class XidEvent:
    xid: int
    pci_addr: str
    timestamp: str          # raw string from log, not normalized
    pid: int | None
    process_name: str | None
    detail: str             # everything after "xid, " on the Xid line
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class Incident:
    pci_addr: str
    gpu_uuid: str | None    # carried forward from last-seen UUID for this PCI addr
    events: list[XidEvent] = field(default_factory=list)
    source_file: str = ""


@dataclass
class XidInfo:
    """Enrichment fields from xid_reference.json for one Xid code."""
    name: str
    category: str
    severity: str
    likely_cause: str
    action: str
    notes: str


@dataclass
class ClassifiedEvent:
    event: XidEvent
    info: XidInfo


@dataclass
class ClassifiedIncident:
    incident: Incident
    classified_events: list[ClassifiedEvent] = field(default_factory=list)

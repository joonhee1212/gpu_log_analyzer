from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .models import Incident, XidEvent


# how long a gap between same-PCI Xids before we call it a new incident
INCIDENT_GAP_SECS = 10


# --- timestamp prefix stripping ---

_ISO_RE = re.compile(
    r'^(\d{4}-\d{2}-\d{2}T[\d:.\-+]+)\s+\S+\s+\S+:\s*(.*)'
)
_SYS_RE = re.compile(
    r'^((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+\s+\d{2}:\d{2}:\d{2})\s+\S+\s+\S+:\s*(.*)'
)
_DMESG_RE = re.compile(r'^(\[\s*[\d.]+\])\s*(.*)')


def _strip_prefix(line: str) -> tuple[str, str] | tuple[None, None]:
    for pattern in (_ISO_RE, _SYS_RE, _DMESG_RE):
        m = pattern.match(line)
        if m:
            return m.group(1), m.group(2)
    return None, None


def _parse_ts_for_gap(ts: str) -> datetime | None:
    # only used internally to detect whether same-PCI Xids are in the same burst.
    # always return a naive datetime so mixed-format files (ISO8601 + syslog) don't
    # crash when subtracting an aware datetime from a naive one.
    try:
        return datetime.fromisoformat(ts).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        return datetime.strptime(ts, "%b %d %H:%M:%S")
    except ValueError:
        pass
    return None


# --- body classification ---

_UUID_RE = re.compile(r'NVRM: GPU at PCI:([\w:.]+):\s+(GPU-[\w-]+)')
_XID_RE = re.compile(r'NVRM: Xid \(PCI:([\w:.]+)\):\s*(\d+),?\s*(.*)')
_PID_RE = re.compile(r'pid=(\d+)(?:,\s*name=([\w-]+))?')
_REPEATED_RE = re.compile(r'message repeated (\d+) times: \[(.*)\]')


def _classify_body(body: str) -> tuple[str, dict]:
    m = _REPEATED_RE.search(body)
    if m:
        return 'REPEATED', {'count': int(m.group(1)), 'content': m.group(2)}

    m = _UUID_RE.match(body)
    if m:
        return 'GPU_UUID', {'pci_addr': m.group(1), 'uuid': m.group(2)}

    m = _XID_RE.match(body)
    if m:
        pci_addr, xid_str, rest = m.group(1), m.group(2), m.group(3).strip()
        fields: dict = {'pci_addr': pci_addr, 'xid': int(xid_str), 'detail': rest}
        pid_m = _PID_RE.search(rest)
        if pid_m:
            fields['pid'] = int(pid_m.group(1))
            fields['process_name'] = pid_m.group(2)  # may be None if name= absent
        else:
            fields['pid'] = None
            fields['process_name'] = None
        return 'XID', fields

    return 'NOISE', {}


# main parse function 

def parse_file(path: str | Path) -> list[Incident]:
    path = str(path)
    # PCI addr -> last-seen UUID; carries forward across the whole file so that
    # any Xid on a known PCI addr gets the UUID even if the UUID line isn't repeated
    uuid_by_pci: dict[str, str] = {}
    # used only for gap detection, not stored anywhere
    last_ts_by_pci: dict[str, datetime] = {}

    incidents: list[Incident] = []
    current_incident: Incident | None = None
    current_event: XidEvent | None = None

    with open(path) as f:
        lines = f.readlines()

    for raw_line in lines:
        raw_line = raw_line.rstrip('\n')
        ts, body = _strip_prefix(raw_line)
        if body is None:
            continue

        ltype, fields = _classify_body(body)

        if ltype == 'REPEATED':
            if current_event:
                current_event.raw_lines.append(raw_line)
            continue

        if ltype == 'GPU_UUID':
            uuid_by_pci[fields['pci_addr']] = fields['uuid']
            # UUID line precedes the Xid line in the burst; no event open yet
            if current_event:
                current_event.raw_lines.append(raw_line)
            continue

        if ltype == 'NOISE':
            if current_event:
                current_event.raw_lines.append(raw_line)
            continue

        if ltype == 'XID':
            pci_addr = fields['pci_addr']
            parsed_ts = _parse_ts_for_gap(ts) if ts else None

            # is this Xid part of the current incident or the start of a new one?
            same_incident = False
            if current_incident and current_incident.pci_addr == pci_addr:
                last_ts = last_ts_by_pci.get(pci_addr)
                if last_ts and parsed_ts:
                    gap = abs((parsed_ts - last_ts).total_seconds())
                    same_incident = gap <= INCIDENT_GAP_SECS
                else:
                    # can't compute a gap — at least one side is unparseable (e.g. dmesg
                    # uptime following a syslog burst). only treat as same burst if NEITHER
                    # side has timing info; if one is parseable and the other isn't, play safe.
                    same_incident = (last_ts is None and parsed_ts is None)
                    # TODO: dmesg-only files with multiple incidents can't be separated here
                    # because dmesg uptime floats don't go through _parse_ts_for_gap. fix this
                    # when adding --follow / live dmesg streaming — extract the uptime float
                    # from the bracket and use a separate numeric gap comparison path.

            if not same_incident:
                if current_incident:
                    incidents.append(current_incident)
                current_incident = Incident(
                    pci_addr=pci_addr,
                    gpu_uuid=uuid_by_pci.get(pci_addr),
                    source_file=path,
                )

            # fill in UUID if we learned it after incident was created
            if current_incident.gpu_uuid is None:
                current_incident.gpu_uuid = uuid_by_pci.get(pci_addr)

            if parsed_ts:
                last_ts_by_pci[pci_addr] = parsed_ts

            current_event = XidEvent(
                xid=fields['xid'],
                pci_addr=pci_addr,
                timestamp=ts or '',
                pid=fields.get('pid'),
                process_name=fields.get('process_name'),
                detail=fields.get('detail', ''),
                raw_lines=[raw_line],
            )
            current_incident.events.append(current_event)

    if current_incident:
        incidents.append(current_incident)

    return incidents

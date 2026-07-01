from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from .classifier import classify_incidents, load_xid_reference
from .models import ClassifiedIncident
from .parser import parse_file
from .reporter import generate_report


def _summary_line(classified: list[ClassifiedIncident]) -> str:
    gpu_count = len({ci.incident.pci_addr for ci in classified})
    event_count = sum(len(ci.classified_events) for ci in classified)

    xid_counts: dict[tuple[str, int], int] = defaultdict(int)
    for ci in classified:
        for ce in ci.classified_events:
            xid_counts[(ci.incident.pci_addr, ce.event.xid)] += 1
    recurring_count = sum(1 for v in xid_counts.values() if v > 1)

    gpu_word    = "GPU"    if gpu_count    == 1 else "GPUs"
    event_word  = "event"  if event_count  == 1 else "events"
    fault_word  = "fault"  if recurring_count == 1 else "faults"

    return (
        f"{gpu_count} {gpu_word} analyzed, "
        f"{event_count} total {event_word}, "
        f"{recurring_count} recurring {fault_word} detected"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gpu_log_analyzer",
        description="Parse NVIDIA GPU error logs and produce a diagnostic report.",
    )
    parser.add_argument(
        "logs",
        metavar="LOG",
        nargs="+",
        help="one or more log files to analyze",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="write report to FILE instead of stdout",
    )
    parser.add_argument(
        "--xid-ref",
        metavar="FILE",
        default=None,
        help="path to a custom xid_reference.json (default: bundled data/xid_reference.json)",
    )
    args = parser.parse_args()

    # validate inputs up front so we fail loudly before doing any work
    missing = [p for p in args.logs if not Path(p).is_file()]
    if missing:
        for p in missing:
            print(f"error: file not found: {p}", file=sys.stderr)
        sys.exit(1)

    ref = load_xid_reference(args.xid_ref) if args.xid_ref else load_xid_reference()

    all_incidents = []
    for log_path in args.logs:
        all_incidents.extend(parse_file(log_path))

    classified = classify_incidents(all_incidents, ref)

    report = generate_report(classified)
    summary = _summary_line(classified)
    full_output = report + "\n" + summary + "\n"

    if args.output:
        Path(args.output).write_text(full_output)
        print(f"report written to {args.output}", file=sys.stderr)
    else:
        print(full_output, end="")


if __name__ == "__main__":
    main()

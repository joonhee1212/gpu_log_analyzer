# GPU Error Log Analysis Tool — Project Brief

## What this is
A tool that parses NVIDIA GPU error logs (Xid errors from dmesg / nvidia-bug-report.log),
classifies them by category and severity, and produces a diagnostic report — instead of
just grepping raw error codes, it tells the user what the error means and what to do about it.

Goal: a meaningful, portfolio-worthy GitHub project grounded in real GPU/ML-infra operations,
not a toy log parser.

## Current status
- [x] Defined error taxonomy / categories (see below)
- [x] Built `data/xid_reference.json` — Xid code -> {name, category, severity, likely_cause, action, notes}
- [x] Collected real sample logs in `samples/real/` (redacted excerpts from an actual
      nvidia-bug-report.log, showing a real recurring Xid 79 -> Xid 154 incident)
- [ ] Parser (next step)
- [ ] Classifier (uses xid_reference.json to enrich parsed results)
- [ ] Report generator (CLI output, maybe markdown/HTML)
- [ ] Synthetic log generator (for tests / letting others try it without real hardware)

## Category taxonomy (used in xid_reference.json)
- `memory_ecc` — ECC errors, row remapping (Xid 48, 63, 64, 95)
- `illegal_memory_access` — page faults, out-of-bounds access (Xid 13, 31)
- `gpu_fallen_off_bus` — GPU unresponsive on PCIe bus (Xid 79)
- `gsp_firmware_error` — GSP microcontroller/firmware issues (Xid 119, 120, 143)
- `nvlink_nvswitch` — interconnect/fabric errors, including newer NVLink5 (Xid 74, 144-150)
- `thermal_power` — power/cooling issues (Xid 54)
- `driver_software` — generic driver/software-level errors (Xid 14, 43, 45, 109, 154, 32, 56)
- `unknown_uncategorized` — fallback for codes not yet in the reference table

`xid_reference.json` was built by hand (with LLM assistance) from NVIDIA's official Xid
documentation (docs.nvidia.com/deploy/xid-errors) and cross-referenced against real-world
log samples. It is NOT an official NVIDIA file — it's a starting scaffold (~16 codes) and
should grow over time. Attribution to NVIDIA's docs belongs in the README.

## Sample logs (`samples/real/`)
Two redacted excerpts from a real nvidia-bug-report.log:
- `incident1_first_occurrence.log` — first Xid 79 ("fallen off the bus") -> Xid 154
  ("GPU recovery action changed to Reset Required"), with surrounding GSP RPC context
- `incident2_recurrence.log` — same pattern recurring ~11 hours later, same PCI address
  and GPU UUID

Important: these are NOT single clean lines. They're realistic bursts of related log
lines (GPU identifier line -> Xid line -> RPC/assertion noise -> second Xid line). The
parser needs to associate a burst with one incident, not just extract isolated Xid lines.
Also note real logs contain repeated-line collapsing like
`message repeated 13 times: [...]` — the parser should handle/collapse this pattern
rather than choke on it or treat manually-repeated lines as N separate incidents.

The recurrence across the two files (same GPU, same fault, hours apart) is meant to be
a signal the tool eventually surfaces: repeated Xid on the same device = escalate,
per NVIDIA's own operational guidance.

## Immediate next step: parser design
Requirements gathered so far:
- Input: raw text log files (dmesg-style or full nvidia-bug-report.log dumps, which are
  mostly irrelevant noise around a small number of relevant lines)
- Must extract: PCI device ID / GPU UUID, timestamp, Xid code, and any inline detail
  (e.g. pid/process name, fault type, error strings) when present
- Log line formats vary — some have `pid=`, some don't; some are single-line, some
  cascade across many related lines; timestamp formats vary between plain dmesg
  (`[ 142.881234]`), syslog-style (`Feb 03 01:53:05`), and ISO8601 with kernel prefix
  (as seen in the real samples)
- Should group related lines into one "incident" rather than emit one row per line
- Output should be structured (e.g. list of incident objects) so the classifier step
  can consume it and look up each Xid in `xid_reference.json`

## Tech preferences
- Python, using `re` or a small state machine for parsing
- Structured output (dataclass or dict) per incident
- CLI entry point (click or argparse/typer) for later report generation step

## Not yet decided / open questions for this session
- Exact incident-grouping heuristic (time-window based? same-PCI-address + Xid-adjacency?)
- Whether to support live `dmesg` streaming vs. static file input only (static file first)
- Report output format (plain text first, HTML/markdown later)

## Git / GitHub workflow
- Repo name: gpu-log-analyzer
- Visibility: public
- Use Conventional Commits (feat:, fix:, docs:, etc.) but keep the description casual
  per the tone guidance below
- Commit after each meaningful milestone, not just at the end of a session
- Include a Python .gitignore
- Push to GitHub after each commit (or at minimum, at end of each session)

## Voice / tone for comments and commit messages
Write code comments and commit messages like a CS student working on a personal
project, not like an AI assistant. Concretely:
- No corporate/marketing tone ("leverages," "robust," "seamlessly," "comprehensive solution")
- No over-explaining obvious code; comment on *why*, not *what*, and only when it's
  actually non-obvious
- Casual is fine: "quick hack for now, revisit later" / "this regex is ugly but it works"
  / "TODO: this breaks if the log has no timestamp, fix later"
- Commit messages: short, lowercase-first, plain description of what changed —
  e.g. `add xid regex parser`, `fix incident grouping edge case`, `wip: report formatting`
  — not `Implement comprehensive XID parsing module with enhanced error handling`
- It's fine to leave in a rough edge, a TODO, or an honest "not sure this is the best
  way to do this" comment — that reads as real, not polished-to-death
- Skip emoji in commits/comments unless I use them first
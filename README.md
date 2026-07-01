# gpu-log-analyzer

Parse NVIDIA GPU error logs, classify Xid error codes, and produce a human-readable diagnostic report — instead of just grepping raw codes, it tells you what the error means and what to do about it.

Built on real `nvidia-bug-report.log` samples from a recurring Xid 79 ("GPU has fallen off the bus") incident.

---

## What it does

- Parses raw log files (`dmesg` output or `nvidia-bug-report.log` excerpts)
- Handles both ISO8601 and syslog-style timestamps, and collapses `message repeated N times` noise
- Groups related log lines into incidents (e.g. Xid 79 → Xid 154 bursts), rather than emitting one row per line
- Classifies each Xid code against a reference table: name, severity, category, recommended action
- **Detects recurrence** — if the same Xid appears more than once on the same GPU across multiple log files, it flags it and summarizes at the bottom. NVIDIA's own operational guidance treats repeated Xid 79 as escalation-worthy (possible hardware fault, not a one-off transient).
- Accepts multiple log files at once so you can compare across incidents

---

## Install

Requires Python 3.9+, no third-party dependencies.

```bash
git clone https://github.com/joonhee1212/gpu-log-analyzer.git
cd gpu-log-analyzer
pip install -e .
```

After install, the `gpu-log-analyzer` command is available on your PATH.

---

## Usage

```
gpu-log-analyzer LOG [LOG ...] [--output FILE] [--xid-ref FILE]
```

```bash
# analyze one or more log files, print to stdout
gpu-log-analyzer incident1.log incident2.log

# write report to a file instead
gpu-log-analyzer incident1.log incident2.log --output report.txt

# use a custom xid_reference.json (e.g. with more codes added)
gpu-log-analyzer dmesg.log --xid-ref my_xid_ref.json
```

You can also run it without installing:

```bash
python -m gpu_log_analyzer.cli incident1.log incident2.log
```

---

## Example output

Running against the two real sample logs included in `samples/real/`:

```
$ gpu-log-analyzer samples/real/incident1_first_occurrence.log samples/real/incident2_recurrence.log

GPU Log Analysis Report
Source files: 2
============================================================

GPU 0000:01:00  [UUID: GPU-a13e0a3a-e4d7-0a3c-ccf2-29c1f34b9812]
------------------------------------------------------------

  Incident 1  [2026-02-02T14:42:51.867977-06:00]  (incident1_first_occurrence.log)

    Xid 79  GPU Has Fallen Off the Bus  [RECURRING x2]
      severity : CRITICAL
      category : gpu_fallen_off_bus
      action   : RESET_GPU
      detail   : pid=2361, name=mutter-x11-fram, GPU has fallen off the bus.

    Xid 154  GPU Recovery Action Required  [RECURRING x2]
      severity : MEDIUM
      category : driver_software
      action   : CHECK_RECOVERY_ACTION
      detail   : GPU recovery action changed from 0x0 (None) to 0x1 (GPU Reset Required)

  Incident 2  [Feb 03 01:53:05]  (incident2_recurrence.log)

    Xid 79  GPU Has Fallen Off the Bus  [RECURRING x2]
      severity : CRITICAL
      category : gpu_fallen_off_bus
      action   : RESET_GPU
      detail   : GPU has fallen off the bus.

    Xid 154  GPU Recovery Action Required  [RECURRING x2]
      severity : MEDIUM
      category : driver_software
      action   : CHECK_RECOVERY_ACTION
      detail   : GPU recovery action changed from 0x0 (None) to 0x1 (GPU Reset Required)

============================================================
RECURRENCE SUMMARY

  Xid 79  (GPU Has Fallen Off the Bus)  —  2x on 0000:01:00
  Note: Frequently requires a physical reseat or node reboot if reset doesn't recover it. Can also appear as multiline log entries without an explicit Xid tag.

  Xid 154  (GPU Recovery Action Required)  —  2x on 0000:01:00
  Note: Visible via nvidia-smi's GPU Recovery Action field; pair with nvidia-smi output when parsing.

1 GPU analyzed, 4 total events, 2 recurring faults detected
```

---

## xid_reference.json

`data/xid_reference.json` maps Xid codes to structured metadata:

```json
"79": {
  "name": "GPU Has Fallen Off the Bus",
  "category": "gpu_fallen_off_bus",
  "severity": "critical",
  "likely_cause": "GPU became unresponsive on the PCIe bus, often due to power, thermal, seating, or hardware failure.",
  "action": "RESET_GPU",
  "notes": "Frequently requires a physical reseat or node reboot if reset doesn't recover it."
}
```

Fields:

| Field | Description |
|---|---|
| `name` | Short human-readable name for the Xid |
| `category` | Error category (see below) |
| `severity` | `low` / `medium` / `high` / `critical` |
| `likely_cause` | What typically causes this error |
| `action` | Recommended first action |
| `notes` | Extra context — caveats, related errors, operational tips |

Error categories: `memory_ecc`, `illegal_memory_access`, `gpu_fallen_off_bus`, `gsp_firmware_error`, `nvlink_nvswitch`, `thermal_power`, `driver_software`, `unknown_uncategorized`.

**Attribution:** the reference table was built from [NVIDIA's official Xid error documentation](https://docs.nvidia.com/deploy/xid-errors/index.html) and cross-referenced against real log samples. This is not an official NVIDIA file. The authoritative source is NVIDIA's docs and `nverror.h` in [open-gpu-kernel-modules](https://github.com/NVIDIA/open-gpu-kernel-modules).

---

## Project structure

```
gpu_log_analyzer/
  cli.py          # gpu-log-analyzer entry point, wires parse -> classify -> report
  generator.py    # gpu-log-generator entry point, synthetic log generation
  parser.py       # regex + state machine, produces Incident objects
  classifier.py   # looks up each Xid in xid_reference.json
  reporter.py     # formats ClassifiedIncident list as plain text
  models.py       # dataclasses: XidEvent, Incident, ClassifiedEvent, ClassifiedIncident

data/
  xid_reference.json   # Xid code -> name/severity/category/action/notes (33 codes)

samples/real/
  incident1_first_occurrence.log   # real Xid 79 -> 154 burst
  incident2_recurrence.log         # same GPU, same fault, ~11 hours later

tests/
  conftest.py          # generates synthetic fixtures at session start
  test_parser.py       # 20 parser tests (formats, grouping, recurrence, real samples)
  test_classifier.py   # 12 classifier tests (reference table, enrichment, fallback)
  fixtures/            # generated at test time, not checked in
```

---

## Known limitations

- **~33 Xid codes covered.** NVIDIA documents 200+ Xid codes; unknown ones fall back to a generic "Unknown / Unmapped Xid" entry. See the [full NVIDIA Xid catalog](https://docs.nvidia.com/deploy/xid-errors/index.html) to add more.
- **Static file input only.** Live `dmesg -w` streaming is not supported yet.
- **Syslog timestamps have no year.** Logs in `Feb 03 01:53:05` format are stored and displayed as-is; the year is not inferred. Chronological sorting within the same year still works correctly.
- **dmesg-only files can't separate multiple incidents.** dmesg timestamps are boot-relative floats (`[ 142.881234]`), not wall-clock datetimes, so the incident gap detector can't compute time differences between them. Two separate incidents in a dmesg-only file will be merged into one. This will be fixed when live `dmesg` streaming support is added (requires a numeric gap-comparison path separate from the datetime one).
- **Tested on two real log excerpts.** Other GPU models, driver versions, or log formats may surface parsing edge cases.

---

## Roadmap

Done:
- [x] Xid reference table — 33 codes across 7 categories, built from NVIDIA's official docs
- [x] Parser — handles ISO8601, syslog, and dmesg timestamp formats; groups multi-line bursts into incidents; collapses `message repeated N times`; detects recurrence across files
- [x] Classifier — enriches each Xid with name/severity/category/action from the reference table; unknown codes fall back gracefully
- [x] Report generator — grouped by GPU, sorted chronologically, recurrence flagged inline and summarized at the bottom
- [x] CLI — `gpu-log-analyzer` entry point; multi-file input; `--output` flag
- [x] Synthetic log generator — `gpu-log-generator` entry point; single-code and kitchen-sink modes; all three timestamp formats; realistic noise/burst structure
- [x] Test suite — 32 tests covering parser, classifier, all fixture formats, recurrence detection, and real sample regression

Up next:
- **More Xid coverage** — expand toward full NVIDIA catalog (200+ codes)
- **Markdown / HTML report output** — `--format md` or `--format html` flag
- **Live dmesg streaming** — `--follow` mode; also fixes dmesg-only multi-incident gap detection
- **`nvidia-smi` correlation** — pair Xid 154 (recovery action) with live `nvidia-smi` output to surface the actual recovery state

---

## Acknowledgments

This project was designed and built with assistance from [Claude](https://claude.ai) (Anthropic) — architecture discussion, parsing strategy, and implementation via Claude Code. The Xid reference data is derived from [NVIDIA's official documentation](https://docs.nvidia.com/deploy/xid-errors/index.html).

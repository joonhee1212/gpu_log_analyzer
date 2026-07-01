# Synthetic sample logs

Generated with `gpu_log_analyzer.generator` to demonstrate Xid codes added in the
reference table expansion (16 → 33 codes). All files are deterministic — same seed
produces the same bytes.

| File | Xids | Format | What it shows |
|---|---|---|---|
| `xid_094_contained_ecc.log` | 94 | iso8601 | ECC error successfully contained to one app |
| `xid_109_context_switch_timeout.log` | 109 → 154 | syslog | Context switch timeout (early warning before bus fall) + recovery action |
| `xid_080_bar1_bus_fall.log` | 80 → 154 | iso8601 | BAR1 PCIe mapping loss + recovery action |
| `xid_145_nvlink5_nonfatal.log` | 145 | syslog | NVLink5 non-fatal link event |
| `xid_061_062_microcontroller_escalation.log` | 61 → 62 | dmesg | Micro-controller error escalating to halt (12s apart, same GPU) |
| `mixed_new_codes.log` | 6, 38, 65, 68, 73, 94, 145 | rotating | Multi-incident kitchen sink across illegal_memory_access, driver_software, memory_ecc, nvlink_nvswitch |

To regenerate: `python -m gpu_log_analyzer.generator fixtures --output-dir samples/synthetic`
(or use the individual `single`/`kitchen-sink` subcommands for custom output).

# GPU Log Analyzer — Project Notes

## Category taxonomy

Categories used in `data/xid_reference.json`:

| Category | Description | Example Xids |
|---|---|---|
| Category | Description | Example Xids |
|---|---|---|
| `memory_ecc` | ECC errors, row remapping, DRAM/SRAM faults | 48, 63, 64, 92, 94, 95, 140, 171, 172 |
| `illegal_memory_access` | Page faults, out-of-bounds access | 6, 13, 31 |
| `gpu_fallen_off_bus` | GPU unresponsive on PCIe bus | 79, 80 |
| `gsp_firmware_error` | GSP/PMU microcontroller/firmware issues | 46, 61, 62, 110, 119, 120, 143, 158 |
| `nvlink_nvswitch` | Interconnect/fabric errors, NVLink5 | 74, 136, 137, 144–150, 155 |
| `thermal_power` | Power/cooling issues | 54 |
| `driver_software` | Driver/software-level errors | 8, 11, 14, 16, 25, 32, 37–41, 43–45, 56, 60, 65–69, 73, 78, 93, 109, 121, 151, 154, 156–157, 159–161 |
| `unknown_uncategorized` | Fallback for unmapped codes | — |

67 real codes + fallback. `xid_reference.json` is not an official NVIDIA file. Built from
[NVIDIA's official Xid documentation](https://docs.nvidia.com/deploy/xid-errors/index.html)
and expanded using NVIDIA's official Xid catalog. The authoritative source is NVIDIA's docs
and `nverror.h` in [open-gpu-kernel-modules](https://github.com/NVIDIA/open-gpu-kernel-modules).

## Code style

- Comments on *why*, not *what* — skip obvious ones
- Commit messages: conventional commits prefix (`feat:`, `fix:`, `docs:`), lowercase,
  plain description of what changed — e.g. `fix incident grouping edge case`
- Casual tone is fine; no corporate language

## Git / GitHub workflow

- Commit after each meaningful milestone
- Push to GitHub after each commit (or at end of session)
- Python `.gitignore` in repo root

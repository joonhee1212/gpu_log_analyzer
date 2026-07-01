# NVIDIA Xid Catalog — Attribution & Provenance

`xid_reference.json` was built from NVIDIA's official Xid Catalog.

## Sources

| Resource | URL |
|---|---|
| Analyzing the Xid Catalog (docs page) | https://docs.nvidia.com/deploy/xid-errors/analyzing-xid-catalog.html |
| Xid-Catalog.xlsx (direct download) | https://docs.nvidia.com/deploy/xid-errors/_downloads/4586dadb59119a55d1e93a181caa4272/Xid-Catalog.xlsx |

## What was done

- Fields from the spreadsheet (Xid code, name, severity, recommended action) were mapped
  to the schema used in `xid_reference.json` (`name`, `category`, `severity`, `action`,
  `likely_cause`, `notes`).
- `likely_cause` and `notes` were expanded with operational context derived from the
  documentation page and cross-referenced against real log samples.
- `category` is a local taxonomy (not from NVIDIA) — see the category table in
  `PROJECT_BRIEF.md`.

## Disclaimer

This is not an official NVIDIA file. The authoritative source for Xid definitions is
NVIDIA's documentation and `nverror.h` in
[open-gpu-kernel-modules](https://github.com/NVIDIA/open-gpu-kernel-modules).

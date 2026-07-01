"""
Synthetic NVIDIA GPU log generator.

Two public modes:
  single_code_file(xid)       — one clean burst per Xid, good for regression tests
  kitchen_sink_file(xids)     — mixed multi-incident file with recurrence, like real samples

generate_fixtures(output_dir) — writes both modes to a directory for the test suite.
"""
from __future__ import annotations

import random
import uuid as _uuid_mod
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

TimestampFormat = Literal["iso8601", "syslog", "dmesg"]

_FORMATS: list[TimestampFormat] = ["iso8601", "syslog", "dmesg"]

# Xids that realistically produce a follow-up Xid 154 (GPU recovery action)
_FOLLOWED_BY_154 = {79, 80, 109, 119, 120}


# ---------------------------------------------------------------------------
# GPU identity
# ---------------------------------------------------------------------------

@dataclass
class GPU:
    pci_addr: str
    uuid: str
    host: str = "gpu-node-01"
    idx: int = 0   # used in "GPU0" / "GPU1" strings in NVRM messages


def make_gpu(
    pci_addr: str = "0000:01:00",
    idx: int = 0,
    host: str = "gpu-node-01",
    rng: random.Random | None = None,
) -> GPU:
    r = rng or random.Random()
    uid = f"GPU-{_uuid_mod.UUID(int=r.getrandbits(128))}"
    return GPU(pci_addr=pci_addr, uuid=uid, host=host, idx=idx)


# ---------------------------------------------------------------------------
# Timestamp cursor — handles sub-second ticking and all three formats
# ---------------------------------------------------------------------------

class _TimestampCursor:
    def __init__(self, base: datetime, fmt: TimestampFormat, dmesg_uptime: float = 142.881):
        self._ts = base
        self._fmt = fmt
        self._uptime = dmesg_uptime   # fake boot-relative seconds for dmesg

    def formatted(self) -> str:
        if self._fmt == "iso8601":
            return self._ts.strftime("%Y-%m-%dT%H:%M:%S.%f-06:00")
        elif self._fmt == "syslog":
            return self._ts.strftime("%b %d %H:%M:%S")
        else:
            return f"[{self._uptime:10.6f}]"

    def prefix(self, gpu: GPU) -> str:
        ts = self.formatted()
        if self._fmt == "dmesg":
            return f"{ts} "
        return f"{ts} {gpu.host} kernel: "

    def tick(self, us: int = 200) -> None:
        """Small advance between lines within a burst."""
        if self._fmt == "iso8601":
            self._ts += timedelta(microseconds=us)
        # syslog has 1-second resolution — don't advance within a burst
        self._uptime += us / 1_000_000

    def advance(self, seconds: int) -> None:
        """Larger advance between incidents."""
        self._ts += timedelta(seconds=seconds)
        self._uptime += seconds


# ---------------------------------------------------------------------------
# Per-Xid line content
# ---------------------------------------------------------------------------

def _xid_detail(xid: int, rng: random.Random) -> tuple[int | None, str | None, str]:
    """Return (pid, process_name, detail) for the Xid log line."""
    pid = rng.randint(1000, 65535)
    proc = rng.choice(["python3", "pt_main_thread", "nccl_comm", "triton", "cuda_app"])

    if xid == 6:
        return pid, proc, f"pid={pid}, name={proc}, MMU fault @ 0x{rng.randint(0, 0xffffffff):08x}"
    if xid == 8:
        return None, None, "GPU stopped processing"
    if xid == 11:
        return pid, proc, f"pid={pid}, name={proc}, PBDMA error"
    if xid == 13:
        return pid, proc, f"pid={pid}, name={proc}, Ch {rng.randint(0, 255):08x}, errorString CTX_WDT_TIMEOUT_ERROR, intr 00000000"
    if xid == 14:
        return pid, proc, f"pid={pid}, name={proc}, Ch {rng.randint(0, 255):08x}"
    if xid == 16:
        return None, None, "display engine error"
    if xid == 31:
        addr = rng.randint(0, 0xffffffffffff)
        engine = rng.choice(["GRAPHICS", "COPY", "NVDEC"])
        fault = rng.choice(["FAULT_PDE", "FAULT_PTE"])
        return (pid, proc,
                f"pid={pid}, name={proc}, Ch {rng.randint(0,255):08x}, intr 00000000. "
                f"MMU Fault: ENGINE {engine} VEID 0 faulted @ 0x{addr:016x}. "
                f"Fault is of type {fault} ACCESS_TYPE_VIRT_READ")
    if xid == 32:
        return pid, proc, f"pid={pid}, name={proc}, corrupted push buffer"
    if xid == 38:
        return None, None, "driver firmware error"
    if xid == 43:
        return pid, proc, f"pid={pid}, name={proc}"
    if xid == 45:
        return pid, proc, f"pid={pid}, name={proc}"
    if xid == 48:
        row = rng.randint(0, 0xffff)
        return None, None, f"Row 0x{row:08x}, Err 0x00000000"
    if xid == 54:
        return None, None, "power cable issue detected"
    if xid == 56:
        return None, None, "display driver error"
    if xid == 61:
        return None, None, "internal micro-controller error"
    if xid == 62:
        return None, None, "internal micro-controller halt"
    if xid == 63:
        row = rng.randint(0, 0xffff)
        return None, None, f"Row 0x{row:08x}"
    if xid == 64:
        row = rng.randint(0, 0xffff)
        return None, None, f"Row 0x{row:08x}, remap failed"
    if xid == 65:
        return pid, proc, f"pid={pid}, name={proc}, video processor exception"
    if xid == 68:
        return None, None, "NVDEC error"
    if xid == 73:
        return None, None, "NVENC error"
    if xid == 74:
        link = rng.randint(0, 11)
        return None, None, f"NVLink error on link {link}"
    if xid == 79:
        # real logs show pid present ~50% of the time
        if rng.random() < 0.5:
            return pid, proc, f"pid={pid}, name={proc}, GPU has fallen off the bus."
        return None, None, "GPU has fallen off the bus."
    if xid == 80:
        return None, None, "BAR1 mapping error"
    if xid == 94:
        return None, None, "contained ECC error"
    if xid == 95:
        return None, None, "uncontained ECC error"
    if xid == 109:
        return pid, proc, f"pid={pid}, name={proc}, context switch timeout"
    if xid == 119:
        return None, None, "GSP RPC timeout after 6s"
    if xid == 120:
        return None, None, "GSP error"
    if xid == 143:
        return None, None, "GSP assert failed"
    if xid in (144, 145):
        link = rng.randint(0, 17)
        severity = "FATAL" if xid == 144 else "NON_FATAL"
        return None, None, f"NVLink5 {severity} link event on link {link}, subcode NETIR_LINK_EVT"
    if xid == 154:
        return None, None, "GPU recovery action changed from 0x0 (None) to 0x1 (GPU Reset Required)"
    return None, None, f"error detail for Xid {xid}"


def _noise_lines(xid: int, gpu: GPU, rng: random.Random) -> list[str]:
    """
    Return body strings (no timestamp prefix) for the noise lines surrounding this Xid.
    Includes one candidate line that gets collapsed into 'message repeated N times'.
    The first element of the returned list that starts with 'message repeated' IS that collapse;
    all others are regular noise.
    """
    g = f"GPU{gpu.idx}"
    p = gpu.pci_addr

    if xid in (79, 80, 109):
        repeated_body = f"NVRM: {g} _threadNodeCheckTimeout: API_GPU_ATTACHED_SANITY_CHECK failed!"
        n = rng.randint(5, 15)
        rpc_seq_base = rng.randint(1700, 1800)
        lines = [
            f"NVRM: GPU {p}.0: GPU has fallen off the bus.",
            f"NVRM: GPU {p}.0: GPU serial number is 0.",
            f"NVRM: {g} krcRcAndNotifyAllChannels_IMPL: RC all channels for critical error {xid}.",
            repeated_body,
            f"message repeated {n} times: [ {repeated_body}]",
        ]
        for i in range(rng.randint(2, 4)):
            lines.append(
                f"NVRM: {g} _issueRpcAndWait: rpcSendMessage failed with status 0x0000000f "
                f"for fn 78 sequence {rpc_seq_base + i}!"
            )
        # abbreviated GSP RPC history table (just header + two rows, like the real samples)
        lines += [
            f"NVRM:     entry function                     sequence data0              data1"
            f"              ts_start           ts_end             duration during_incomplete_rpc",
            f"NVRM:      0    4099 POST_EVENT                     0 0x00000000000000a2 "
            f"0x0000000000000000 0x000649dd5d9881fc 0x000649dd5d988210     20us  ",
            f"NVRM:     -1    4124 GSP_LOCKDOWN_NOTICE            0 0x0000000000000000 "
            f"0x0000000000000000 0x000649dd5cc9224e 0x000649dd5cc9224e           ",
            f"nvidia-modeset: ERROR: GPU:0: Failed to query display engine channel state: "
            f"0x0000ca7e:6:0:0x0000000f",
        ]
        return lines

    if xid in (48, 63, 64, 94, 95):
        lines = [f"NVRM: {g} ECC error detected in DRAM"]
        if xid in (63, 64):
            lines.append(f"NVRM: {g} row remapping {'initiated' if xid == 63 else 'failed'}")
        if xid == 95:
            lines.append(f"NVRM: {g} error spanned multiple processes — cannot be contained")
        return lines

    if xid in (119, 120, 143):
        repeated_body = f"NVRM: {g} GSP-RM: error 0x{rng.randint(0, 0xffff):08x}"
        n = rng.randint(3, 8)
        return [
            f"NVRM: {g} _issueRpcAndWait: RPC timed out for fn 0x1234 after 6000ms",
            repeated_body,
            f"message repeated {n} times: [ {repeated_body}]",
            f"NVRM: {g} nvAssertFailedNoLog: Assertion failed: (status == NV_OK) @ rs_client.c:844",
        ]

    if xid in (74, 144, 145):
        link = rng.randint(0, 11)
        return [
            f"NVRM: {g} NVLink: link {link} transitioned to fault state",
            f"NVRM: {g} NVLink: DLPL error subcode 0x{rng.randint(0, 0xff):04x} on link {link}",
        ]

    if xid == 31:
        return [f"NVRM: {g} fault buffer: {rng.randint(1, 4)} unserviced fault(s)"]

    # generic fallback noise
    return [f"NVRM: {g} error context for Xid {xid}"]


# ---------------------------------------------------------------------------
# Burst assembly
# ---------------------------------------------------------------------------

def generate_burst(
    xid: int,
    gpu: GPU,
    cursor: _TimestampCursor,
    rng: random.Random,
    include_uuid_line: bool = True,
    add_154_followup: bool = True,
) -> list[str]:
    """Return a list of fully-formatted raw log lines for one Xid burst."""
    lines: list[str] = []

    def emit(body: str) -> None:
        lines.append(cursor.prefix(gpu) + body)
        cursor.tick(rng.randint(50, 800))

    if include_uuid_line:
        emit(f"NVRM: GPU at PCI:{gpu.pci_addr}: {gpu.uuid}")
        emit(f"NVRM: GPU Board Serial Number: 0")

    _pid, _proc, detail = _xid_detail(xid, rng)
    emit(f"NVRM: Xid (PCI:{gpu.pci_addr}): {xid}, {detail}")

    for noise_body in _noise_lines(xid, gpu, rng):
        emit(noise_body)

    if add_154_followup and xid in _FOLLOWED_BY_154:
        _, _, detail154 = _xid_detail(154, rng)
        emit(f"NVRM: Xid (PCI:{gpu.pci_addr}): 154, {detail154}")
        emit(f"NVRM: GPU{gpu.idx} nvAssertFailedNoLog: Assertion failed: "
             f"(status == NV_OK) || (status == NV_ERR_GPU_IN_FULLCHIP_RESET) @ rs_server.c:259")

    return lines


# ---------------------------------------------------------------------------
# Public modes
# ---------------------------------------------------------------------------

def single_code_file(
    xid: int,
    fmt: TimestampFormat = "iso8601",
    base_ts: datetime | None = None,
    rng: random.Random | None = None,
) -> str:
    """One clean Xid burst, deterministic by default (seeded by xid)."""
    rng = rng or random.Random(xid)
    base_ts = base_ts or datetime(2026, 3, 1, 10, 0, 0)
    gpu = make_gpu(rng=rng)
    cursor = _TimestampCursor(base_ts, fmt)
    lines = generate_burst(xid, gpu, cursor, rng)
    return "\n".join(lines) + "\n"


def kitchen_sink_file(
    xids: list[int] | None = None,
    seed: int = 42,
    base_ts: datetime | None = None,
) -> str:
    """
    Mixed multi-incident file on one GPU, with:
    - several different Xid categories
    - rotating timestamp formats between incidents
    - one deliberate recurrence (first Xid repeated at the end)
    """
    rng = random.Random(seed)
    base_ts = base_ts or datetime(2026, 3, 1, 8, 0, 0)

    if xids is None:
        # cross-category: page fault, bus fall, DBE, GSP timeout, NVLink, context switch
        xids = [31, 79, 48, 119, 74, 109]

    gpu = make_gpu(rng=rng)
    all_lines: list[str] = []
    cursor = _TimestampCursor(base_ts, "iso8601")

    for i, xid in enumerate(xids):
        cursor._fmt = _FORMATS[i % len(_FORMATS)]
        burst = generate_burst(xid, gpu, cursor, rng)
        all_lines.extend(burst)
        all_lines.append("")
        cursor.advance(rng.randint(3600, 21600))   # 1–6 hour gap between incidents

    # recurrence: repeat first Xid on the same GPU (cursor already advanced by last iteration)
    cursor._fmt = _FORMATS[len(xids) % len(_FORMATS)]
    recur_burst = generate_burst(xids[0], gpu, cursor, rng)
    all_lines.extend(recur_burst)

    return "\n".join(all_lines) + "\n"


# ---------------------------------------------------------------------------
# Fixture generation for test suite
# ---------------------------------------------------------------------------

_KITCHEN_SINK_XIDS = [31, 79, 48, 119, 74, 109]


def generate_fixtures(output_dir: str | Path) -> None:
    """
    Write one .log per real Xid code (rotating formats) plus kitchen_sink.log.
    All output is deterministic — same seed = same bytes.
    """
    from .classifier import load_xid_reference

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ref = load_xid_reference()
    real_codes = sorted(k for k in ref if k != 0)

    for xid in real_codes:
        fmt = _FORMATS[xid % len(_FORMATS)]
        content = single_code_file(xid, fmt=fmt, rng=random.Random(xid))
        (output_dir / f"xid_{xid:03d}.log").write_text(content)

    content = kitchen_sink_file(_KITCHEN_SINK_XIDS, seed=42)
    (output_dir / "kitchen_sink.log").write_text(content)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="gpu_log_generator",
        description="Generate synthetic NVIDIA GPU error logs for testing.",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_single = sub.add_parser("single", help="one burst per specified Xid code")
    p_single.add_argument("xids", metavar="XID", nargs="+", type=int)
    p_single.add_argument("--fmt", choices=_FORMATS, default="iso8601")
    p_single.add_argument("--output-dir", "-o", required=True)

    p_sink = sub.add_parser("kitchen-sink", help="mixed multi-incident file")
    p_sink.add_argument("--xids", nargs="+", type=int)
    p_sink.add_argument("--seed", type=int, default=42)
    p_sink.add_argument("--output", "-o")

    p_fix = sub.add_parser("fixtures", help="write all fixture files")
    p_fix.add_argument("--output-dir", "-o", required=True)

    args = parser.parse_args()

    if args.cmd == "single":
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for xid in args.xids:
            content = single_code_file(xid, fmt=args.fmt, rng=random.Random(xid))
            path = out / f"xid_{xid:03d}.log"
            path.write_text(content)
            print(f"wrote {path}", file=sys.stderr)

    elif args.cmd == "kitchen-sink":
        content = kitchen_sink_file(args.xids, seed=args.seed)
        if args.output:
            Path(args.output).write_text(content)
            print(f"wrote {args.output}", file=sys.stderr)
        else:
            print(content, end="")

    elif args.cmd == "fixtures":
        generate_fixtures(args.output_dir)
        out = Path(args.output_dir)
        n = len(list(out.glob("*.log")))
        print(f"wrote {n} fixture files to {args.output_dir}", file=sys.stderr)

    else:
        parser.print_help()

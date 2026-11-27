#!/usr/bin/env python3
"""VeriLoop Dual-Mode Experiment Sandbox (`./veriloop sandbox`).

Executes training or evaluation commands either directly in the local environment
(`--mode local`, zero-dependency fast path) or inside an isolated Docker container
(`--mode docker`, supporting NVIDIA GPU pass-through, read-only data volumes,
network-off isolation, timeout enforcement, and NaN/OOM failure detection).

Every run appends a tamper-checkable record to `<workspace>/out/sandbox_runs.jsonl`.
Zero external Python dependencies (stdlib only).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ANOMALY_PATTERNS = [
    ("CUDA_OOM", re.compile(r"CUDA out of memory|OutOfMemoryError", re.I)),
    ("NAN_OR_INF", re.compile(r"\b(loss\s*[=:]\s*nan|nan loss|loss is nan|\binf\b.*loss)\b", re.I)),
    ("TRACEBACK", re.compile(r"Traceback \(most recent call last\):")),
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    p = subprocess.run(["docker", "info"], capture_output=True, text=True)
    return p.returncode == 0


def build_docker_command(
    ws: Path,
    cmd_str: str,
    image: str,
    gpus: str,
    data_dir: Path | None,
    network_none: bool,
    memory: str,
    cpus: str,
) -> list[str]:
    args = [
        "docker", "run", "--rm",
        "-v", f"{ws}:/workspace:rw",
        "-w", "/workspace",
        "--memory", memory,
        "--cpus", cpus,
        "-e", "PYTHONUNBUFFERED=1",
    ]
    if gpus and gpus.lower() != "none":
        args.extend(["--gpus", gpus])
    if data_dir is not None:
        args.extend(["-v", f"{data_dir.resolve()}:/data:ro"])
    if network_none:
        args.extend(["--network", "none"])
    args.extend([image, "bash", "-lc", cmd_str])
    return args


def detect_anomalies(text: str) -> list[str]:
    hits = []
    for name, pat in ANOMALY_PATTERNS:
        if pat.search(text):
            hits.append(name)
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", "-w", default=".", help="Workspace mounted as /workspace (or cwd in local mode)")
    ap.add_argument("--mode", choices=("auto", "local", "docker"), default="local", help="Execution isolation mode (default: local)")
    ap.add_argument("--image", default="veriloop-gpu:latest", help="Docker image for --mode docker")
    ap.add_argument("--gpus", default="all", help="Docker --gpus flag (e.g., all, device=0, none)")
    ap.add_argument("--data-dir", default=None, help="Optional host dataset directory mounted read-only at /data in Docker")
    ap.add_argument("--network-none", action="store_true", help="Disable network inside Docker container")
    ap.add_argument("--memory", default="12g", help="Docker memory limit (default: 12g)")
    ap.add_argument("--cpus", default="4", help="Docker CPU limit (default: 4)")
    ap.add_argument("--timeout", type=int, default=3600, help="Hard timeout in seconds (default: 3600)")
    ap.add_argument("--log-out", default=None, help="Path to write combined stdout+stderr log (default: <ws>/out/sandbox_last.log)")
    ap.add_argument("--cmd", required=True, help="Shell command string to execute inside the workspace")
    ap.add_argument("--dry-run", action="store_true", help="Print resolved command and exit 0 without executing")
    ap.add_argument("--json", action="store_true", help="Emit structured JSON summary")
    a = ap.parse_args()

    ws = Path(a.workspace).resolve()
    ws.mkdir(parents=True, exist_ok=True)
    out_dir = ws / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(a.log_out).resolve() if a.log_out else (out_dir / "sandbox_last.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_mode = a.mode
    if resolved_mode == "auto":
        resolved_mode = "docker" if docker_available() else "local"

    data_dir = Path(a.data_dir).resolve() if a.data_dir else None
    if resolved_mode == "docker":
        exec_cmd = build_docker_command(ws, a.cmd, a.image, a.gpus, data_dir, a.network_none, a.memory, a.cpus)
        cwd = None
    else:
        exec_cmd = ["bash", "-lc", a.cmd]
        cwd = str(ws)

    if a.dry_run:
        res = {
            "dry_run": True,
            "mode": resolved_mode,
            "workspace": str(ws),
            "command": exec_cmd,
            "command_shell": shlex.join(exec_cmd),
            "timeout_s": a.timeout,
            "log_out": str(log_path),
        }
        print(json.dumps(res, indent=2) if a.json else f"SANDBOX DRY_RUN ({resolved_mode}): {res['command_shell']}")
        sys.exit(0)

    if resolved_mode == "docker" and not docker_available():
        print("ERROR: --mode docker requested but Docker daemon is unavailable.", file=sys.stderr)
        sys.exit(2)

    t0 = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            exec_cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=a.timeout,
        )
        rc = proc.returncode
        combined = proc.stdout or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = 124
        out_raw = exc.stdout or b""
        combined = out_raw.decode("utf-8", errors="replace") if isinstance(out_raw, bytes) else str(out_raw)
        combined += f"\n[VERILOOP_SANDBOX_TIMEOUT] Aborted after {a.timeout}s\n"

    elapsed = round(time.time() - t0, 2)
    log_path.write_text(combined, encoding="utf-8")
    anomalies = detect_anomalies(combined)
    if timed_out:
        anomalies.append("TIMEOUT")

    rec = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": resolved_mode,
        "workspace": str(ws),
        "cmd": a.cmd,
        "returncode": rc,
        "elapsed_s": elapsed,
        "timed_out": timed_out,
        "anomalies": anomalies,
        "log_path": str(log_path),
        "log_sha256": sha256_file(log_path),
        "log_bytes": log_path.stat().st_size,
    }
    with (out_dir / "sandbox_runs.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")

    if a.json:
        print(json.dumps(rec, indent=2))
    else:
        status = "OK" if (rc == 0 and not anomalies) else "FAILED"
        print(
            f"SANDBOX {status} | mode={resolved_mode} rc={rc} elapsed={elapsed}s "
            f"anomalies={anomalies or 'none'} log={log_path} sha256={rec['log_sha256'][:12]}"
        )
    sys.exit(0 if rc == 0 else rc)


if __name__ == "__main__":
    main()

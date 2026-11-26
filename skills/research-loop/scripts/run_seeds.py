#!/usr/bin/env python3
"""Single-GPU sequential multi-seed runner with crash resume & live log health watchdog.

Stdlib only. Designed for 1x 8GB GPU workstations (never runs two GPU jobs in
parallel, reads local stdout/logs directly — no W&B required).

  run_seeds.py --name beauty_noid --seeds 0,1,2 --out-dir out/ \\
               --cmd "python3 train.py --seed {seed}" \\
               [--complete-marker "DONE"] [--loss-regex "loss\\s+([0-9.]+)"] \\
               [--max-loss-ratio 3.0] [--kill-on-nan]

Features:
  - Sequential execution (1 GPU job at a time)
  - Crash-safe resume: skips seeds with existing `.done` marker & non-empty log
  - Live log watchdog: detects NaN/Inf, CUDA OOM, and loss explosion (>max-loss-ratio)
    and terminates doomed runs early to save overnight GPU hours
  - Emits `<name>_summary.json` with per-seed SHA-256, wall time, status, and exit code
"""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime

NAN_INF_RE = re.compile(r"\b(?:loss|grad|val|metric)[^=\n:]{0,20}[:=\s]+(?:nan|inf|-inf)\b|\bNaN\b", re.I)
OOM_RE = re.compile(r"CUDA out of memory|OutOfMemoryError|CUBLAS_STATUS_ALLOC_FAILED", re.I)


def sha256_file(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_one_seed(cmd_str, log_path, done_path, complete_marker=None,
                 loss_re=None, max_loss_ratio=3.0, kill_on_nan=True):
    if os.path.exists(done_path) and os.path.exists(log_path) and os.path.getsize(log_path) > 0:
        return {
            "status": "SKIPPED_DONE",
            "exit_code": 0,
            "seconds": 0.0,
            "log": log_path,
            "sha256": sha256_file(log_path),
            "reason": "existing .done marker",
        }

    t0 = time.monotonic()
    first_loss = None
    abort_reason = None
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)

    proc = subprocess.Popen(
        cmd_str,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    with open(log_path, "w") as lf:
        lf.write(f"# CMD: {cmd_str}\n# STARTED: {datetime.now().isoformat(timespec='seconds')}\n")
        lf.flush()
        for line in proc.stdout:
            lf.write(line)
            lf.flush()
            if OOM_RE.search(line):
                abort_reason = f"OOM detected: {line.strip()[:120]}"
                proc.terminate()
                break
            if kill_on_nan and NAN_INF_RE.search(line):
                abort_reason = f"NaN/Inf detected: {line.strip()[:120]}"
                proc.terminate()
                break
            if loss_re:
                m = loss_re.search(line)
                if m:
                    try:
                        val = float(m.group(1))
                        if math.isnan(val) or math.isinf(val):
                            abort_reason = f"Loss NaN/Inf: {line.strip()[:120]}"
                            proc.terminate()
                            break
                        if first_loss is None and val > 0:
                            first_loss = val
                        elif first_loss is not None and max_loss_ratio > 0 and val > first_loss * max_loss_ratio:
                            abort_reason = f"Loss exploded ({val:.4f} > {max_loss_ratio}x initial {first_loss:.4f})"
                            proc.terminate()
                            break
                    except ValueError:
                        pass
        try:
            rc = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = proc.wait()

        elapsed = round(time.monotonic() - t0, 3)
        lf.write(f"# FINISHED: {datetime.now().isoformat(timespec='seconds')} rc={rc} elapsed={elapsed}s\n")
        if abort_reason:
            lf.write(f"# WATCHDOG_ABORT: {abort_reason}\n")

    status = "OK"
    if abort_reason:
        status = "WATCHDOG_ABORT"
    elif rc != 0:
        status = "FAILED"
    elif complete_marker:
        txt = open(log_path, "r", errors="replace").read()
        if complete_marker not in txt:
            status = "INCOMPLETE_MARKER"
            abort_reason = f"missing complete marker '{complete_marker}'"

    if status == "OK":
        with open(done_path, "w") as df:
            df.write(f"ok {datetime.now().isoformat(timespec='seconds')}\n")

    return {
        "status": status,
        "exit_code": rc,
        "seconds": elapsed,
        "log": log_path,
        "sha256": sha256_file(log_path),
        "reason": abort_reason or "",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="run family stem")
    ap.add_argument("--seeds", default="0,1,2", help="comma-separated seeds (default 0,1,2)")
    ap.add_argument("--out-dir", required=True, help="output directory for logs & summary")
    ap.add_argument("--cmd", required=True, help="shell command template containing {seed}")
    ap.add_argument("--complete-marker", help="optional required completion string in log")
    ap.add_argument("--loss-regex", default=r"\bloss\s*[:= ]\s*([+-]?\d+(?:\.\d+)?|nan|inf)",
                    help="regex with capture group 1 for loss monitoring")
    ap.add_argument("--max-loss-ratio", type=float, default=3.0,
                    help="abort if loss exceeds this multiple of first logged loss (0 disables)")
    ap.add_argument("--no-kill-on-nan", action="store_true")
    ap.add_argument("--stop-on-fail", action="store_true", help="stop remaining seeds after a failure")
    a = ap.parse_args()

    seeds = [s.strip() for s in a.seeds.split(",") if s.strip()]
    os.makedirs(a.out_dir, exist_ok=True)
    loss_re = re.compile(a.loss_regex, re.I) if a.loss_regex else None

    results = {}
    any_bad = False
    for s in seeds:
        cmd_str = a.cmd.replace("{seed}", s)
        log_path = os.path.join(a.out_dir, f"{a.name}_s{s}.txt")
        done_path = os.path.join(a.out_dir, f"{a.name}_s{s}.done")
        res = run_one_seed(
            cmd_str, log_path, done_path,
            complete_marker=a.complete_marker,
            loss_re=loss_re,
            max_loss_ratio=a.max_loss_ratio,
            kill_on_nan=not a.no_kill_on_nan,
        )
        results[s] = res
        print(f"[{a.name} s={s}] {res['status']} ({res['seconds']}s) {res['reason']}")
        if res["status"] not in ("OK", "SKIPPED_DONE"):
            any_bad = True
            if a.stop_on_fail:
                break

    summary_path = os.path.join(a.out_dir, f"{a.name}_summary.json")
    summary = {
        "name": a.name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seeds_requested": seeds,
        "all_ok": not any_bad,
        "runs": results,
    }
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=1, ensure_ascii=False)
    print(f"summary written: {summary_path}")
    sys.exit(1 if any_bad else 0)


if __name__ == "__main__":
    main()

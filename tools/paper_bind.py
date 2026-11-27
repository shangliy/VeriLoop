#!/usr/bin/env python3
"""VeriLoop Paper-Bind: Zero-Dependency Experiment Log -> LaTeX & Figure Binder.

Directly ingests raw experiment outputs from:
  1. TensorBoard binary event files (`events.out.tfevents.*` via stdlib TFRecord+protobuf decoder)
  2. Weights & Biases local run dirs (`wandb-summary.json`, `wandb-history.jsonl`, `config.yaml`)
  3. CSV / TSV / JSONL / JSON metric logs

Automatically aggregates across seeds (mean +/- std + 95% Student-t CI) and emits
100% provenance-bound paper artifacts with SHA-256 source manifests:
  - `bound_metrics.txt`       : canonical log traceable by `trace_numbers.py`
  - `bound_macros.tex`        : LaTeX `\\newcommand` macros (never hand-copy numbers!)
  - `bound_table.tex`         : Booktabs LaTeX comparison table (bold best per metric)
  - `provenance_manifest.json`: SHA-256 binding from every source log to every emitted value
  - `bound_curves.pdf` / `bound_bars.pdf`: Okabe-Ito publication-grade vector figures (if matplotlib available)

Usage:
  paper_bind.py --inputs runs/ [--metrics val_acc test_acc val_loss] [--out-dir paper/bound]
"""
import argparse
import csv
import hashlib
import json
import math
import os
import re
import statistics
import struct
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Two-sided 95% Student-t critical values for df = 1..30 (stdlib, no scipy needed)
T_CRIT_95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
    9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
    23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}

OKABE_ITO = ["#0072B2", "#009E73", "#E69F00", "#CC79A7", "#D55E00", "#56B4E9", "#1F2937"]
SEED_RE = re.compile(r"(?:^|[_/\-.])(?:seed|s)[=_-]?(\d+)(?:$|[_/\-.])", re.I)
META_COLS = {"method", "model", "arm", "run", "name", "experiment", "seed", "step", "epoch", "iter", "iteration", "timestamp", "_step", "_runtime", "_timestamp"}


def sha256_file(fp: Path) -> str:
    h = hashlib.sha256()
    with fp.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ==================== PURE-STDLIB TENSORBOARD TFRECORD + PROTOBUF CODEC ====================

def _encode_varint(n: int) -> bytes:
    out = bytearray()
    n &= (1 << 64) - 1
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _decode_varint(buf: bytes, pos: int) -> tuple[int, int]:
    shift = 0
    val = 0
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, pos
        shift += 7
    raise ValueError("Truncated varint")


def _iter_proto_fields(buf: bytes):
    """Minimal protobuf wire decoder yielding (field_no, wire_type, value)."""
    pos = 0
    n = len(buf)
    while pos < n:
        tag, pos = _decode_varint(buf, pos)
        fno, wtype = tag >> 3, tag & 0x7
        if wtype == 0:
            v, pos = _decode_varint(buf, pos)
            yield fno, wtype, v
        elif wtype == 1:
            if pos + 8 > n:
                break
            yield fno, wtype, buf[pos:pos + 8]
            pos += 8
        elif wtype == 2:
            ln, pos = _decode_varint(buf, pos)
            if pos + ln > n:
                break
            yield fno, wtype, buf[pos:pos + ln]
            pos += ln
        elif wtype == 5:
            if pos + 4 > n:
                break
            yield fno, wtype, buf[pos:pos + 4]
            pos += 4
        else:
            break


def _masked_crc32c(data: bytes) -> int:
    # Castagnoli CRC32C in pure Python for valid TFRecord framing
    poly = 0x82F63B78
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ poly if (crc & 1) else (crc >> 1)
    crc ^= 0xFFFFFFFF
    return (((crc >> 15) | (crc << 17)) + 0xA282EAD8) & 0xFFFFFFFF


def write_tfevents_scalars(out_path: Path, records: list[tuple[int, str, float]], wall_time: float = 1700000000.0):
    """Write standard TensorBoard `events.out.tfevents.*` scalar records using stdlib only."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as fh:
        for step, tag, val in records:
            tag_b = tag.encode("utf-8")
            # Summary.Value: field 1 = tag (bytes), field 2 = simple_value (float32)
            sv = (
                _encode_varint((1 << 3) | 2) + _encode_varint(len(tag_b)) + tag_b
                + _encode_varint((2 << 3) | 5) + struct.pack("<f", float(val))
            )
            # Summary: field 1 = value (Summary.Value)
            summary = _encode_varint((1 << 3) | 2) + _encode_varint(len(sv)) + sv
            # Event: field 1 = wall_time (double), field 2 = step (int64), field 5 = summary
            ev = (
                _encode_varint((1 << 3) | 1) + struct.pack("<d", wall_time + step)
                + _encode_varint((2 << 3) | 0) + _encode_varint(int(step))
                + _encode_varint((5 << 3) | 2) + _encode_varint(len(summary)) + summary
            )
            ln_b = struct.pack("<Q", len(ev))
            fh.write(ln_b)
            fh.write(struct.pack("<I", _masked_crc32c(ln_b)))
            fh.write(ev)
            fh.write(struct.pack("<I", _masked_crc32c(ev)))


def parse_tfevents_file(fp: Path) -> list[tuple[int, str, float]]:
    """Read (step, tag, value) scalar tuples from a TensorBoard tfevents file (stdlib-only)."""
    raw = fp.read_bytes()
    pos = 0
    n = len(raw)
    out = []
    while pos + 12 <= n:
        rec_len = struct.unpack("<Q", raw[pos:pos + 8])[0]
        pos += 12  # length (8) + length_crc (4)
        if pos + rec_len + 4 > n:
            break
        payload = raw[pos:pos + rec_len]
        pos += rec_len + 4  # data + data_crc
        step = 0
        summaries = []
        try:
            for fno, wtype, val in _iter_proto_fields(payload):
                if fno == 2 and wtype == 0:
                    step = int(val)
                elif fno == 5 and wtype == 2:
                    summaries.append(val)
        except Exception:
            continue
        for sbuf in summaries:
            for sfno, swtype, sval in _iter_proto_fields(sbuf):
                if sfno == 1 and swtype == 2:
                    tag = ""
                    scalar = None
                    for vfno, vwtype, vval in _iter_proto_fields(sval):
                        if vfno == 1 and vwtype == 2:
                            tag = vval.decode("utf-8", errors="replace")
                        elif vfno == 2 and vwtype == 5:
                            scalar = struct.unpack("<f", vval)[0]
                        elif vfno == 8 and vwtype == 2 and scalar is None:
                            # TensorProto scalar fallback: field 4 (tensor_content) or field 5 (float_val)
                            for tfno, twtype, tval in _iter_proto_fields(vval):
                                if tfno == 4 and twtype == 2 and len(tval) == 4:
                                    scalar = struct.unpack("<f", tval)[0]
                                elif tfno == 5 and twtype == 5:
                                    scalar = struct.unpack("<f", tval)[0]
                    if tag and scalar is not None and math.isfinite(scalar):
                        out.append((step, tag, float(scalar)))
    return out


# ==================== MULTI-SOURCE RUN INGESTION ====================

def _infer_method_and_seed(path: Path) -> tuple[str, str]:
    parts = [p for p in path.parts[-4:]]
    joined = "/".join(parts)
    sm = SEED_RE.search(joined)
    seed = sm.group(1) if sm else "0"
    # Choose nearest meaningful directory or stem that is not generic
    generic = {"files", "logs", "out", "outputs", "tb", "tensorboard", "wandb", "runs", "metrics", "history", "summary"}
    candidates = [path.stem] + [p.name for p in list(path.parents)[:3]]
    method = "model"
    for c in candidates:
        low = c.lower()
        if low.startswith("events.out.tfevents") or low.startswith("wandb-") or low.startswith("run-"):
            continue
        cleaned = re.sub(r"[_-]?(?:seed|s)[=_-]?\d+$", "", c, flags=re.I).strip("_-")
        if cleaned and cleaned.lower() not in generic:
            method = cleaned
            break
    return method, seed


def _safe_float(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def ingest_sources(input_paths: list[Path]) -> tuple[list[dict], list[dict]]:
    """Return (records, source_manifest). Each record: {method, seed, step, metric, value, source, format}."""
    records = []
    sources = []
    seen_files = set()

    def discover_files(p: Path):
        if p.is_file():
            return [p]
        out = []
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in sorted(dirs) if not d.startswith(".") and d != "__pycache__"]
            for fn in sorted(files):
                out.append(Path(root) / fn)
        return out

    all_files = []
    for ip in input_paths:
        all_files.extend(discover_files(ip))

    for fp in all_files:
        rp = fp.resolve()
        if rp in seen_files:
            continue
        name = fp.name
        ext = fp.suffix.lower()

        # 1. TensorBoard tfevents
        if "tfevents" in name:
            seen_files.add(rp)
            pts = parse_tfevents_file(fp)
            if pts:
                method, seed = _infer_method_and_seed(fp)
                sources.append({"path": str(fp), "format": "tensorboard", "sha256": sha256_file(fp), "points": len(pts)})
                for step, tag, val in pts:
                    records.append({
                        "method": method, "seed": seed, "step": step,
                        "metric": tag.replace("/", "_"), "value": val,
                        "source": str(fp), "format": "tensorboard",
                    })
            continue

        # 2. W&B summary JSON or history JSONL
        if name == "wandb-summary.json":
            seen_files.add(rp)
            try:
                data = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            method, seed = _infer_method_and_seed(fp)
            # Check sibling wandb-metadata.json or config.json for explicit method/seed
            cfg_p = fp.parent / "config.json"
            if cfg_p.is_file():
                try:
                    cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
                    method = str(cfg.get("method") or cfg.get("model") or method)
                    if "seed" in cfg:
                        seed = str(cfg["seed"])
                except Exception:
                    pass
            if isinstance(data, dict):
                method = str(data.get("method") or data.get("model") or method)
                if "seed" in data:
                    seed = str(data["seed"])
                step = int(_safe_float(data.get("_step")) or _safe_float(data.get("epoch")) or 0)
                cnt = 0
                for k, v in data.items():
                    if k.startswith("_") or k.lower() in META_COLS:
                        continue
                    fv = _safe_float(v)
                    if fv is not None:
                        records.append({
                            "method": method, "seed": seed, "step": step,
                            "metric": k, "value": fv, "source": str(fp), "format": "wandb_summary",
                        })
                        cnt += 1
                if cnt:
                    sources.append({"path": str(fp), "format": "wandb_summary", "sha256": sha256_file(fp), "points": cnt})
            continue

        if name == "wandb-history.jsonl" or ext == ".jsonl":
            seen_files.add(rp)
            method_def, seed_def = _infer_method_and_seed(fp)
            fmt = "wandb_history" if name == "wandb-history.jsonl" else "jsonl"
            cnt = 0
            for idx, line in enumerate(fp.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if not isinstance(row, dict):
                    continue
                method = str(row.get("method") or row.get("model") or row.get("arm") or method_def)
                seed = str(row.get("seed") if row.get("seed") is not None else seed_def)
                step = int(_safe_float(row.get("_step")) or _safe_float(row.get("step")) or _safe_float(row.get("epoch")) or idx)
                for k, v in row.items():
                    if k.startswith("_") or k.lower() in META_COLS:
                        continue
                    fv = _safe_float(v)
                    if fv is not None:
                        records.append({
                            "method": method, "seed": seed, "step": step,
                            "metric": k, "value": fv, "source": str(fp), "format": fmt,
                        })
                        cnt += 1
            if cnt:
                sources.append({"path": str(fp), "format": fmt, "sha256": sha256_file(fp), "points": cnt})
            continue

        # 3. CSV / TSV
        if ext in (".csv", ".tsv"):
            seen_files.add(rp)
            delim = "\t" if ext == ".tsv" else ","
            method_def, seed_def = _infer_method_and_seed(fp)
            cnt = 0
            try:
                with fp.open("r", encoding="utf-8", errors="replace", newline="") as fh:
                    reader = csv.DictReader(fh, delimiter=delim)
                    if not reader.fieldnames:
                        continue
                    for idx, row in enumerate(reader, 1):
                        method = str(row.get("method") or row.get("model") or row.get("arm") or row.get("run") or method_def).strip()
                        seed = str(row.get("seed") if row.get("seed") not in (None, "") else seed_def).strip()
                        step_raw = row.get("step") or row.get("epoch") or row.get("iter") or idx
                        step = int(_safe_float(step_raw) or idx)
                        for k, v in row.items():
                            if not k or k.strip().lower() in META_COLS:
                                continue
                            fv = _safe_float(v)
                            if fv is not None:
                                records.append({
                                    "method": method, "seed": seed, "step": step,
                                    "metric": k.strip(), "value": fv, "source": str(fp), "format": ext.lstrip("."),
                                })
                                cnt += 1
            except Exception:
                continue
            if cnt:
                sources.append({"path": str(fp), "format": ext.lstrip("."), "sha256": sha256_file(fp), "points": cnt})

    return records, sources


# ==================== AGGREGATION + LATEX/FIGURE GENERATION ====================

def aggregate_records(records: list[dict], metrics_filter: list[str], step_agg: str = "last") -> tuple[dict, dict]:
    """Return (summary_table, curve_series).

    summary_table[(method, metric)] = {n_seeds, mean, std, ci_lo, ci_hi, seeds: {seed: val}, sources: [...]}
    curve_series[(method, metric)][step] = [vals across seeds]
    """
    # Per (method, metric, seed) collect (step, val)
    per_seed = defaultdict(list)
    per_seed_src = defaultdict(set)
    curve_by_seed = defaultdict(lambda: defaultdict(dict))  # (method, metric) -> step -> {seed: val}

    all_metrics = sorted({r["metric"] for r in records})
    target_metrics = [m for m in metrics_filter if m in all_metrics] if metrics_filter else all_metrics

    for r in records:
        if r["metric"] not in target_metrics:
            continue
        k = (r["method"], r["metric"], r["seed"])
        per_seed[k].append((r["step"], r["value"]))
        per_seed_src[(r["method"], r["metric"])].add(r["source"])
        curve_by_seed[(r["method"], r["metric"])][r["step"]][r["seed"]] = r["value"]

    grouped = defaultdict(dict)
    for (method, metric, seed), pts in per_seed.items():
        pts.sort(key=lambda x: x[0])
        if step_agg == "max":
            val = max(v for _, v in pts)
        elif step_agg == "min":
            val = min(v for _, v in pts)
        else:
            val = pts[-1][1]
        grouped[(method, metric)][seed] = val

    summary = {}
    for (method, metric), seed_map in sorted(grouped.items()):
        vals = [seed_map[s] for s in sorted(seed_map)]
        n = len(vals)
        mean = statistics.mean(vals)
        std = statistics.stdev(vals) if n > 1 else 0.0
        if n > 1:
            tcrit = T_CRIT_95.get(n - 1, 1.96)
            half = tcrit * (std / math.sqrt(n))
        else:
            half = 0.0
        summary[(method, metric)] = {
            "method": method,
            "metric": metric,
            "n_seeds": n,
            "mean": mean,
            "std": std,
            "ci_lo": mean - half,
            "ci_hi": mean + half,
            "per_seed": {s: seed_map[s] for s in sorted(seed_map)},
            "sources": sorted(per_seed_src[(method, metric)]),
        }

    curves = {}
    for (method, metric), step_map in sorted(curve_by_seed.items()):
        if len(step_map) >= 2:
            pts = []
            for st in sorted(step_map):
                vs = list(step_map[st].values())
                m = statistics.mean(vs)
                sd = statistics.stdev(vs) if len(vs) > 1 else 0.0
                pts.append((st, m, sd, len(vs)))
            curves[(method, metric)] = pts
    return summary, curves


_DIGIT_WORDS = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five", "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine"}


def _macro_name(method: str, metric: str, suffix: str = "", prefix: str = "vl") -> str:
    # Preserve backwards-compatible method naming (e.g. M0_Linear -> MLinear) while spelling out digits in metric names (e.g. ndcg10 vs ndcg20)
    metric_spelled = re.sub(r"\d", lambda m: " " + _DIGIT_WORDS[m.group(0)] + " ", metric)
    clean = re.sub(r"[^A-Za-z]+", " ", f"{method} {metric_spelled} {suffix}").title().replace(" ", "")
    return f"\\{prefix}{clean}"


def _is_lower_better(metric: str) -> bool:
    low = metric.lower()
    return any(tok in low for tok in ("loss", "err", "error", "ece", "nll", "brier", "mse", "mae", "rmse", "ppl", "perplexity", "fpr", "latency", "time"))


def write_outputs(summary: dict, curves: dict, sources: list[dict], out_dir: Path, decimals: int = 4, curve_metric: str | None = None, macro_prefix: str = "vl"):
    out_dir.mkdir(parents=True, exist_ok=True)
    methods = sorted({k[0] for k in summary})
    metrics = sorted({k[1] for k in summary})
    fmt = f"{{:.{decimals}f}}"

    # 1. bound_metrics.txt (canonical byte-deterministic log 100% traceable by trace_numbers.py)
    log_lines = [
        "# VeriLoop Paper-Bind Canonical Metrics Log (auto-generated; do not edit by hand)",
        f"# sources={len(sources)} methods={len(methods)} metrics={len(metrics)}",
    ]
    for s in sources:
        log_lines.append(f"SOURCE format={s['format']} sha256={s['sha256'][:16]} points={s['points']} path={s['path']}")
    log_lines.append("")
    for m in methods:
        for met in metrics:
            if (m, met) not in summary:
                continue
            r = summary[(m, met)]
            mean_s = fmt.format(r["mean"])
            std_s = fmt.format(r["std"])
            lo_s = fmt.format(r["ci_lo"])
            hi_s = fmt.format(r["ci_hi"])
            pct_note = ""
            if 0.0 <= r["mean"] <= 1.0 and not _is_lower_better(met):
                pct_note = f" | pct={r['mean']*100:.2f}±{r['std']*100:.2f}%"
            seed_str = " ".join(f"s{sk}={fmt.format(sv)}" for sk, sv in r["per_seed"].items())
            log_lines.append(
                f"BOUND {m} | {met} | n={r['n_seeds']} | {mean_s}±{std_s} [{lo_s},{hi_s}]{pct_note} | {seed_str}"
            )
    log_lines.append("COMPLETED_OK")
    (out_dir / "bound_metrics.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    # 2. bound_macros.tex
    macro_lines = [
        "% Auto-generated by VeriLoop paper_bind.py — DO NOT EDIT BY HAND",
        "% Every macro traces verbatim to bound_metrics.txt",
    ]
    macro_map = {}
    for (m, met), r in sorted(summary.items()):
        nm_pm = _macro_name(m, met, prefix=macro_prefix)
        nm_mean = _macro_name(m, met, "Mean", prefix=macro_prefix)
        nm_ci = _macro_name(m, met, "CI", prefix=macro_prefix)
        val_pm = f"{fmt.format(r['mean'])}$\\pm${fmt.format(r['std'])}"
        val_mean = fmt.format(r["mean"])
        val_ci = f"[{fmt.format(r['ci_lo'])}, {fmt.format(r['ci_hi'])}]"
        macro_lines.append(f"\\newcommand{{{nm_pm}}}{{{val_pm}}}")
        macro_lines.append(f"\\newcommand{{{nm_mean}}}{{{val_mean}}}")
        macro_lines.append(f"\\newcommand{{{nm_ci}}}{{{val_ci}}}")
        macro_map[nm_pm] = {"method": m, "metric": met, "value": val_pm, "sources": r["sources"]}
    (out_dir / "bound_macros.tex").write_text("\n".join(macro_lines) + "\n", encoding="utf-8")

    # 3. bound_table.tex (Booktabs)
    best_by_metric = {}
    for met in metrics:
        cands = [(summary[(m, met)]["mean"], m) for m in methods if (m, met) in summary]
        if cands:
            best_by_metric[met] = min(cands)[1] if _is_lower_better(met) else max(cands)[1]

    col_spec = "l" + "c" * (len(metrics) + 1)
    hdr_metrics = " & ".join(f"\\textbf{{{met.replace('_', ' ').title()}}}" for met in metrics)
    tbl_lines = [
        "% Auto-generated by VeriLoop paper_bind.py — 100% bound to raw logs",
        "\\begin{table}[t]",
        "\\centering",
        "\\caption{\\textbf{Multi-seed experiment results automatically bound from raw execution logs (mean $\\pm$ std).}}",
        "\\label{tab:bound_results}",
        "\\footnotesize",
        f"\\begin{{tabular}}{{{col_spec}}}",
        "\\toprule",
        f"\\textbf{{Method}} & \\textbf{{Seeds}} & {hdr_metrics} \\\\",
        "\\midrule",
    ]
    for m in methods:
        n_seeds = max((summary[(m, met)]["n_seeds"] for met in metrics if (m, met) in summary), default=0)
        cells = []
        for met in metrics:
            if (m, met) not in summary:
                cells.append("---")
                continue
            r = summary[(m, met)]
            cell = f"{fmt.format(r['mean'])}$\\pm${fmt.format(r['std'])}"
            if best_by_metric.get(met) == m:
                cell = f"\\textbf{{{cell}}}"
            cells.append(cell)
        m_tex = m.replace("_", "\\_")
        tbl_lines.append(f"{m_tex} & {n_seeds} & {' & '.join(cells)} \\\\")
    tbl_lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}"])
    (out_dir / "bound_table.tex").write_text("\n".join(tbl_lines) + "\n", encoding="utf-8")

    # 4. provenance_manifest.json
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "bound_metrics_sha256": sha256_file(out_dir / "bound_metrics.txt"),
        "sources": sources,
        "summary": {f"{m}::{met}": r for (m, met), r in summary.items()},
        "macros": macro_map,
    }
    (out_dir / "provenance_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # 5. Publication-grade Okabe-Ito vector PDF figures (optional matplotlib)
    figs_written = []
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        plt.rcParams.update({
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 8.0,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.5,
            "legend.frameon": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        })

        # Bar chart with 95% CI error bars
        if methods and metrics:
            plot_metrics = metrics[:4]
            fig, ax = plt.subplots(figsize=(6.4, 2.7))
            x = np.arange(len(plot_metrics))
            w = 0.78 / max(1, len(methods))
            for idx, m in enumerate(methods):
                means = [summary[(m, met)]["mean"] if (m, met) in summary else 0.0 for met in plot_metrics]
                errs = [
                    (summary[(m, met)]["ci_hi"] - summary[(m, met)]["mean"]) if (m, met) in summary else 0.0
                    for met in plot_metrics
                ]
                offset = (idx - (len(methods) - 1) / 2.0) * w
                bars = ax.bar(
                    x + offset, means, w * 0.92, yerr=errs, capsize=2.5,
                    label=m, color=OKABE_ITO[idx % len(OKABE_ITO)],
                    edgecolor="#1F2937", linewidth=0.55, error_kw={"linewidth": 0.8, "ecolor": "#1F2937"},
                )
                for b, mv in zip(bars, means):
                    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + max(errs) * 0.12 + 0.01,
                            f"{mv:.3f}", ha="center", va="bottom", fontsize=6.2, fontweight="bold")
            ax.set_xticks(x)
            ax.set_xticklabels([met.replace("_", " ").title() for met in plot_metrics])
            if ax.get_ylim()[1] <= 1.25:
                from matplotlib.ticker import FormatStrFormatter
                ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
            ax.set_ylabel("Metric Value (mean ± 95% CI)")
            ax.grid(axis="y", linestyle=":", alpha=0.4)
            ax.set_axisbelow(True)
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=min(4, len(methods)))
            fig.tight_layout(pad=0.35)
            fig.savefig(out_dir / "bound_bars.pdf", bbox_inches="tight")
            plt.close(fig)
            figs_written.append("bound_bars.pdf")

        # Multi-seed training curves (shaded mean +/- std)
        if curves:
            avail_cmetrics = sorted({k[1] for k in curves})
            chosen = curve_metric if (curve_metric in avail_cmetrics) else avail_cmetrics[0]
            fig, ax = plt.subplots(figsize=(6.4, 2.7))
            for idx, m in enumerate(methods):
                pts = curves.get((m, chosen))
                if not pts:
                    continue
                xs = np.array([p[0] for p in pts], dtype=float)
                ys = np.array([p[1] for p in pts], dtype=float)
                sds = np.array([p[2] for p in pts], dtype=float)
                c = OKABE_ITO[idx % len(OKABE_ITO)]
                ax.plot(xs, ys, label=m, color=c, linewidth=1.6)
                if np.any(sds > 0):
                    ax.fill_between(xs, ys - sds, ys + sds, color=c, alpha=0.18, linewidth=0)
            ax.set_xlabel("Training Step / Epoch")
            ax.set_ylabel(chosen.replace("_", " ").title())
            ax.grid(linestyle=":", alpha=0.4)
            ax.legend(loc="best")
            fig.tight_layout(pad=0.35)
            fig.savefig(out_dir / "bound_curves.pdf", bbox_inches="tight")
            plt.close(fig)
            figs_written.append("bound_curves.pdf")
    except ImportError:
        pass

    return {
        "out_dir": str(out_dir),
        "methods": methods,
        "metrics": metrics,
        "sources_count": len(sources),
        "figures": figs_written,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inputs", nargs="+", required=True, help="Experiment log directories/files (TensorBoard tfevents, W&B runs, CSV/TSV/JSONL)")
    ap.add_argument("--metrics", nargs="*", default=[], help="Optional subset of metric names to include")
    ap.add_argument("--step-agg", choices=("last", "max", "min"), default="last", help="Per-seed reduction across steps (default: last)")
    ap.add_argument("--curve-metric", default=None, help="Metric name to plot in bound_curves.pdf")
    ap.add_argument("--decimals", type=int, default=4, help="Decimal places in macros/tables (default: 4)")
    ap.add_argument("--macro-prefix", default="vl", help="LaTeX macro prefix (default: vl; use distinct prefixes for multi-dataset papers)")
    ap.add_argument("--out-dir", default="paper/bound", help="Output directory for bound_metrics.txt, macros, tables, figures, manifest")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    in_paths = [Path(p).resolve() for p in a.inputs]
    missing = [str(p) for p in in_paths if not p.exists()]
    if missing:
        print(f"Input path(s) not found: {missing}", file=sys.stderr)
        sys.exit(2)

    records, sources = ingest_sources(in_paths)
    if not records:
        print("No numeric experiment metrics discovered under --inputs", file=sys.stderr)
        sys.exit(1)

    summary, curves = aggregate_records(records, a.metrics, step_agg=a.step_agg)
    if not summary:
        print("No metrics matched --metrics filter", file=sys.stderr)
        sys.exit(1)

    res = write_outputs(summary, curves, sources, Path(a.out_dir).resolve(), decimals=a.decimals, curve_metric=a.curve_metric, macro_prefix=a.macro_prefix)
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        print(
            f"PAPER_BIND OK | sources={res['sources_count']} | methods={len(res['methods'])} | "
            f"metrics={len(res['metrics'])} | figs={res['figures']} | out={res['out_dir']}"
        )


if __name__ == "__main__":
    main()

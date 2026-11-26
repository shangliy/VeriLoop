#!/usr/bin/env python3
"""Render a self-contained static HTML dashboard from claims.json, audits/, and budget_ledger.json.

Source files on disk remain the single source of truth; the HTML is strictly a
verifiable read-only view carrying source paths, SHA-256 hashes, and timestamp
in its header. Stdlib only; escapes all untrusted text safely.

  render_board.py -w <workspace> [--budget budget_ledger.json] [--out board.html]
"""
import argparse
import hashlib
import html
import json
import os
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import claims  # noqa: E402


def sha256_file(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


STATUS_COLORS = {
    "supported": "#16a34a",
    "partial": "#d97706",
    "pilot": "#2563eb",
    "proposed": "#6b7280",
    "unsupported": "#dc2626",
    "refuted": "#991b1b",
    "killed": "#374151",
}


def render_html(ws, budget_path=None):
    ws = os.path.abspath(ws)
    claims_fp = claims.path(ws)
    db = claims.load(ws)
    sources = []
    if os.path.exists(claims_fp):
        sources.append((claims_fp, sha256_file(claims_fp)))

    audits_dir = os.path.join(ws, "audits")
    audit_files = []
    if os.path.isdir(audits_dir):
        for f in sorted(os.listdir(audits_dir)):
            if f.endswith(".md"):
                fp = os.path.join(audits_dir, f)
                audit_files.append((f, fp, sha256_file(fp)))
                sources.append((fp, sha256_file(fp)))

    budget_html = ""
    if budget_path and os.path.exists(budget_path):
        sources.append((os.path.abspath(budget_path), sha256_file(budget_path)))
        bdb = json.load(open(budget_path))
        spent = float(bdb.get("spent_usd", 0.0))
        limit = float(bdb.get("limit_usd", 50.0))
        pct = min(100.0, (spent / limit * 100.0) if limit > 0 else 0.0)
        budget_html = (
            f"<section class='card'><h2>API Budget</h2>"
            f"<p><strong>${spent:.4f}</strong> / ${limit:.2f} ({pct:.1f}%) — "
            f"{len(bdb.get('calls', []))} calls</p>"
            f"<div class='bar'><div class='fill' style='width:{pct:.1f}%'></div></div></section>"
        )

    cards = []
    for cid, c in db.get("claims", {}).items():
        res = claims.gates(c, ws)
        color = STATUS_COLORS.get(c["status"], "#6b7280")
        gate_pills = []
        for gname, ok, detail in res:
            cls = "pill-ok" if ok else "pill-fail"
            tip = html.escape(detail or "pass")
            gate_pills.append(f"<span class='pill {cls}' title='{tip}'>{html.escape(gname)}</span>")

        hist_rows = []
        for h in c.get("history", []):
            seq = f"#{h['seq']} " if "seq" in h else ""
            hist_rows.append(
                f"<li><code>{html.escape(seq + h.get('at', ''))}</code> — "
                f"{html.escape(h.get('text', ''))} <em>(why: {html.escape(h.get('why', ''))})</em></li>"
            )

        ev_rows = []
        for e in c.get("evidence", []):
            role = e.get("role") or ("baseline" if e.get("arm") else "method")
            arm = f" [{e['arm']}]" if e.get("arm") else ""
            h12 = e.get("sha256", "")[:12] or "unhashed"
            ev_rows.append(
                f"<tr><td>{html.escape(role + arm)}</td>"
                f"<td><code>{html.escape(os.path.basename(e.get('log', '')))}</code></td>"
                f"<td>{html.escape(str(e.get('seeds', '-')))}</td>"
                f"<td>{html.escape(str(e.get('selected_on', '-')))}</td>"
                f"<td><code>{html.escape(h12)}</code></td></tr>"
            )

        cards.append(
            f"<section class='card'>"
            f"<div class='row'><h2>{html.escape(cid)}</h2>"
            f"<span class='badge' style='background:{color}'>{html.escape(c['status'])}</span></div>"
            f"<p class='claim-text'>{html.escape(c.get('text', ''))}</p>"
            f"<p class='meta'><strong>Metric:</strong> {html.escape(str(c.get('metric', '-')))} | "
            f"<strong>Scope:</strong> {html.escape(str(c.get('scope', '-')))} | "
            f"<strong>Kill if:</strong> {html.escape(str(c.get('kill', '-')))}</p>"
            f"<div class='gates'>{''.join(gate_pills)}</div>"
            f"<h3>Wording History ({len(c.get('history', [])) - 1} revisions)</h3><ul>{''.join(hist_rows)}</ul>"
            f"<h3>Attached Evidence ({len(ev_rows)})</h3>"
            f"<table><thead><tr><th>Role / Arm</th><th>Log</th><th>Seeds</th><th>Selected On</th><th>SHA-256</th></tr></thead>"
            f"<tbody>{''.join(ev_rows)}</tbody></table></section>"
        )

    audit_list = "".join(
        f"<li><code>{html.escape(name)}</code> (sha256: <code>{h[:12]}</code>)</li>"
        for name, _fp, h in audit_files
    ) or "<li>(none)</li>"

    source_rows = "".join(
        f"<li><code>{html.escape(p)}</code> — sha256 <code>{h[:16]}</code></li>"
        for p, h in sources
    )

    gen_at = datetime.now().isoformat(timespec="seconds")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Research Loop Board — {html.escape(os.path.basename(ws))}</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 1040px; margin: 24px auto; padding: 0 16px; color: #111827; background: #f9fafb; }}
header {{ background: #111827; color: #f9fafb; padding: 16px 20px; border-radius: 8px; margin-bottom: 18px; }}
header code {{ color: #93c5fd; }}
.card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px 20px; margin-bottom: 16px; }}
.row {{ display: flex; align-items: center; justify-content: space-between; }}
.badge {{ color: #fff; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; text-transform: uppercase; }}
.claim-text {{ font-size: 15px; line-height: 1.5; }}
.meta {{ font-size: 13px; color: #4b5563; }}
.gates {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 14px; }}
.pill {{ font-size: 12px; padding: 3px 8px; border-radius: 4px; font-weight: 500; }}
.pill-ok {{ background: #dcfce7; color: #166534; }}
.pill-fail {{ background: #fee2e2; color: #991b1b; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 6px; }}
th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid #e5e7eb; }}
.bar {{ height: 10px; background: #e5e7eb; border-radius: 5px; overflow: hidden; }}
.fill {{ height: 100%; background: #2563eb; }}
</style>
</head>
<body>
<header>
  <h1>Research Loop Claim Board</h1>
  <p>Generated: <code>{html.escape(gen_at)}</code> | Workspace: <code>{html.escape(ws)}</code></p>
  <details><summary>Verifiable Source Provenance ({len(sources)} files)</summary><ul>{source_rows}</ul></details>
</header>
{budget_html}
{''.join(cards) or '<section class="card"><p>No claims registered.</p></section>'}
<section class="card"><h2>Audit Reports</h2><ul>{audit_list}</ul></section>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-w", "--workspace", required=True)
    ap.add_argument("--budget", help="optional path to budget_ledger.json")
    ap.add_argument("--out", help="output HTML path (default: <workspace>/board.html)")
    a = ap.parse_args()
    out_fp = a.out or os.path.join(a.workspace, "board.html")
    content = render_html(a.workspace, budget_path=a.budget)
    os.makedirs(os.path.dirname(os.path.abspath(out_fp)), exist_ok=True)
    with open(out_fp, "w") as fh:
        fh.write(content)
    print(f"rendered {out_fp} ({len(content):,} bytes)")


if __name__ == "__main__":
    main()

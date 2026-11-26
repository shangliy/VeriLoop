#!/usr/bin/env python3
"""VeriLoop Interactive Local Web Review UI (stdlib-only, zero npm/Node dependencies).

Builds a synchronized split-pane audit inspector linking:
  - Left pane : Manuscript source (.tex / .md) with inline clickable highlights for
                traced numbers (green), untraced/sign/wrong-log defects (red/orange),
                citations (blue/purple with API & abstract status), and prose lint warnings.
  - Right pane: Raw execution logs, Python AST code files, BibTeX + real fetched abstracts,
                and full SHA-256 provenance manifest. Clicking ANY number, citation, or
                defect jumps directly to and highlights the exact source file & line!

Modes:
  1. Export self-contained static HTML (works offline in any browser):
     review_ui.py --report paper/sec/3_experiments.tex --logs paper/out/stats_summary.txt --out review.html
  2. Serve live on localhost:
     review_ui.py --report ... --logs ... --serve --port 8765
"""
import argparse
import hashlib
import html
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RL_SCRIPTS = REPO_ROOT / "skills/research-loop/scripts"
BP_SCRIPTS = REPO_ROOT / "skills/bestpaper-writing/scripts"


def _sha256(fp: Path) -> str:
    h = hashlib.sha256()
    with fp.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_text_files(paths: list[Path], exts: set[str], max_files: int = 30, max_bytes: int = 200_000) -> dict[str, dict]:
    out = {}
    for p in paths:
        if not p.exists():
            continue
        files = [p] if p.is_file() else sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in exts)
        for f in files:
            if len(out) >= max_files:
                break
            try:
                if f.stat().st_size > max_bytes:
                    continue
                key = str(f)
                out[key] = {
                    "path": key,
                    "name": f.name,
                    "sha256": _sha256(f)[:16],
                    "lines": f.read_text(encoding="utf-8", errors="replace").splitlines(),
                }
            except OSError:
                continue
    return out


def collect_audit_bundle(
    report_paths: list[Path],
    log_paths: list[Path],
    script_paths: list[Path],
    bib_path: Path | None = None,
    online_cites: bool = False,
) -> dict:
    """Run trace_numbers, audit_code, citation_audit, and check_draft and assemble UI JSON payload."""
    # Combine multi-file reports cleanly with section markers
    report_lines = []
    report_files_meta = []
    for rp in report_paths:
        report_files_meta.append({"path": str(rp), "name": rp.name, "sha256": _sha256(rp)[:16]})
        txt = rp.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(report_paths) > 1:
            report_lines.append(f"% ===== FILE: {rp.name} =====")
        report_lines.extend(txt)

    combined_text = "\n".join(report_lines) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=report_paths[0].suffix or ".tex", delete=False, encoding="utf-8") as tf:
        tf.write(combined_text)
        tmp_rep = Path(tf.name)

    try:
        # 1. trace_numbers.py (detailed per-number trace via Python import for exact traced sources!)
        sys.path.insert(0, str(RL_SCRIPTS))
        import trace_numbers as tn  # noqa: E402

        lfiles = tn.log_files([str(p) for p in log_paths], str(tmp_rep))
        idx_u, idx_s, line_keys, _ = tn.build_index(lfiles, 50_000_000)

        # Also run CLI JSON for official defect arrays
        cmd_tr = [sys.executable, str(RL_SCRIPTS / "trace_numbers.py"), str(tmp_rep), "--json"]
        for lp in log_paths:
            cmd_tr.extend(["--logs", str(lp)])
        p_tr = subprocess.run(cmd_tr, capture_output=True, text=True)
        tr_json = json.loads(p_tr.stdout) if p_tr.stdout.strip().startswith("{") else {}

        # Build per-line traced token -> exact (abs_file, line_no) map for clickable jump-to-log!
        number_links = []
        in_code = False
        for ln, line in enumerate(report_lines, 1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            for raw_tok, sign, val, dec, pct in tn.numbers_in(line, allow_prose_polarity=True):
                if dec < 3:
                    continue
                sh, uh = tn.lookup(idx_u, idx_s, sign, val, min(dec, tn.MAX_D), pct)
                tok_display = raw_tok + ("%" if pct else "")
                if sh:
                    first_f, first_ln = sorted(sh.items())[0]
                    number_links.append({
                        "line": ln, "token": tok_display, "status": "TRACED",
                        "target_file": str(Path(first_f).resolve()), "target_line": first_ln,
                        "all_sources": [f"{Path(f).name}:{l}" for f, l in sorted(sh.items())[:4]],
                    })
                elif uh:
                    first_f, first_ln = sorted(uh.items())[0]
                    number_links.append({
                        "line": ln, "token": tok_display, "status": "SIGN_MISMATCH",
                        "target_file": str(Path(first_f).resolve()), "target_line": first_ln,
                        "all_sources": [f"{Path(f).name}:{l}" for f, l in sorted(uh.items())[:4]],
                    })
                else:
                    number_links.append({
                        "line": ln, "token": tok_display, "status": "UNTRACED",
                        "target_file": "", "target_line": 0, "all_sources": [],
                    })

        # 2. audit_code.py
        ast_json = {"counts": {"HIGH": 0, "MEDIUM": 0, "INFO": 0}, "findings": []}
        if script_paths:
            cmd_ast = [sys.executable, str(RL_SCRIPTS / "audit_code.py"), "--report", str(tmp_rep), "--json", "--strict"]
            for sp in script_paths:
                cmd_ast.extend(["--scripts", str(sp)])
            p_ast = subprocess.run(cmd_ast, capture_output=True, text=True)
            if p_ast.stdout.strip().startswith("{"):
                ast_json = json.loads(p_ast.stdout)

        # 3. citation_audit.py
        cite_json = {"pairs_count": 0, "issues_count": 0, "warnings_count": 0, "issues": [], "warnings": [], "pairs": []}
        cmd_cit = [sys.executable, str(RL_SCRIPTS / "citation_audit.py"), str(tmp_rep), "--json"]
        if bib_path and bib_path.is_file():
            cmd_cit.extend(["--bib", str(bib_path)])
        if online_cites:
            cmd_cit.extend(["--online", "--check-claims"])
        p_cit = subprocess.run(cmd_cit, capture_output=True, text=True)
        if p_cit.stdout.strip().startswith("{"):
            cite_json = json.loads(p_cit.stdout)

        # 4. check_draft.py (bestpaper prose lint)
        lint_lines = []
        if (BP_SCRIPTS / "check_draft.py").is_file():
            p_lint = subprocess.run(
                [sys.executable, str(BP_SCRIPTS / "check_draft.py"), *[str(r) for r in report_paths]],
                capture_output=True, text=True,
            )
            for l in p_lint.stdout.splitlines():
                if l.startswith(("ERROR", "WARN", "NOTE")):
                    lint_lines.append(l)

        log_files_map = _collect_text_files(
            [Path(f).resolve() for f in lfiles],
            {".txt", ".log", ".out", ".json", ".jsonl", ".csv", ".tsv", ".md", ""},
        )
        code_files_map = _collect_text_files(
            [p.resolve() for p in script_paths],
            {".py", ".sh"},
        )
    finally:
        tmp_rep.unlink(missing_ok=True)

    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "report_files": report_files_meta,
        "report_lines": report_lines,
        "number_links": number_links,
        "trace_summary": {
            "traced": tr_json.get("traced", 0),
            "untraced": len(tr_json.get("untraced", [])),
            "sign_mismatches": len(tr_json.get("sign_mismatches", [])),
            "wrong_logs": len(tr_json.get("wrong_logs", [])),
            "unpaired_pairs": len(tr_json.get("unpaired_pairs", [])),
        },
        "ast": ast_json,
        "citations": cite_json,
        "lint_messages": lint_lines,
        "logs": log_files_map,
        "code": code_files_map,
    }


def render_review_html(bundle: dict) -> str:
    """Render a self-contained interactive split-pane HTML review workbench."""
    payload_json = json.dumps(bundle, ensure_ascii=False).replace("</", "<\\/")
    ts = bundle["trace_summary"]
    ast_h = int((bundle.get("ast", {}).get("counts") or {}).get("HIGH", 0))
    cit_err = int(bundle.get("citations", {}).get("issues_count", 0))
    blocked = (ts["untraced"] + ts["sign_mismatches"] + ts["wrong_logs"] + ts["unpaired_pairs"] + ast_h + cit_err) > 0
    badge_cls = "badge-block" if blocked else "badge-pass"
    badge_txt = "HARD BLOCK" if blocked else "VERIFIED PASS"
    title_files = html.escape(", ".join(f["name"] for f in bundle["report_files"]))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>VeriLoop Interactive Review UI — {title_files}</title>
<style>
  :root {{
    --bg: #0f172a; --panel: #111827; --card: #1e293b; --border: #334155;
    --text: #e2e8f0; --muted: #94a3b8; --blue: #38bdf8; --green: #22c55e;
    --red: #ef4444; --amber: #f59e0b; --purple: #a78bfa;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; }}
  header {{ padding: 10px 16px; background: #020617; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }}
  header h1 {{ margin: 0; font-size: 15px; font-weight: 700; color: #fff; }}
  .badge {{ padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: .04em; }}
  .badge-pass {{ background: #14532d; color: #86efac; border: 1px solid #22c55e; }}
  .badge-block {{ background: #7f1d1d; color: #fecaca; border: 1px solid #ef4444; }}
  .stats {{ display: flex; gap: 10px; font-size: 12px; color: var(--muted); flex-wrap: wrap; }}
  .stat b {{ color: #fff; }}
  .stat.err b {{ color: #fca5a5; }}
  .stat.ok b {{ color: #86efac; }}
  .toolbar {{ margin-left: auto; display: flex; gap: 6px; }}
  .btn {{ background: var(--card); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 4px 10px; font-size: 12px; cursor: pointer; }}
  .btn.active, .btn:hover {{ border-color: var(--blue); color: #fff; }}
  main {{ flex: 1; display: grid; grid-template-columns: 1.08fr 0.92fr; min-height: 0; }}
  .pane {{ display: flex; flex-direction: column; min-height: 0; border-right: 1px solid var(--border); }}
  .pane:last-child {{ border-right: none; }}
  .pane-hdr {{ padding: 8px 12px; background: #0b1220; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 8px; font-size: 12px; }}
  .tabs {{ display: flex; gap: 4px; }}
  .tab {{ padding: 4px 10px; border-radius: 5px; cursor: pointer; color: var(--muted); border: 1px solid transparent; }}
  .tab.active {{ background: var(--card); color: #fff; border-color: var(--border); }}
  .scroll {{ flex: 1; overflow: auto; padding: 8px 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; line-height: 1.55; }}
  .code-line {{ display: flex; padding: 0 12px; white-space: pre-wrap; word-break: break-word; }}
  .code-line:hover {{ background: rgba(56,189,248,0.06); }}
  .code-line.hl-pulse {{ background: rgba(245,158,11,0.28) !important; outline: 1px solid var(--amber); }}
  .ln {{ width: 42px; flex-shrink: 0; color: #64748b; user-select: none; text-align: right; padding-right: 10px; }}
  .txt {{ flex: 1; }}
  .tok {{ padding: 0 4px; border-radius: 4px; cursor: pointer; font-weight: 600; display: inline-block; }}
  .tok-traced {{ background: rgba(34,197,94,0.18); color: #86efac; border: 1px solid rgba(34,197,94,0.45); }}
  .tok-untraced {{ background: rgba(239,68,68,0.24); color: #fecaca; border: 1px solid #ef4444; }}
  .tok-sign {{ background: rgba(245,158,11,0.25); color: #fde68a; border: 1px solid #f59e0b; }}
  .tok-cite {{ background: rgba(167,139,250,0.2); color: #ddd6fe; border: 1px solid rgba(167,139,250,0.5); }}
  .tok-cite-err {{ background: rgba(239,68,68,0.24); color: #fecaca; border: 1px solid #ef4444; }}
  .inspector-banner {{ padding: 8px 12px; background: #172554; border-bottom: 1px solid #1d4ed8; font-size: 12px; color: #dbeafe; display: none; }}
  .file-sel {{ background: var(--card); color: var(--text); border: 1px solid var(--border); border-radius: 5px; padding: 3px 8px; font-size: 12px; max-width: 260px; }}
  .card {{ margin: 8px 12px; padding: 10px 12px; background: var(--card); border: 1px solid var(--border); border-radius: 8px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 12.5px; }}
  .card h4 {{ margin: 0 0 6px; font-size: 13px; color: #fff; }}
  .card .meta {{ color: var(--muted); font-size: 11.5px; margin-bottom: 5px; }}
  .card .abs {{ color: #cbd5e1; line-height: 1.45; margin-top: 6px; font-size: 12px; }}
  .pill {{ display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 10.5px; font-weight: 700; margin-right: 6px; }}
  .pill-high {{ background: #7f1d1d; color: #fecaca; }}
  .pill-med {{ background: #78350f; color: #fde68a; }}
  .pill-ok {{ background: #14532d; color: #86efac; }}
  .search {{ background: var(--card); color: var(--text); border: 1px solid var(--border); border-radius: 5px; padding: 3px 8px; font-size: 12px; width: 170px; }}
</style>
</head>
<body>
<header>
  <h1>VeriLoop Review UI</h1>
  <span class="badge {badge_cls}">{badge_txt}</span>
  <div class="stats">
    <span class="stat ok">Traced: <b>{ts['traced']}</b></span>
    <span class="stat {'err' if ts['untraced'] else 'ok'}">Untraced: <b>{ts['untraced']}</b></span>
    <span class="stat {'err' if ts['sign_mismatches'] else 'ok'}">Sign: <b>{ts['sign_mismatches']}</b></span>
    <span class="stat {'err' if ast_h else 'ok'}">AST HIGH: <b>{ast_h}</b></span>
    <span class="stat {'err' if cit_err else 'ok'}">Cite Issues: <b>{cit_err}</b>/{bundle['citations'].get('pairs_count', 0)}</span>
    <span class="stat">Lint: <b>{len(bundle['lint_messages'])}</b></span>
  </div>
  <div class="toolbar">
    <button class="btn active" id="flt-all" onclick="setFilter('all')">All Lines</button>
    <button class="btn" id="flt-def" onclick="setFilter('defects')">Defects Only</button>
    <button class="btn" id="flt-num" onclick="setFilter('numbers')">Numbers &amp; Cites</button>
  </div>
</header>
<main>
  <section class="pane">
    <div class="pane-hdr">
      <strong>Manuscript:</strong> <span>{title_files}</span>
      <input class="search" id="ms-search" placeholder="Filter manuscript..." oninput="renderManuscript()" style="margin-left:auto">
    </div>
    <div class="scroll" id="ms-view"></div>
  </section>
  <section class="pane">
    <div class="pane-hdr">
      <div class="tabs">
        <div class="tab active" data-tab="logs" onclick="switchTab('logs')">Logs</div>
        <div class="tab" data-tab="code" onclick="switchTab('code')">Code &amp; AST</div>
        <div class="tab" data-tab="cites" onclick="switchTab('cites')">Citations</div>
        <div class="tab" data-tab="lint" onclick="switchTab('lint')">Lint &amp; SHA-256</div>
      </div>
      <select class="file-sel" id="file-sel" onchange="renderRight()" style="margin-left:auto"></select>
    </div>
    <div class="inspector-banner" id="banner"></div>
    <div class="scroll" id="right-view"></div>
  </section>
</main>
<script>
const BUNDLE = {payload_json};
let currentFilter = 'all';
let currentTab = 'logs';
let currentFile = Object.keys(BUNDLE.logs)[0] || '';
let highlightLine = 0;

function esc(s) {{
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

const linksByLine = {{}};
for (const nl of BUNDLE.number_links) {{
  (linksByLine[nl.line] ||= []).push(nl);
}}
const citesByLine = {{}};
for (const cp of (BUNDLE.citations.pairs || [])) {{
  (citesByLine[cp.line] ||= []).push(cp);
}}

function setFilter(f) {{
  currentFilter = f;
  for (const id of ['all','def','num']) document.getElementById('flt-'+id).classList.remove('active');
  document.getElementById(f==='all'?'flt-all':f==='defects'?'flt-def':'flt-num').classList.add('active');
  renderManuscript();
}}

function decorateLine(ln, rawText) {{
  let out = esc(rawText);
  const nls = linksByLine[ln] || [];
  const used = new Set();
  for (const nl of nls) {{
    if (used.has(nl.token)) continue;
    used.add(nl.token);
    const cls = nl.status === 'TRACED' ? 'tok-traced' : (nl.status === 'SIGN_MISMATCH' ? 'tok-sign' : 'tok-untraced');
    const tip = nl.status + (nl.all_sources.length ? ' -> ' + nl.all_sources.join(', ') : '');
    const idx = BUNDLE.number_links.indexOf(nl);
    const re = new RegExp('(?<![\\w.])' + nl.token.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&'));
    out = out.replace(re, `<span class="tok ${{cls}}" title="${{esc(tip)}}" onclick="jumpNumber(${{idx}})">${{esc(nl.token)}}</span>`);
  }}
  const cps = citesByLine[ln] || [];
  for (const cp of cps) {{
    const isErr = ['MISSING_BIB','UNRESOLVED_REFERENCE','TITLE_MISMATCH','AUTHOR_MISMATCH','YEAR_MISMATCH','RETRACTED_PAPER','UNRESOLVED_ARXIV'].includes(cp.status);
    const cls = isErr ? 'tok-cite-err' : 'tok-cite';
    const cidx = BUNDLE.citations.pairs.indexOf(cp);
    const safeKey = esc(cp.key);
    out = out.replace(safeKey, `<span class="tok ${{cls}}" title="${{esc(cp.status)}}" onclick="jumpCite(${{cidx}})">${{safeKey}}</span>`);
  }}
  return out;
}}

function renderManuscript() {{
  const q = (document.getElementById('ms-search').value || '').toLowerCase();
  const el = document.getElementById('ms-view');
  const rows = [];
  BUNDLE.report_lines.forEach((line, i) => {{
    const ln = i + 1;
    const nls = linksByLine[ln] || [];
    const cps = citesByLine[ln] || [];
    const hasDef = nls.some(x => x.status !== 'TRACED') || cps.some(x => x.status.includes('MISSING') || x.status.includes('MISMATCH') || x.status.includes('UNRESOLVED'));
    if (currentFilter === 'defects' && !hasDef) return;
    if (currentFilter === 'numbers' && !nls.length && !cps.length) return;
    if (q && !line.toLowerCase().includes(q)) return;
    rows.push(`<div class="code-line" id="ms-L${{ln}}"><span class="ln">${{ln}}</span><span class="txt">${{decorateLine(ln, line)}}</span></div>`);
  }});
  el.innerHTML = rows.join('') || '<div class="card">No matching lines under current filter.</div>';
}}

function showBanner(msg) {{
  const b = document.getElementById('banner');
  b.style.display = msg ? 'block' : 'none';
  b.innerHTML = msg;
}}

function jumpNumber(idx) {{
  const nl = BUNDLE.number_links[idx];
  if (!nl) return;
  if (nl.target_file && BUNDLE.logs[nl.target_file]) {{
    currentTab = 'logs';
    currentFile = nl.target_file;
    highlightLine = nl.target_line;
    updateTabs();
    showBanner(`<b>${{esc(nl.token)}}</b> [${{esc(nl.status)}}] &rarr; <code>${{esc(BUNDLE.logs[nl.target_file].name)}}:${{nl.target_line}}</code>`);
    renderRight();
  }} else {{
    currentTab = 'logs';
    updateTabs();
    showBanner(`<b>${{esc(nl.token)}}</b> [${{esc(nl.status)}}] — No matching log entry found in indexed logs.`);
    renderRight();
  }}
}}

function jumpCite(cidx) {{
  const cp = BUNDLE.citations.pairs[cidx];
  currentTab = 'cites';
  updateTabs();
  showBanner(`Citation <b>${{esc(cp.key)}}</b> (L${{cp.line}}) — Status: <b>${{esc(cp.status)}}</b>`);
  renderRight(cp.key);
}}

function jumpCode(file, ln) {{
  if (!BUNDLE.code[file]) return;
  currentTab = 'code';
  currentFile = file;
  highlightLine = ln;
  updateTabs();
  showBanner(`AST Finding &rarr; <code>${{esc(BUNDLE.code[file].name)}}:${{ln}}</code>`);
  renderRight();
}}

function switchTab(t) {{
  currentTab = t;
  highlightLine = 0;
  showBanner('');
  if (t === 'logs' && !BUNDLE.logs[currentFile]) currentFile = Object.keys(BUNDLE.logs)[0] || '';
  if (t === 'code' && !BUNDLE.code[currentFile]) currentFile = Object.keys(BUNDLE.code)[0] || '';
  updateTabs();
  renderRight();
}}

function updateTabs() {{
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x.dataset.tab === currentTab));
  const sel = document.getElementById('file-sel');
  if (currentTab === 'logs' || currentTab === 'code') {{
    const map = currentTab === 'logs' ? BUNDLE.logs : BUNDLE.code;
    sel.style.display = 'inline-block';
    sel.innerHTML = Object.entries(map).map(([k, v]) => `<option value="${{esc(k)}}" ${{k===currentFile?'selected':''}}>${{esc(v.name)}} (${{v.sha256.slice(0,8)}})</option>`).join('');
  }} else {{
    sel.style.display = 'none';
  }}
}}

function renderRight(focusCiteKey) {{
  const el = document.getElementById('right-view');
  const sel = document.getElementById('file-sel');
  if (currentTab === 'logs' || currentTab === 'code') {{
    if (sel.value) currentFile = sel.value;
    const map = currentTab === 'logs' ? BUNDLE.logs : BUNDLE.code;
    const fobj = map[currentFile];
    let htmlParts = [];
    if (currentTab === 'code' && (BUNDLE.ast.findings || []).length) {{
      htmlParts.push('<div class="card"><h4>Python AST Integrity Findings</h4>' +
        BUNDLE.ast.findings.map(f => {{
          const pcls = f.severity === 'HIGH' ? 'pill-high' : 'pill-med';
          const fullPath = Object.keys(BUNDLE.code).find(k => k.endsWith(f.file)) || f.file;
          return `<div style="margin:4px 0;cursor:pointer" onclick="jumpCode('${{esc(fullPath)}}', ${{f.line||1}})"><span class="pill ${{pcls}}">${{esc(f.severity)}}</span><code>${{esc(f.code)}}</code> ${{esc(f.file)}}:${{f.line}} — ${{esc(f.detail||'')}}</div>`;
        }}).join('') + '</div>');
    }}
    if (!fobj) {{
      htmlParts.push('<div class="card">No files loaded in this tab.</div>');
      el.innerHTML = htmlParts.join('');
      return;
    }}
    htmlParts.push(fobj.lines.map((l, i) => {{
      const ln = i + 1;
      const hl = ln === highlightLine ? ' hl-pulse' : '';
      return `<div class="code-line${{hl}}" id="r-L${{ln}}"><span class="ln">${{ln}}</span><span class="txt">${{esc(l)}}</span></div>`;
    }}).join(''));
    el.innerHTML = htmlParts.join('');
    if (highlightLine > 0) {{
      const target = document.getElementById('r-L' + highlightLine);
      if (target) target.scrollIntoView({{behavior: 'smooth', block: 'center'}});
    }}
  }} else if (currentTab === 'cites') {{
    const pairs = BUNDLE.citations.pairs || [];
    const seen = new Map();
    for (const p of pairs) {{ if (!seen.has(p.key)) seen.set(p.key, p); }}
    const items = Array.from(seen.values());
    if (focusCiteKey) items.sort((a,b) => (a.key===focusCiteKey?-1:b.key===focusCiteKey?1:0));
    el.innerHTML = items.map(p => {{
      const isErr = ['MISSING_BIB','UNRESOLVED_REFERENCE','TITLE_MISMATCH','AUTHOR_MISMATCH','YEAR_MISMATCH','RETRACTED_PAPER'].includes(p.status);
      const pcls = isErr ? 'pill-high' : 'pill-ok';
      const meta = p.online || {{}};
      const cva = p.claim_vs_abstract ? `<div class="meta"><b>Claim vs Abstract:</b> ${{esc(p.claim_vs_abstract.status)}} (overlap=${{p.claim_vs_abstract.overlap}})</div>` : '';
      const absHtml = meta.abstract ? `<div class="abs"><b>Fetched Real Abstract (${{esc(meta.source||'')}}):</b> ${{esc(meta.abstract.slice(0, 650))}}</div>` : '';
      return `<div class="card" style="${{p.key===focusCiteKey?'border-color:#38bdf8':''}}">
        <h4><span class="pill ${{pcls}}">${{esc(p.status)}}</span>${{esc(p.key)}}</h4>
        <div class="meta"><b>Bib Title:</b> ${{esc(p.bib_title || meta.title || '(none)')}} | <b>Year:</b> ${{esc(p.bib_year || meta.year || '-')}}</div>
        <div class="meta"><b>Manuscript Context (L${{p.line}}):</b> ${{esc(p.sentence)}}</div>
        ${{cva}}${{absHtml}}
      </div>`;
    }}).join('') || '<div class="card">No citations extracted.</div>';
  }} else {{
    const lintHtml = BUNDLE.lint_messages.length
      ? BUNDLE.lint_messages.map(m => `<div><code>${{esc(m)}}</code></div>`).join('')
      : '<span class="pill pill-ok">OK</span> 0 prose lint issues';
    const shaHtml = [
      ...BUNDLE.report_files.map(f => `<li><code>${{esc(f.name)}}</code> sha256=<code>${{esc(f.sha256)}}</code></li>`),
      ...Object.values(BUNDLE.logs).map(f => `<li><code>${{esc(f.name)}}</code> sha256=<code>${{esc(f.sha256)}}</code></li>`),
    ].join('');
    el.innerHTML = `<div class="card"><h4>Best-Paper Prose &amp; Figure Lint</h4>${{lintHtml}}</div>
      <div class="card"><h4>SHA-256 Artifact Provenance (${{esc(BUNDLE.generated_utc)}})</h4><ul>${{shaHtml}}</ul></div>`;
  }}
}}

updateTabs();
renderManuscript();
renderRight();
</script>
</body>
</html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", nargs="+", required=True, help="Manuscript .tex/.md file(s)")
    ap.add_argument("--logs", nargs="+", required=True, help="Raw log file(s) or directory(ies)")
    ap.add_argument("--scripts", nargs="*", default=[], help="Optional code file(s) or directory(ies) for AST audit")
    ap.add_argument("--bib", default=None, help="Optional .bib file")
    ap.add_argument("--online-cites", action="store_true", help="Also run online arXiv/Crossref/S2 citation verification")
    ap.add_argument("--out", default="review_ui.html", help="Output standalone HTML path")
    ap.add_argument("--serve", action="store_true", help="Start local HTTP server after generating HTML")
    ap.add_argument("--port", type=int, default=8765, help="Port for --serve (default: 8765)")
    a = ap.parse_args()

    reps = [Path(p).resolve() for p in a.report]
    logs = [Path(p).resolve() for p in a.logs]
    scripts = [Path(p).resolve() for p in a.scripts]
    bib = Path(a.bib).resolve() if a.bib else None

    bundle = collect_audit_bundle(reps, logs, scripts, bib_path=bib, online_cites=a.online_cites)
    out_html = render_review_html(bundle)
    out_path = Path(a.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out_html, encoding="utf-8")
    ts = bundle["trace_summary"]
    print(
        f"REVIEW_UI WRITTEN: {out_path} | traced={ts['traced']} untraced={ts['untraced']} "
        f"sign={ts['sign_mismatches']} cites={bundle['citations'].get('pairs_count', 0)}"
    )

    if a.serve:
        html_bytes = out_html.encode("utf-8")

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html_bytes)))
                self.end_headers()
                self.wfile.write(html_bytes)

            def log_message(self, fmt, *args):
                pass

        with socketserver.TCPServer(("127.0.0.1", a.port), Handler) as httpd:
            print(f"SERVING VeriLoop Review UI at http://127.0.0.1:{a.port} (Ctrl+C to stop)", flush=True)
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()

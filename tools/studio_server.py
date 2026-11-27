#!/usr/bin/env python3
"""VeriLoop Studio — Local Web Research Cockpit (`./veriloop studio`).

Unified zero-build-dependency Web GUI combining:
  1. Level-1 (Idea + Repo) & Level-2 (Reference Papers) Pipeline Launcher
  2. Real-time SSE Log Stream, 7-Stage Progress Stepper, Gate Traffic Lights & Formula<->Code Map
  3. Embedded Split-Pane Audit Workbench (`review_ui.html`) + 1-Click Hard-Gate Re-Audit

Zero external Python dependencies (stdlib `http.server` only).
Also supports `--export-html <path>` to emit a self-contained static Studio snapshot.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
STAGES = [
    ("ingest", "1. Ingest"),
    ("ideate_and_register", "2. Plan & Claims"),
    ("execute", "3. Execute"),
    ("bind", "4. Auto-Bind"),
    ("draft", "5. Draft"),
    ("gate_and_repair", "6. Hard Gate"),
    ("package_and_ui", "7. Audit & UI"),
]


def _read_json_safe(p: Path) -> dict | list | None:
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _read_jsonl_tail(p: Path, limit: int = 80) -> list[dict]:
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def collect_workspace_snapshot(ws: Path, active_job: dict | None = None) -> dict:
    state = _read_json_safe(ws / "state.json") or {"status": "idle", "stages": {}}
    gate = _read_json_safe(ws / "audits/veriloop_gate.json")
    pdf_audit = _read_json_safe(ws / "audits/pdf_audit.json")
    ingest = _read_json_safe(ws / "out/ingest_manifest.json")
    claims = _read_json_safe(ws / "claims.json")
    budget = _read_json_safe(ws / "audits/budget.json")
    events = _read_jsonl_tail(ws / "out/pipeline_events.jsonl", limit=100)
    sandbox_runs = _read_jsonl_tail(ws / "out/sandbox_runs.jsonl", limit=20)
    gate_trace = _read_jsonl_tail(ws / "out/gate_audit_trace.jsonl", limit=30)

    # Discover bound manifests (either paper/bound/provenance_manifest.json or paper/bound/*/provenance_manifest.json)
    bound_summaries = {}
    for mp in sorted((ws / "paper/bound").glob("**/provenance_manifest.json")) if (ws / "paper/bound").is_dir() else []:
        rel = mp.parent.name if mp.parent != (ws / "paper/bound") else "default"
        data = _read_json_safe(mp)
        if isinstance(data, dict) and data.get("summary"):
            bound_summaries[rel] = data["summary"]

    # If no v5 state.json exists yet, infer completed stages from existing audited artifacts
    if not state.get("stages"):
        inferred = {}
        if isinstance(ingest, dict) and (ingest.get("papers") or ingest.get("code_symbols")):
            inferred["ingest"] = {"status": "completed"}
        if isinstance(claims, dict) and claims.get("claims"):
            inferred["ideate_and_register"] = {"status": "completed"}
        if sandbox_runs or (ws / "out/trajectory_ledger.jsonl").is_file() or bound_summaries:
            inferred["execute"] = {"status": "completed"}
        if bound_summaries:
            inferred["bind"] = {"status": "completed"}
        if any((ws / "paper").glob("*.tex")) or (ws / "report/report.md").is_file():
            inferred["draft"] = {"status": "completed"}
        if isinstance(gate, dict):
            inferred["gate_and_repair"] = {"status": "blocked" if gate.get("blocked") else "completed"}
        if (ws / "review_ui.html").is_file() or isinstance(pdf_audit, dict):
            inferred["package_and_ui"] = {"status": "completed"}
        if inferred:
            state = {"status": "completed" if isinstance(gate, dict) and not gate.get("blocked") else "active", "stages": inferred}

    return {
        "workspace": str(ws),
        "workspace_name": ws.name,
        "active_job": active_job or {"running": False},
        "state": state,
        "gate": gate,
        "pdf_audit": pdf_audit,
        "ingest": {
            "papers": len(ingest.get("papers", [])) if isinstance(ingest, dict) else 0,
            "code_symbols": len(ingest.get("code_symbols", [])) if isinstance(ingest, dict) else 0,
            "alignments": (ingest.get("alignments", []) if isinstance(ingest, dict) else [])[:30],
            "unmatched": (ingest.get("unmatched_equations", []) if isinstance(ingest, dict) else [])[:15],
        },
        "claims": claims.get("claims", {}) if isinstance(claims, dict) else {},
        "budget": budget or {"total_usd": 0.0},
        "events": events,
        "sandbox_runs": sandbox_runs,
        "gate_trace": gate_trace,
        "bound_summaries": bound_summaries,
        "has_review_ui": (ws / "review_ui.html").is_file(),
    }


def render_studio_html(initial_snapshot: dict, static_mode: bool = False) -> str:
    snap_json = json.dumps(initial_snapshot, ensure_ascii=False).replace("</", "<\\/")
    stages_json = json.dumps(STAGES)
    ws_esc = html.escape(initial_snapshot["workspace"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>VeriLoop Studio — Verifiable Research Cockpit</title>
<style>
  :root {{
    --bg: #0b1220; --panel: #111a2e; --card: #16223a; --border: #253553;
    --text: #e2e8f0; --muted: #94a3b8; --blue: #38bdf8; --navy: #0072b2;
    --green: #10b981; --amber: #f59e0b; --red: #ef4444; --purple: #a78bfa;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }}
  header {{ display: flex; align-items: center; justify-content: space-between; padding: 14px 24px; background: linear-gradient(90deg, #0b2545, #004c78); border-bottom: 1px solid #1e3a5f; }}
  .brand {{ display: flex; align-items: center; gap: 12px; }}
  .brand h1 {{ margin: 0; font-size: 20px; font-weight: 800; letter-spacing: -0.3px; }}
  .brand .sub {{ font-size: 12px; color: #bae6fd; }}
  .ws-pill {{ font-family: monospace; font-size: 12px; background: rgba(255,255,255,0.1); padding: 6px 12px; border-radius: 999px; border: 1px solid rgba(147,197,253,0.35); }}
  nav.tabs {{ display: flex; gap: 6px; padding: 10px 24px 0; background: var(--panel); border-bottom: 1px solid var(--border); }}
  nav.tabs button {{ background: transparent; color: var(--muted); border: none; padding: 10px 16px; font-size: 13px; font-weight: 700; cursor: pointer; border-bottom: 3px solid transparent; }}
  nav.tabs button.active {{ color: #ffffff; border-bottom-color: var(--blue); }}
  main {{ padding: 20px 24px; max-width: 1480px; margin: 0 auto; }}
  .tab-pane {{ display: none; }}
  .tab-pane.active {{ display: block; }}
  .grid-2 {{ display: grid; grid-template-columns: 1.15fr 1fr; gap: 18px; }}
  .grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px; }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; }}
  .card h2 {{ margin: 0 0 12px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.6px; color: #93c5fd; }}
  .kpi {{ font-size: 24px; font-weight: 800; margin-top: 4px; }}
  .kpi.ok {{ color: var(--green); }} .kpi.warn {{ color: var(--amber); }} .kpi.bad {{ color: var(--red); }} .kpi.info {{ color: var(--blue); }}
  .kpi-lbl {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }}
  .stepper {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; margin-bottom: 18px; }}
  .step {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 10px; text-align: center; font-size: 12px; font-weight: 700; }}
  .step .st {{ font-size: 10px; margin-top: 4px; text-transform: uppercase; color: var(--muted); }}
  .step.completed {{ border-color: var(--green); background: rgba(16,185,129,0.12); }}
  .step.completed .st {{ color: #34d399; }}
  .step.running {{ border-color: var(--blue); background: rgba(56,189,248,0.14); }}
  .step.running .st {{ color: var(--blue); }}
  .step.failed, .step.blocked {{ border-color: var(--red); background: rgba(239,68,68,0.14); }}
  .step.failed .st, .step.blocked .st {{ color: #fca5a5; }}
  label {{ display: block; font-size: 12px; color: var(--muted); margin: 10px 0 4px; font-weight: 600; }}
  input, textarea, select {{ width: 100%; background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 9px 11px; font-size: 13px; font-family: inherit; }}
  textarea {{ min-height: 76px; resize: vertical; }}
  .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .btn {{ display: inline-flex; align-items: center; gap: 8px; padding: 10px 18px; border-radius: 8px; border: none; font-size: 13px; font-weight: 700; cursor: pointer; }}
  .btn-primary {{ background: #0284c7; color: #fff; }}
  .btn-primary:hover {{ background: #0369a1; }}
  .btn-green {{ background: #059669; color: #fff; }}
  .btn-row {{ display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }}
  .terminal {{ background: #070c16; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; height: 290px; overflow-y: auto; line-height: 1.5; }}
  .log-line {{ white-space: pre-wrap; margin-bottom: 3px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }}
  .badge.ok {{ background: rgba(16,185,129,0.18); color: #34d399; }}
  .badge.bad {{ background: rgba(239,68,68,0.2); color: #fca5a5; }}
  .badge.info {{ background: rgba(56,189,248,0.18); color: #7dd3fc; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th, td {{ text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); }}
  th {{ color: #93c5fd; font-size: 11px; text-transform: uppercase; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11.5px; color: #7dd3fc; }}
  iframe.review-frame {{ width: 100%; height: 740px; border: 1px solid var(--border); border-radius: 10px; background: #fff; }}
</style>
</head>
<body>
<header>
  <div class="brand">
    <svg width="32" height="32" viewBox="0 0 56 60"><path d="M 28 2 L 52 10 L 52 28 C 52 44 40 53 28 58 C 16 53 4 44 4 28 L 4 10 Z" fill="rgba(16,185,129,0.25)" stroke="#34d399" stroke-width="3"/><path d="M 17 29 L 25 37 L 40 20" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <div>
      <h1>VeriLoop Studio</h1>
      <div class="sub">Level-1 / Level-2 Autonomous Research Cockpit + Real-Time Hard-Gate Verification</div>
    </div>
  </div>
  <div class="ws-pill" id="ws-pill">{ws_esc}</div>
</header>

<nav class="tabs">
  <button class="active" onclick="switchTab('monitor', this)">1. Live Monitor &amp; Gates</button>
  <button onclick="switchTab('launcher', this)">2. Level-1 / Level-2 Launcher</button>
  <button onclick="switchTab('workbench', this)">3. Split-Pane Audit Workbench</button>
</nav>

<main>
  <!-- TAB 1: LIVE MONITOR -->
  <section id="tab-monitor" class="tab-pane active">
    <div class="stepper" id="stepper"></div>
    <div class="grid-4" id="kpi-row"></div>
    <div class="grid-2">
      <div class="card">
        <h2>Live Pipeline Events &amp; Stage Logs</h2>
        <div class="terminal" id="log-term"></div>
        <div class="btn-row">
          <button class="btn btn-green" onclick="triggerGate()" {"disabled" if static_mode else ""}>Re-Run Hard Gate (./veriloop gate)</button>
          <button class="btn btn-primary" onclick="refreshState()" {"disabled" if static_mode else ""}>Refresh Snapshot</button>
        </div>
      </div>
      <div class="card">
        <h2>Claims Ledger (G1–G7) &amp; Formula ↔ Code Map</h2>
        <div id="claims-box" style="margin-bottom:14px;"></div>
        <div id="align-box"></div>
      </div>
    </div>
    <div class="card" style="margin-top:18px;">
      <h2>Auto-Bound Experiment Metrics (paper_bind.py)</h2>
      <div id="metrics-box"></div>
    </div>
  </section>

  <!-- TAB 2: LAUNCHER -->
  <section id="tab-launcher" class="tab-pane">
    <div class="grid-2">
      <div class="card">
        <h2>Launch Verified Research Run</h2>
        <div class="row">
          <div>
            <label>Research Mode</label>
            <select id="f-level">
              <option value="1">Level 1 — Concrete Idea + Baseline Repo</option>
              <option value="2">Level 2 — Reference Papers → Gap → Innovation</option>
            </select>
          </div>
          <div>
            <label>Execution Sandbox</label>
            <select id="f-sandbox">
              <option value="local">Local Python (Zero-Dep Fast)</option>
              <option value="docker">Docker GPU Container (Isolated)</option>
            </select>
          </div>
        </div>
        <label>Seed Idea / Hypothesis (Level 1)</label>
        <textarea id="f-idea" placeholder="e.g., Post-hoc validation-fitted temperature scaling resolves underconfidence induced by Label Smoothing &amp; Mixup on CIFAR-10..."></textarea>
        <label>Reference arXiv IDs (Level 2 or citations, space-separated)</label>
        <input id="f-papers" placeholder="e.g., 1706.04599 1512.03385 1710.09412" />
        <label>Baseline Repo URL or Local Path</label>
        <input id="f-repo" placeholder="e.g., https://github.com/... or ./code" />
        <label>Experiment Command (optional)</label>
        <input id="f-cmd" placeholder="e.g., python3 code/train.py --seeds 42 43 44" />
        <div class="row">
          <div>
            <label>Executor Provider</label>
            <select id="f-provider">
              <option value="offline">Offline / Deterministic ($0)</option>
              <option value="claude-cli">Claude CLI (Anthropic)</option>
              <option value="codex-cli">Codex CLI (OpenAI)</option>
            </select>
          </div>
          <div>
            <label>Layer-2 Reviewer Provider</label>
            <select id="f-reviewer">
              <option value="none">Layer 1 Only ($0)</option>
              <option value="codex-cli">Codex CLI (Path-Isolated)</option>
              <option value="claude-cli">Claude CLI (Path-Isolated)</option>
            </select>
          </div>
        </div>
        <div class="row">
          <div>
            <label>Hard Budget Cap (USD)</label>
            <input id="f-budget" type="number" step="0.5" value="5.0" />
          </div>
          <div>
            <label>Online 3-API Citation Gate</label>
            <select id="f-online-cites">
              <option value="false">Offline BibTeX Only</option>
              <option value="true">Online (arXiv + Crossref + S2)</option>
            </select>
          </div>
        </div>
        <div class="btn-row">
          <button class="btn btn-primary" onclick="launchPipeline(false)" {"disabled" if static_mode else ""}>Launch Full Verified Pipeline</button>
          <button class="btn btn-green" onclick="launchPipeline(true)" {"disabled" if static_mode else ""}>Dry-Run Plan ($0)</button>
        </div>
        <div id="launch-msg" style="margin-top:10px; font-size:12px; color:#7dd3fc;"></div>
      </div>
      <div class="card">
        <h2>Why VeriLoop Studio vs. Black-Box Runners</h2>
        <p style="font-size:13px; color:var(--muted); line-height:1.6;">
          Unlike black-box idea-to-paper runners that only surface a final PDF after hours of unverified LLM execution,
          <strong>VeriLoop Studio</strong> enforces mechanical accountability at every stage:
        </p>
        <ul style="font-size:13px; color:var(--text); line-height:1.75; padding-left:18px;">
          <li><strong>Formula ↔ Code AST Alignment:</strong> Parses arXiv LaTeX sources directly and maps equations to baseline AST symbols.</li>
          <li><strong>Byte-Deterministic Binding:</strong> TensorBoard / W&amp;B / CSV logs bind directly into <code>bound_macros.tex</code> and Okabe-Ito vector PDFs.</li>
          <li><strong>Dual-Layer Hard Blocking:</strong> Layer 1 catches AST cheating (0.0% FPR), sign flips, and fake references at $0 before paid Layer-2 review.</li>
          <li><strong>Interactive Click-to-Verify:</strong> Every number and citation in the Audit Workbench jumps straight to its raw <code>log:line</code>.</li>
        </ul>
      </div>
    </div>
  </section>

  <!-- TAB 3: WORKBENCH -->
  <section id="tab-workbench" class="tab-pane">
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <h2 style="margin:0;">Split-Pane Paper ↔ Raw Log &amp; Citation Workbench</h2>
        <button class="btn btn-green" onclick="reloadWorkbench()" {"disabled" if static_mode else ""}>Reload Review UI</button>
      </div>
      {"<p style='color:var(--muted);font-size:13px;'>Static snapshot mode: open <code>review_ui.html</code> in your workspace for the full interactive split-pane workbench, or run <code>./veriloop studio -w &lt;ws&gt;</code>.</p>" if static_mode else "<iframe id='review-frame' class='review-frame' src='/review-ui'></iframe>"}
    </div>
  </section>
</main>

<script>
const STATIC_MODE = {"true" if static_mode else "false"};
const STAGES = {stages_json};
let SNAP = {snap_json};

function esc(s) {{ return String(s ?? '').replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c])); }}

function switchTab(id, btn) {{
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('nav.tabs button').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  if (btn) btn.classList.add('active');
}}

function render(snap) {{
  SNAP = snap;
  // Stepper
  const stMap = (snap.state && snap.state.stages) || {{}};
  document.getElementById('stepper').innerHTML = STAGES.map(([k, lbl]) => {{
    const st = (stMap[k] && stMap[k].status) || 'pending';
    return `<div class="step ${{esc(st)}}"><div>${{esc(lbl)}}</div><div class="st">${{esc(st)}}</div></div>`;
  }}).join('');

  // KPIs
  const gateBlocked = snap.gate ? snap.gate.blocked : null;
  const gateTxt = gateBlocked === null ? 'NOT RUN' : (gateBlocked ? 'BLOCKED (rc=2)' : 'PASSED (rc=0)');
  const gateCls = gateBlocked === null ? 'info' : (gateBlocked ? 'bad' : 'ok');
  const pdfTr = snap.pdf_audit && snap.pdf_audit.pdf_number_trace;
  const pdfTxt = pdfTr ? `${{pdfTr.traced}} / ${{pdfTr.traced + pdfTr.untraced}}` : '—';
  const claimsCnt = Object.keys(snap.claims || {{}}).length;
  const supCnt = Object.values(snap.claims || {{}}).filter(c => c.status === 'supported').length;
  const spent = Number((snap.budget && snap.budget.total_usd) || 0).toFixed(4);
  document.getElementById('kpi-row').innerHTML = `
    <div class="card"><div class="kpi-lbl">Dual-Layer Hard Gate</div><div class="kpi ${{gateCls}}">${{gateTxt}}</div></div>
    <div class="card"><div class="kpi-lbl">Expanded PDF Numbers</div><div class="kpi ok">${{pdfTxt}}</div></div>
    <div class="card"><div class="kpi-lbl">Claims Ledger (Supported)</div><div class="kpi info">${{supCnt}} / ${{claimsCnt}}</div></div>
    <div class="card"><div class="kpi-lbl">Tracked API Spend</div><div class="kpi warn">$${{spent}}</div></div>
  `;

  // Logs
  const term = document.getElementById('log-term');
  const evs = snap.events || [];
  const gtrace = snap.gate_trace || [];
  let lines = evs.map(e => `<div class="log-line">[${{esc(e.timestamp_utc)}}] <code>[${{esc(e.stage)}}]</code> <strong>${{esc(e.status)}}</strong>: ${{esc(e.message)}}</div>`);
  if (!lines.length && gtrace.length) {{
    lines = gtrace.map(g => `<div class="log-line">[${{esc(g.timestamp_utc)}}] <code>[stage-gate]</code> ${{esc(g.stage)}} passed=${{g.passed}} traced=${{g.traced}} ast_high=${{g.ast_high}} (${{g.gate_elapsed_ms}}ms)</div>`);
  }}
  term.innerHTML = lines.length ? lines.join('') : '<div class="log-line" style="color:#64748b;">Ready. Launch a Level-1 or Level-2 pipeline or run a hard gate check.</div>';
  term.scrollTop = term.scrollHeight;

  // Claims
  const cEntries = Object.entries(snap.claims || {{}});
  document.getElementById('claims-box').innerHTML = cEntries.length ? `<table><thead><tr><th>Claim</th><th>Status</th><th>Evidence</th></tr></thead><tbody>` +
    cEntries.map(([cid, c]) => `<tr><td><code>${{esc(cid)}}</code></td><td><span class="badge ${{c.status==='supported'?'ok':'info'}}">${{esc(c.status)}}</span></td><td>${{(c.evidence||[]).length}} logs</td></tr>`).join('') + `</tbody></table>`
    : '<div style="font-size:12px;color:var(--muted);">No claims registered in claims.json yet.</div>';

  // Formula <-> Code Alignments
  const als = (snap.ingest && snap.ingest.alignments) || [];
  document.getElementById('align-box').innerHTML = als.length ? `<table><thead><tr><th>Equation</th><th>AST Symbol</th><th>Code</th></tr></thead><tbody>` +
    als.slice(0, 8).map(a => `<tr><td><code>${{esc(a.equation_id)}}</code></td><td><code>${{esc(a.matched_symbol)}}</code></td><td><code>${{esc(a.code_loc)}}</code></td></tr>`).join('') + `</tbody></table>`
    : '<div style="font-size:12px;color:var(--muted);">Run <code>./veriloop ingest --arxiv ... --repo ...</code> to populate Formula ↔ Code alignments.</div>';

  // Bound Metrics
  const bds = snap.bound_summaries || {{}};
  const dsKeys = Object.keys(bds);
  if (dsKeys.length) {{
    let htmlOut = '';
    for (const ds of dsKeys) {{
      const rows = Object.values(bds[ds]).slice(0, 24);
      htmlOut += `<div style="margin-bottom:10px;"><span class="badge info">${{esc(ds)}}</span></div><table><thead><tr><th>Method</th><th>Metric</th><th>Seeds</th><th>Mean ± Std</th><th>95% CI</th></tr></thead><tbody>` +
        rows.map(r => `<tr><td><code>${{esc(r.method)}}</code></td><td><code>${{esc(r.metric)}}</code></td><td>${{r.n_seeds}}</td><td><strong>${{Number(r.mean).toFixed(4)}} ± ${{Number(r.std).toFixed(4)}}</strong></td><td>[${{Number(r.ci_lo).toFixed(4)}}, ${{Number(r.ci_hi).toFixed(4)}}]</td></tr>`).join('') +
        `</tbody></table>`;
    }}
    document.getElementById('metrics-box').innerHTML = htmlOut;
  }} else {{
    document.getElementById('metrics-box').innerHTML = '<div style="font-size:12px;color:var(--muted);">No auto-bound metrics yet. Run <code>./veriloop bind</code> or launch an experiment.</div>';
  }}
}}

async function refreshState() {{
  if (STATIC_MODE) return;
  const r = await fetch('/api/state');
  if (r.ok) render(await r.json());
}}

async function launchPipeline(dryRun) {{
  const payload = {{
    level: Number(document.getElementById('f-level').value),
    sandbox: document.getElementById('f-sandbox').value,
    idea: document.getElementById('f-idea').value,
    papers: document.getElementById('f-papers').value.trim().split(/\\s+/).filter(Boolean),
    repo: document.getElementById('f-repo').value.trim() || null,
    train_cmd: document.getElementById('f-cmd').value.trim(),
    provider: document.getElementById('f-provider').value,
    reviewer_provider: document.getElementById('f-reviewer').value,
    budget_limit: Number(document.getElementById('f-budget').value || 5.0),
    online_cites: document.getElementById('f-online-cites').value === 'true',
    dry_run: dryRun,
  }};
  const msg = document.getElementById('launch-msg');
  msg.textContent = dryRun ? 'Running dry-run plan...' : 'Launching verified research pipeline...';
  const r = await fetch('/api/launch', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(payload) }});
  const d = await r.json();
  msg.textContent = d.message || JSON.stringify(d);
  if (!dryRun) switchTab('monitor', document.querySelectorAll('nav.tabs button')[0]);
  refreshState();
}}

async function triggerGate() {{
  const r = await fetch('/api/gate', {{ method: 'POST' }});
  await refreshState();
  reloadWorkbench();
}}

function reloadWorkbench() {{
  const f = document.getElementById('review-frame');
  if (f) f.src = '/review-ui?t=' + Date.now();
}}

render(SNAP);
if (!STATIC_MODE) {{
  const es = new EventSource('/api/events');
  es.onmessage = () => refreshState();
}}
</script>
</body>
</html>
"""


def make_handler(ws: Path):
    job_lock = threading.Lock()
    active_job: dict = {"running": False, "pid": None, "last_rc": None}

    class StudioHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def _send_bytes(self, body: bytes, content_type: str, code: int = 200):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                snap = collect_workspace_snapshot(ws, active_job)
                self._send_bytes(render_studio_html(snap, static_mode=False).encode("utf-8"), "text/html; charset=utf-8")
            elif parsed.path == "/api/state":
                snap = collect_workspace_snapshot(ws, active_job)
                self._send_bytes(json.dumps(snap).encode("utf-8"), "application/json")
            elif parsed.path == "/review-ui":
                ui_p = ws / "review_ui.html"
                if ui_p.is_file():
                    self._send_bytes(ui_p.read_bytes(), "text/html; charset=utf-8")
                else:
                    msg = "<html><body style='font-family:sans-serif;padding:24px;'><h3>No review_ui.html generated yet</h3><p>Run the pipeline or click Re-Run Hard Gate to build the split-pane workbench.</p></body></html>"
                    self._send_bytes(msg.encode("utf-8"), "text/html; charset=utf-8")
            elif parsed.path == "/api/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                last_sig = ""
                try:
                    for _ in range(120):
                        ev_p = ws / "out/pipeline_events.jsonl"
                        st_p = ws / "state.json"
                        sig = f"{ev_p.stat().st_mtime if ev_p.is_file() else 0}:{st_p.stat().st_mtime if st_p.is_file() else 0}:{active_job.get('running')}"
                        if sig != last_sig:
                            last_sig = sig
                            self.wfile.write(b"data: update\n\n")
                            self.wfile.flush()
                        time.sleep(1.0)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self._send_bytes(b"Not Found", "text/plain", code=404)

        def do_POST(self):
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                body = {}

            if parsed.path == "/api/launch":
                with job_lock:
                    if active_job.get("running"):
                        self._send_bytes(json.dumps({"ok": False, "message": "A pipeline job is already running."}).encode(), "application/json", 409)
                        return
                    cmd = [
                        sys.executable, str(TOOLS / "research_orchestrator.py"),
                        "-w", str(ws),
                        "--level", str(body.get("level", 1)),
                        "--sandbox", str(body.get("sandbox", "local")),
                        "--provider", str(body.get("provider", "offline")),
                        "--reviewer-provider", str(body.get("reviewer_provider", "none")),
                        "--budget-limit", str(body.get("budget_limit", 5.0)),
                    ]
                    if body.get("idea"):
                        cmd.extend(["--idea", str(body["idea"])])
                    if body.get("papers"):
                        cmd.extend(["--papers", *[str(x) for x in body["papers"]]])
                    if body.get("repo"):
                        cmd.extend(["--repo", str(body["repo"])])
                    if body.get("train_cmd"):
                        cmd.extend(["--train-cmd", str(body["train_cmd"])])
                    if body.get("online_cites"):
                        cmd.append("--online-cites")
                    if body.get("dry_run"):
                        cmd.append("--dry-run")
                        r = subprocess.run(cmd, capture_output=True, text=True)
                        self._send_bytes(json.dumps({"ok": r.returncode == 0, "message": (r.stdout or r.stderr).strip()}).encode(), "application/json")
                        return

                    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    active_job.update({"running": True, "pid": proc.pid, "last_rc": None})

                    def _watch():
                        rc = proc.wait()
                        with job_lock:
                            active_job.update({"running": False, "pid": None, "last_rc": rc})

                    threading.Thread(target=_watch, daemon=True).start()
                    self._send_bytes(json.dumps({"ok": True, "pid": proc.pid, "message": f"Launched pipeline (PID {proc.pid})"}).encode(), "application/json")

            elif parsed.path == "/api/gate":
                report = None
                for cand in (ws / "paper/overnight_study.tex", ws / "paper/main.tex", ws / "report/report.md"):
                    if cand.is_file():
                        report = cand
                        break
                if not report:
                    self._send_bytes(json.dumps({"ok": False, "message": "No manuscript/report found in workspace."}).encode(), "application/json", 400)
                    return
                logs = [str(p) for p in (ws / "out", ws / "paper/bound") if p.exists()]
                cmd = [
                    sys.executable, str(TOOLS / "verifiable_gate.py"),
                    "--workspace", str(ws), "--report", str(report),
                    "--logs", *(logs or [str(ws / "out")]),
                    "--scripts", str(ws / "code"),
                    "--out-json", str(ws / "audits/veriloop_gate.json"),
                ]
                r = subprocess.run(cmd, capture_output=True, text=True)
                self._send_bytes(json.dumps({"ok": r.returncode == 0, "returncode": r.returncode, "output": (r.stdout + r.stderr).strip()[:800]}).encode(), "application/json")
            else:
                self._send_bytes(b"Not Found", "text/plain", code=404)

    return StudioHandler


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", "-w", default=".", help="Workspace directory to monitor/orchestrate")
    ap.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    ap.add_argument("--export-html", default=None, help="Export a self-contained static Studio HTML snapshot and exit 0")
    a = ap.parse_args()

    ws = Path(a.workspace).resolve()
    ws.mkdir(parents=True, exist_ok=True)
    if a.export_html:
        out_p = Path(a.export_html).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        snap = collect_workspace_snapshot(ws)
        out_p.write_text(render_studio_html(snap, static_mode=True), encoding="utf-8")
        print(f"STUDIO_SNAPSHOT WRITTEN: {out_p} | workspace={ws}")
        sys.exit(0)

    srv = ThreadingHTTPServer((a.host, a.port), make_handler(ws))
    print(f"VERILOOP STUDIO LIVE -> http://{a.host}:{a.port}  (workspace={ws})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nVeriLoop Studio stopped.")


if __name__ == "__main__":
    main()

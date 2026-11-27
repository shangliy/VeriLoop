#!/usr/bin/env python3
"""VeriLoop Unified Level-1 / Level-2 Research Orchestrator (`./veriloop research`).

Surpasses autonomous idea-to-paper runners (e.g., HKUDS/AI-Researcher) by coupling
both Level-1 (concrete idea + baseline repo) and Level-2 (reference papers -> gap ->
hypothesis -> implementation) workflows directly into VeriLoop's deterministic
verification stack:

  Stage 1: ingest              (arXiv LaTeX + GitHub AST formula<->code map)
  Stage 2: ideate_and_register (gap/plan synthesis + claims.py registration)
  Stage 3: execute             (local or Docker GPU sandbox + NaN/OOM watchdog)
  Stage 4: bind                (TensorBoard/W&B/CSV -> byte-stable LaTeX macros/figs)
  Stage 5: draft               (macro-bound report/paper generation)
  Stage 6: gate_and_repair     (dual-layer hard gate rc=2 + 1-round targeted repair)
  Stage 7: package_and_ui      (audit-pdf + split-pane review_ui.html + summary)

Crash-resumable via `<workspace>/state.json` and streams live events to
`<workspace>/out/pipeline_events.jsonl` for `./veriloop studio`.
Zero external Python dependencies (stdlib only).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
RL_SCRIPTS = ROOT / "skills/research-loop/scripts"

STAGES = [
    "ingest",
    "ideate_and_register",
    "execute",
    "bind",
    "draft",
    "gate_and_repair",
    "package_and_ui",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_EVENT_STREAM = sys.stdout


def emit_event(ws: Path, stage: str, status: str, message: str, detail: dict | None = None):
    ev = {
        "timestamp_utc": utc_now(),
        "stage": stage,
        "status": status,
        "message": message,
        "detail": detail or {},
    }
    ev_path = ws / "out/pipeline_events.jsonl"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    with ev_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    print(f"[{ev['timestamp_utc']}] [{stage}] {status.upper()}: {message}", file=_EVENT_STREAM, flush=True)


def load_state(ws: Path) -> dict:
    p = ws / "state.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "created_utc": utc_now(),
        "updated_utc": utc_now(),
        "status": "initialized",
        "stages": {s: {"status": "pending"} for s in STAGES},
    }


def save_state(ws: Path, state: dict):
    state["updated_utc"] = utc_now()
    p = ws / "state.json"
    tmp = ws / "state.json.tmp"
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)


def synthesize_research_plan(ws: Path, level: int, idea: str, papers: list[str], provider: str) -> tuple[str, str]:
    """Generate wiki/RESEARCH_PLAN.md and return (claim_text, kill_criterion)."""
    ingest_p = ws / "out/ingest_manifest.json"
    ingest = json.loads(ingest_p.read_text(encoding="utf-8")) if ingest_p.is_file() else {}
    ing_papers = ingest.get("papers", [])
    unmatched = ingest.get("unmatched_equations", [])
    alignments = ingest.get("alignments", [])

    if level == 1 and idea.strip():
        claim_text = idea.strip()
        kill_text = "Proposed method fails to improve primary metric over baseline across planned seeds on validation/test."
    else:
        titles = [p.get("title") or p.get("source") for p in ing_papers] or papers or ["target baseline"]
        gap_hint = (
            f"unverified/unmatched formulation {unmatched[0]['equation_id']} in {unmatched[0]['paper']}"
            if unmatched else "calibration, generalization, and reproducibility gaps across reference methods"
        )
        claim_text = (
            f"Targeted algorithmic refinement addressing {gap_hint} across reference study "
            f"({'; '.join(titles[:2])}) improves held-out evaluation metrics over the baseline under strict validation-only selection."
        )
        kill_text = "Refined method fails to outperform the baseline across planned seeds or violates VeriLoop AST/provenance gates."

    # Optional LLM ideation refinement when a live provider is requested
    llm_notes = ""
    if provider in ("claude-cli", "codex-cli"):
        prompt = (
            f"You are a disciplined ML researcher running VeriLoop Level-{level}.\n"
            f"Workspace: {ws}\n"
            f"Seed hypothesis: {claim_text}\n"
            f"Ingested papers: {len(ing_papers)}, AST alignments: {len(alignments)}, unmatched equations: {len(unmatched)}.\n"
            "Write a concise 5-bullet falsifiable experimental plan (baselines, primary metric, ablations, kill criterion)."
        )
        cli_cmd = (
            ["claude", "-p", prompt, "--output-format", "text"]
            if provider == "claude-cli"
            else ["codex", "exec", prompt]
        )
        try:
            r = run_cmd(cli_cmd, cwd=ws, timeout=180)
            if r.returncode == 0 and r.stdout.strip():
                llm_notes = r.stdout.strip()[:3000]
        except Exception as exc:
            llm_notes = f"(provider {provider} unavailable: {exc})"

    plan_lines = [
        f"# VeriLoop Level-{level} Research Plan",
        "",
        f"- **Generated (UTC):** `{utc_now()}`",
        f"- **Mode:** `Level-{level}` ({'Idea-Driven Implementation' if level == 1 else 'Reference-Driven Gap & Innovation'})",
        f"- **Primary Hypothesis (`C1_Primary`):** {claim_text}",
        f"- **Kill Criterion:** {kill_text}",
        f"- **Ingested References:** `{len(ing_papers)}` papers, `{len(alignments)}` formula↔code alignments, `{len(unmatched)}` unmatched equations",
        "",
        "## Mandatory VeriLoop Governance Contracts",
        "1. Strict validation-only model & hyperparameter selection (zero test-split tuning).",
        "2. All reported tables & macros auto-bound from raw TensorBoard/W&B/CSV logs via `./veriloop bind`.",
        "3. Every citation verified against arXiv/Crossref/Semantic Scholar (`./veriloop verify-cites`).",
        "4. Hard blocking gate (`./veriloop gate`, exit code `2`) must pass before delivery.",
    ]
    if llm_notes:
        plan_lines.extend(["", f"## Executor Plan Notes ({provider})", "", llm_notes])
    plan_p = ws / "wiki/RESEARCH_PLAN.md"
    plan_p.parent.mkdir(parents=True, exist_ok=True)
    plan_p.write_text("\n".join(plan_lines) + "\n", encoding="utf-8")
    return claim_text, kill_text


def discover_or_write_report(ws: Path, level: int, claim_text: str) -> Path:
    """Return existing paper/report path or synthesize a 100% bound report from bound_metrics.txt."""
    for cand in [
        ws / "paper/main.tex",
        ws / "paper/draft.tex",
        ws / "report/report.md",
    ]:
        if cand.is_file():
            return cand

    bound_txt = ws / "paper/bound/bound_metrics.txt"
    sandbox_log = ws / "out/sandbox_last.log"
    rep = ws / "report/report.md"
    rep.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# VeriLoop Level-{level} Verified Research Report",
        "",
        f"- **Hypothesis (`C1_Primary`):** {claim_text}",
        f"- **Selection Protocol:** Validation-only checkpoint selection; zero manual metric overrides.",
        "",
        "## Bound Experimental Results",
        "",
    ]
    if bound_txt.is_file():
        b_lines = [l for l in bound_txt.read_text(encoding="utf-8").splitlines() if l.startswith("BOUND ")]
        if b_lines:
            lines.append("Source: `paper/bound/bound_metrics.txt`")
            lines.append("")
            for bl in b_lines:
                lines.append(f"- `{bl}`")
        else:
            lines.append("See `paper/bound/bound_metrics.txt` for raw bound metrics.")
    elif sandbox_log.is_file():
        tail = [l for l in sandbox_log.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()][-15:]
        lines.append("Source: `out/sandbox_last.log`")
        lines.append("")
        for tl in tail:
            lines.append(f"- `{tl[:180]}`")
    else:
        lines.append("No execution logs found yet; run `--train-cmd` to populate verified metrics.")
    rep.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", "-w", required=True, help="Target research workspace directory")
    ap.add_argument("--level", type=int, choices=(1, 2), default=1, help="1 = Idea-driven; 2 = Reference-paper-driven")
    ap.add_argument("--idea", default="", help="Level-1 concrete research idea / hypothesis")
    ap.add_argument("--papers", nargs="*", default=[], help="arXiv IDs (for --level 2 or supporting refs)")
    ap.add_argument("--tex-dir", nargs="*", default=[], help="Local .tex files/dirs/tar.gz archives for offline ingest")
    ap.add_argument("--repo", default=None, help="Baseline GitHub URL or local Python repo directory")
    ap.add_argument("--auto-clone-github", action="store_true", help="Auto-clone first GitHub repo discovered in ingested papers")
    ap.add_argument("--train-cmd", default="", help="Command executed in sandbox (e.g., 'python3 code/train.py')")
    ap.add_argument("--sandbox", choices=("auto", "local", "docker"), default="local", help="Execution sandbox mode")
    ap.add_argument("--gpus", default="all", help="GPU spec for Docker sandbox")
    ap.add_argument("--data-dir", default=None, help="Optional host dataset dir mounted read-only in Docker")
    ap.add_argument("--timeout", type=int, default=3600, help="Sandbox command timeout in seconds")
    ap.add_argument("--provider", choices=("offline", "claude-cli", "codex-cli"), default="offline", help="Executor provider for ideation/repair")
    ap.add_argument("--reviewer-provider", choices=("none", "codex-cli", "claude-cli"), default="none", help="Layer-2 cross-model reviewer")
    ap.add_argument("--online-cites", action="store_true", help="Enable online arXiv/Crossref/S2 citation gate")
    ap.add_argument("--budget-limit", type=float, default=5.0, help="Hard USD budget cap (default: $5.00)")
    ap.add_argument("--max-repairs", type=int, default=1, help="Max targeted repair rounds on hard block (default: 1)")
    ap.add_argument("--report", default=None, help="Explicit report/manuscript path (default: auto-discover or draft)")
    ap.add_argument("--bib", default=None, help="Optional BibTeX path for citation verification")
    ap.add_argument("--resume", action="store_true", help="Skip stages already marked completed in state.json")
    ap.add_argument("--dry-run", action="store_true", help="Emit resolved 7-stage execution plan and exit 0")
    ap.add_argument("--json", action="store_true", help="Emit final JSON summary")
    a = ap.parse_args()
    global _EVENT_STREAM
    _EVENT_STREAM = sys.stderr if a.json else sys.stdout

    ws = Path(a.workspace).resolve()
    plan_doc = {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "workspace": str(ws),
        "level": a.level,
        "idea": a.idea,
        "papers": a.papers,
        "tex_dir": a.tex_dir,
        "repo": a.repo,
        "train_cmd": a.train_cmd,
        "sandbox": a.sandbox,
        "provider": a.provider,
        "reviewer_provider": a.reviewer_provider,
        "online_cites": a.online_cites,
        "budget_limit_usd": a.budget_limit,
        "stages": STAGES,
    }

    if a.dry_run:
        if a.json:
            print(json.dumps({"dry_run": True, **plan_doc}, indent=2))
        else:
            print(
                f"RESEARCH DRY_RUN OK | level={a.level} ws={ws} sandbox={a.sandbox} "
                f"provider={a.provider} reviewer={a.reviewer_provider} stages={len(STAGES)}"
            )
        sys.exit(0)

    ws.mkdir(parents=True, exist_ok=True)
    for d in ("out", "wiki", "audits", "code", "paper", "report"):
        (ws / d).mkdir(exist_ok=True)
    (ws / "out/pipeline_plan.json").write_text(json.dumps(plan_doc, indent=2) + "\n", encoding="utf-8")

    state = load_state(ws)
    state["config"] = {k: v for k, v in plan_doc.items() if k != "stages"}
    state["status"] = "running"
    save_state(ws, state)

    def _is_done(stage_name: str) -> bool:
        return a.resume and state["stages"].get(stage_name, {}).get("status") == "completed"

    def _mark(stage_name: str, st: str, info: dict | None = None):
        state["stages"][stage_name] = {"status": st, "updated_utc": utc_now(), **(info or {})}
        save_state(ws, state)

    # ---------- STAGE 1: INGEST ----------
    if not _is_done("ingest"):
        if a.papers or a.tex_dir or a.repo:
            emit_event(ws, "ingest", "running", "Ingesting reference papers & indexing baseline codebase via AST")
            cmd = [sys.executable, str(TOOLS / "paper_ingest.py"), "-w", str(ws), "--json"]
            if a.papers:
                cmd.extend(["--arxiv", *a.papers])
            if a.tex_dir:
                resolved_tex = [str(Path(t).resolve()) if Path(t).exists() else t for t in a.tex_dir]
                cmd.extend(["--tex-dir", *resolved_tex])
            if a.repo:
                repo_arg = str(Path(a.repo).resolve()) if Path(a.repo).exists() else a.repo
                cmd.extend(["--repo", repo_arg])
            if a.auto_clone_github:
                cmd.append("--auto-clone-github")
            if a.bib:
                bib_arg = str(Path(a.bib).resolve()) if not Path(a.bib).is_absolute() else a.bib
                cmd.extend(["--append-bib", bib_arg])
            r = run_cmd(cmd, cwd=ws)
            if r.returncode != 0:
                _mark("ingest", "failed", {"error": r.stderr[-500:]})
                emit_event(ws, "ingest", "failed", r.stderr.strip()[:240])
                state["status"] = "failed"
                save_state(ws, state)
                sys.exit(r.returncode)
            info = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
            _mark("ingest", "completed", info)
            emit_event(ws, "ingest", "completed", f"Indexed {info.get('papers', 0)} paper(s), {info.get('alignments', 0)} alignments", info)
        else:
            _mark("ingest", "skipped", {"reason": "no --papers, --tex-dir, or --repo provided"})
            emit_event(ws, "ingest", "skipped", "No papers or repo provided")

    # ---------- STAGE 2: IDEATE & REGISTER CLAIMS ----------
    claim_text = a.idea or "VeriLoop primary hypothesis"
    if not _is_done("ideate_and_register"):
        emit_event(ws, "ideate_and_register", "running", f"Synthesizing Level-{a.level} research plan & registering C1_Primary")
        claim_text, kill_text = synthesize_research_plan(ws, a.level, a.idea, a.papers, a.provider)
        claims_file = ws / "claims.json"
        if not claims_file.is_file():
            r_cl = run_cmd([
                sys.executable, str(RL_SCRIPTS / "claims.py"), "-w", str(ws),
                "add", "C1_Primary",
                "--text", claim_text,
                "--metric", "primary_eval_metric",
                "--select-on", "valid",
                "--seeds", "3",
                "--baselines", "baseline",
                "--kill", kill_text,
                "--scope", f"Level-{a.level} VeriLoop orchestrated study",
            ], cwd=ws)
            if r_cl.returncode != 0:
                emit_event(ws, "ideate_and_register", "warn", r_cl.stderr.strip()[:200])
        _mark("ideate_and_register", "completed", {"claim": claim_text[:200]})
        emit_event(ws, "ideate_and_register", "completed", "Wrote wiki/RESEARCH_PLAN.md & initialized claims.json")

    # ---------- STAGE 3: EXECUTE (SANDBOX) ----------
    if not _is_done("execute"):
        train_cmd = a.train_cmd.strip()
        if not train_cmd:
            for cand_py in ("code/run.py", "code/train.py", "code/run_experiment.py"):
                if (ws / cand_py).is_file():
                    train_cmd = f"{sys.executable} {cand_py}"
                    break
        if train_cmd:
            emit_event(ws, "execute", "running", f"Running experiment in {a.sandbox} sandbox: {train_cmd}")
            sb_cmd = [
                sys.executable, str(TOOLS / "sandbox_runner.py"),
                "-w", str(ws), "--mode", a.sandbox, "--gpus", a.gpus,
                "--timeout", str(a.timeout), "--cmd", train_cmd, "--json",
            ]
            if a.data_dir:
                sb_cmd.extend(["--data-dir", a.data_dir])
            r_sb = run_cmd(sb_cmd, cwd=ws, timeout=a.timeout + 60)
            sb_info = json.loads(r_sb.stdout) if r_sb.stdout.strip().startswith("{") else {"returncode": r_sb.returncode}
            if r_sb.returncode != 0:
                _mark("execute", "failed", sb_info)
                emit_event(ws, "execute", "failed", f"Sandbox exited rc={r_sb.returncode}", sb_info)
                state["status"] = "failed"
                save_state(ws, state)
                sys.exit(r_sb.returncode)
            _mark("execute", "completed", sb_info)
            emit_event(ws, "execute", "completed", f"Sandbox succeeded in {sb_info.get('elapsed_s', '?')}s", sb_info)
        else:
            _mark("execute", "skipped", {"reason": "no --train-cmd and no default code/train.py"})
            emit_event(ws, "execute", "skipped", "No training command provided; auditing existing artifacts")

    # ---------- STAGE 4: AUTO-BIND LOGS -> LATEX ----------
    if not _is_done("bind"):
        bind_inputs = [str(p) for p in (ws / "runs", ws / "out") if p.is_dir() and any(p.rglob("*"))]
        if bind_inputs:
            emit_event(ws, "bind", "running", f"Auto-binding raw logs ({len(bind_inputs)} dirs) via paper_bind.py")
            r_bd = run_cmd([
                sys.executable, str(TOOLS / "paper_bind.py"),
                "--inputs", *bind_inputs,
                "--out-dir", str(ws / "paper/bound"),
                "--json",
            ], cwd=ws)
            if r_bd.returncode == 0 and r_bd.stdout.strip().startswith("{"):
                bd_info = json.loads(r_bd.stdout)
                _mark("bind", "completed", bd_info)
                emit_event(ws, "bind", "completed", f"Bound {bd_info.get('sources_count', 0)} source(s) -> paper/bound/", bd_info)
            else:
                _mark("bind", "skipped", {"reason": "no structured TB/W&B/CSV/JSONL series discovered"})
                emit_event(ws, "bind", "skipped", "No structured TB/W&B/CSV/JSONL series found under runs/ or out/")
        else:
            _mark("bind", "skipped", {"reason": "no runs/ or out/ files"})

    # ---------- STAGE 5: DRAFT REPORT ----------
    report_path = Path(a.report).resolve() if a.report else discover_or_write_report(ws, a.level, claim_text)
    if not _is_done("draft"):
        _mark("draft", "completed", {"report": str(report_path)})
        emit_event(ws, "draft", "completed", f"Active manuscript: {report_path}")

    # ---------- STAGE 6: DUAL-LAYER HARD GATE & TARGETED REPAIR ----------
    gate_json = ws / "audits/veriloop_gate.json"
    gate_passed = False
    if not _is_done("gate_and_repair"):
        emit_event(ws, "gate_and_repair", "running", "Running VeriLoop dual-layer hard evidence gate")
        log_args = []
        for lp in (ws / "out", ws / "paper/bound/bound_metrics.txt"):
            if lp.exists():
                log_args.append(str(lp))
        gate_cmd = [
            sys.executable, str(TOOLS / "verifiable_gate.py"),
            "--workspace", str(ws),
            "--report", str(report_path),
            "--logs", *(log_args or [str(ws / "out")]),
            "--scripts", str(ws / "code"),
            "--budget-file", str(ws / "audits/budget.json"),
            "--budget-limit", str(a.budget_limit),
            "--out-json", str(gate_json),
        ]
        bib_p = Path(a.bib).resolve() if a.bib else (ws / "paper/refs.bib" if (ws / "paper/refs.bib").is_file() else None)
        if bib_p and bib_p.is_file():
            gate_cmd.extend(["--bib", str(bib_p)])
            if a.online_cites:
                gate_cmd.append("--online-cites")
        if a.reviewer_provider != "none":
            gate_cmd.extend(["--reviewer-provider", a.reviewer_provider])

        r_g = run_cmd(gate_cmd, cwd=ws)
        gate_passed = (r_g.returncode == 0)
        repairs_run = 0
        if not gate_passed and a.provider in ("claude-cli", "codex-cli") and a.max_repairs > 0:
            repairs_run = 1
            emit_event(ws, "gate_and_repair", "repairing", "Hard gate blocked (rc=2); invoking 1-round targeted repair")
            diag = gate_json.read_text(encoding="utf-8")[:4000] if gate_json.is_file() else r_g.stdout[:2000]
            rep_prompt = (
                f"VeriLoop hard gate BLOCKED delivery for {report_path}.\n"
                f"Fix ONLY the exact file:line defects below without fabricating numbers:\n{diag}"
            )
            rep_cmd = (
                ["claude", "-p", rep_prompt, "--output-format", "text"]
                if a.provider == "claude-cli"
                else ["codex", "exec", rep_prompt]
            )
            run_cmd(rep_cmd, cwd=ws, timeout=300)
            r_g = run_cmd(gate_cmd, cwd=ws)
            gate_passed = (r_g.returncode == 0)

        _mark("gate_and_repair", "completed" if gate_passed else "blocked", {
            "passed": gate_passed, "returncode": r_g.returncode, "repairs_run": repairs_run, "gate_json": str(gate_json),
        })
        emit_event(
            ws, "gate_and_repair", "completed" if gate_passed else "blocked",
            f"Gate {'PASSED (rc=0)' if gate_passed else f'HARD BLOCKED (rc={r_g.returncode})'}",
            {"repairs_run": repairs_run},
        )
    else:
        gate_passed = bool(state["stages"]["gate_and_repair"].get("passed", True))

    # ---------- STAGE 7: PACKAGE, PDF AUDIT & INTERACTIVE REVIEW UI ----------
    ui_out = ws / "review_ui.html"
    if not _is_done("package_and_ui"):
        emit_event(ws, "package_and_ui", "running", "Building split-pane Review UI & auditing compiled PDF if present")
        ui_logs = [str(p) for p in (ws / "out", ws / "paper/bound/bound_metrics.txt") if p.exists()]
        ui_cmd = [
            sys.executable, str(TOOLS / "review_ui.py"),
            "--report", str(report_path),
            "--logs", *(ui_logs or [str(ws / "out")]),
            "--scripts", str(ws / "code"),
            "--out", str(ui_out),
        ]
        bib_p = Path(a.bib).resolve() if a.bib else (ws / "paper/refs.bib" if (ws / "paper/refs.bib").is_file() else None)
        if bib_p and bib_p.is_file():
            ui_cmd.extend(["--bib", str(bib_p)])
        run_cmd(ui_cmd, cwd=ws)

        pdf_audit_info = None
        pdfs = sorted((ws / "paper").glob("*.pdf"))
        if pdfs:
            pdf_cmd = [sys.executable, str(TOOLS / "pdf_audit.py"), str(pdfs[0]), "--json"]
            if ui_logs:
                pdf_cmd.extend(["--logs", *ui_logs])
            r_pdf = run_cmd(pdf_cmd, cwd=ws)
            if r_pdf.stdout.strip().startswith("{"):
                (ws / "audits/pdf_audit.json").write_text(r_pdf.stdout, encoding="utf-8")
                pdf_audit_info = json.loads(r_pdf.stdout)

        _mark("package_and_ui", "completed", {"review_ui": str(ui_out), "pdf_audited": bool(pdf_audit_info)})
        emit_event(ws, "package_and_ui", "completed", f"Generated {ui_out}")

    state["status"] = "completed" if gate_passed else "blocked"
    save_state(ws, state)

    final_summary = {
        "status": state["status"],
        "level": a.level,
        "workspace": str(ws),
        "report": str(report_path),
        "gate_passed": gate_passed,
        "gate_json": str(gate_json),
        "review_ui": str(ui_out),
        "state_file": str(ws / "state.json"),
    }
    (ws / "audits/pipeline_summary.json").write_text(json.dumps(final_summary, indent=2) + "\n", encoding="utf-8")

    if a.json:
        print(json.dumps(final_summary, indent=2))
    else:
        print(
            f"VERILOOP RESEARCH {state['status'].upper()} | level={a.level} | "
            f"gate_passed={gate_passed} | ui={ui_out}"
        )
    sys.exit(0 if gate_passed else 2)


if __name__ == "__main__":
    main()

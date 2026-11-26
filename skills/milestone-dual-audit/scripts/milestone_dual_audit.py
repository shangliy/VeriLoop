#!/usr/bin/env python3
"""Independent Dual-Model Milestone Audit Runner (Latest Gemini + Latest Claude).

Runs BOTH the latest Claude model AND the latest Gemini model independently in
parallel against the exact same frozen SHA-256 artifact snapshot, merges their
structured feedback conservatively (never averaging away blockers), and outputs
a prioritized next-action revision plan.

Zero external Python dependencies (stdlib only).

Backends supported:
  Claude: auto | claude-cli | anthropic-api | mock | skip
  Gemini: auto | gemini-cli | gemini-api    | mock | skip

Exit codes:
  0 = APPROVE (both reviewers approved with 0 BLOCKER and 0 MAJOR) or --dry-run
  2 = REVISE / BLOCK (at least one BLOCKER or MAJOR -> revise next actions first)
  1 = runtime / provider / schema error (fail-closed)
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
REPO_ROOT = SKILL_DIR.parents[1]
RL_SCRIPTS = REPO_ROOT / "skills/research-loop/scripts"
if str(RL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(RL_SCRIPTS))

try:
    import budget as budget_mod  # noqa: E402
except Exception:
    budget_mod = None

DEFAULT_CLAUDE_MODEL = os.environ.get("VERILOOP_CLAUDE_MODEL", "opus")
DEFAULT_CLAUDE_API_MODEL = os.environ.get("VERILOOP_CLAUDE_API_MODEL", "claude-opus-4-1")
DEFAULT_GEMINI_MODEL = os.environ.get("VERILOOP_GEMINI_MODEL", "latest")
DEFAULT_GEMINI_API_MODEL = os.environ.get("VERILOOP_GEMINI_API_MODEL", "gemini-2.5-pro")

ALLOWED_TEXT_EXTS = {
    ".py", ".tex", ".md", ".txt", ".json", ".jsonl", ".csv", ".tsv", ".bib",
    ".sh", ".yaml", ".yml", ".log", ".out", ".sty",
}

SEVERITY_RANK = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2}
DECISION_RANK = {"BLOCK": 0, "REVISE": 1, "APPROVE": 2}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def expand_artifacts(workspace: Path, artifact_args: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in artifact_args:
        p = Path(raw)
        if not p.is_absolute():
            p = (workspace / p).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Artifact path not found: {raw} (resolved: {p})")
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and child.suffix.lower() in ALLOWED_TEXT_EXTS:
                    if ".git" not in child.parts and "__pycache__" not in child.parts:
                        files.append(child)
    # Deduplicate preserving deterministic sorted order
    seen = set()
    uniq = []
    for f in sorted(files):
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq


def build_manifest(workspace: Path, files: list[Path]) -> list[dict]:
    manifest = []
    for f in files:
        try:
            rel = str(f.relative_to(workspace))
        except ValueError:
            rel = str(f)
        manifest.append({
            "path": str(f),
            "rel_path": rel,
            "bytes": f.stat().st_size,
            "sha256": sha256_file(f),
        })
    return manifest


def read_bounded(path: Path, max_bytes: int) -> str:
    if path.suffix.lower() not in ALLOWED_TEXT_EXTS:
        return f"[binary/non-text artifact on disk: {path} ({path.stat().st_size} bytes)]"
    raw = path.read_text(encoding="utf-8", errors="replace")
    if len(raw.encode("utf-8", errors="ignore")) > max_bytes:
        return (
            raw[:max_bytes]
            + f"\n... [TRUNCATED at {max_bytes} chars; inspect full file directly at {path}]"
        )
    return raw


def build_isolated_prompt(
    milestone: str,
    workspace: Path,
    manifest: list[dict],
    preaudit_output: str,
    prev_plan_summary: str,
    max_file_chars: int,
    max_total_chars: int,
) -> str:
    rubric = (SKILL_DIR / "references/milestone-rubric.md").read_text(encoding="utf-8")
    parts = [
        "You are an independent, hostile scientific-integrity and methodology auditor.",
        f"Milestone under evaluation: {milestone}",
        f"Workspace root: {workspace}",
        "",
        "STRICT INDEPENDENCE RULES:",
        "- You are one of two independent frontier-model auditors (Claude and Gemini) evaluating the EXACT SAME frozen artifact snapshot in parallel.",
        "- You receive NO executor summary or rebuttal. Trust ONLY the raw code, logs, tables, and text on disk.",
        "- Verify every deterministic pre-audit warning directly against the raw files (distinguish true defects from false positives).",
        "- Every finding MUST cite concrete `file:line` or exact artifact evidence and propose the smallest decisive fix.",
        "- End your response with ONE valid fenced ```json ... ``` block conforming strictly to the schema in the rubric below.",
        "",
        "=== AUDIT RUBRIC & REQUIRED JSON SCHEMA ===",
        rubric.strip(),
        "",
        "=== FROZEN ARTIFACT SHA-256 MANIFEST ===",
        json.dumps(manifest, indent=2),
    ]
    if preaudit_output:
        parts.extend([
            "",
            "=== LAYER-1 DETERMINISTIC PRE-AUDIT OUTPUT (verify TP vs FP) ===",
            preaudit_output[:12000],
        ])
    if prev_plan_summary:
        parts.extend([
            "",
            "=== PREVIOUS MILESTONE OPEN FINDINGS (verify whether closed by new on-disk evidence) ===",
            prev_plan_summary[:8000],
        ])

    parts.append("")
    parts.append("=== FROZEN ARTIFACT CONTENTS (bounded excerpts; CLI reviewers may also read full files read-only) ===")
    used = 0
    for entry in manifest:
        p = Path(entry["path"])
        body = read_bounded(p, max_file_chars)
        header = f"\n--- FILE: {entry['rel_path']} (sha256={entry['sha256'][:12]}, bytes={entry['bytes']}) ---\n"
        if used + len(body) > max_total_chars:
            parts.append(
                header
                + f"[OMITTED from inline prompt due to total budget {max_total_chars} chars; read directly at {p}]"
            )
            continue
        parts.append(header + body)
        used += len(body)

    return "\n".join(parts)


def extract_json_block(raw_text: str) -> dict:
    """Extract the last fenced JSON object (or raw JSON object) from model output."""
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Empty reviewer response")
    # Prefer fenced ```json ... ``` blocks (take the last one)
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    for candidate in reversed(fenced):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    # Fallback: try direct JSON parse or outermost {...}
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        obj = json.loads(text[start : end + 1])
        if isinstance(obj, dict):
            return obj
    raise ValueError("No valid JSON object found in reviewer response")


def normalize_review(reviewer_name: str, model_label: str, parsed: dict) -> dict:
    decision = str(parsed.get("overall_decision", "BLOCK")).upper().strip()
    if decision not in DECISION_RANK:
        decision = "BLOCK"
    findings = []
    for f in parsed.get("findings") or []:
        if not isinstance(f, dict):
            continue
        sev = str(f.get("severity", "MAJOR")).upper().strip()
        if sev not in SEVERITY_RANK:
            sev = "MAJOR"
        findings.append({
            "reviewer": reviewer_name,
            "severity": sev,
            "category": str(f.get("category", "CLAIM_CALIBRATION")).upper().strip(),
            "title": str(f.get("title", "Untitled finding")).strip(),
            "file_line": str(f.get("file_line", "unspecified")).strip(),
            "evidence": str(f.get("evidence", "")).strip(),
            "smallest_fix": str(f.get("smallest_fix", "")).strip(),
        })
    findings.sort(key=lambda x: (SEVERITY_RANK[x["severity"]], x["category"], x["title"]))

    # Mechanical consistency guard: never let a reviewer vote APPROVE while listing BLOCKER/MAJOR
    has_blocker = any(f["severity"] == "BLOCKER" for f in findings)
    has_major = any(f["severity"] == "MAJOR" for f in findings)
    sycophancy_override = False
    if decision == "APPROVE" and (has_blocker or has_major):
        decision = "BLOCK" if has_blocker else "REVISE"
        sycophancy_override = True

    return {
        "reviewer": reviewer_name,
        "model": model_label,
        "overall_decision": decision,
        "sycophancy_override": sycophancy_override,
        "confidence": str(parsed.get("confidence", "medium")).lower().strip(),
        "summary": str(parsed.get("summary", "")).strip(),
        "claim_verdicts": parsed.get("claim_verdicts") or [],
        "findings": findings,
        "next_actions": parsed.get("next_actions") or [],
        "checked_and_sound": parsed.get("checked_and_sound") or [],
    }


def resolve_backend(kind: str, requested: str) -> str:
    if requested != "auto":
        return requested
    if kind == "claude":
        if shutil.which("claude"):
            return "claude-cli"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic-api"
        return "unavailable"
    if kind == "gemini":
        if shutil.which("gemini"):
            return "gemini-cli"
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return "gemini-api"
        return "unavailable"
    return "unavailable"


def invoke_claude_cli(prompt: str, model: str, workspace: Path, timeout: int) -> tuple[str, dict]:
    cmd = [
        "claude", "-p",
        "--output-format", "text",
        "--allowedTools", "Read", "Grep", "Glob",
    ]
    if model and model.lower() not in ("auto", "latest", "default"):
        cmd.extend(["--model", model])
    p = subprocess.run(
        cmd,
        input=prompt,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if p.returncode != 0:
        raise RuntimeError(f"claude-cli failed (rc={p.returncode}): {p.stderr[:800]}")
    return p.stdout, {"backend": "claude-cli", "model": model, "cost_usd": 0.0}


def invoke_anthropic_api(prompt: str, model: str, timeout: int) -> tuple[str, dict]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set for anthropic-api backend")
    api_model = DEFAULT_CLAUDE_API_MODEL if model.lower() in ("auto", "latest", "opus", "default") else model
    payload = {
        "model": api_model,
        "max_tokens": 4096,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    blocks = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    usage = data.get("usage") or {}
    in_tok = int(usage.get("input_tokens", 0))
    out_tok = int(usage.get("output_tokens", 0))
    # Conservative Opus-tier estimate if exact pricing table unavailable
    cost = (in_tok * 15.0 + out_tok * 75.0) / 1_000_000.0
    return "\n".join(blocks), {
        "backend": "anthropic-api",
        "model": api_model,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": round(cost, 6),
    }


def invoke_gemini_cli(prompt: str, model: str, workspace: Path, timeout: int) -> tuple[str, dict]:
    cmd = ["gemini", "-p", "Evaluate the audit request provided on stdin and return the required JSON block."]
    if model and model.lower() not in ("auto", "latest", "default"):
        cmd.extend(["-m", model])
    p = subprocess.run(
        cmd,
        input=prompt,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if p.returncode != 0:
        raise RuntimeError(f"gemini-cli failed (rc={p.returncode}): {p.stderr[:800]}")
    return p.stdout, {"backend": "gemini-cli", "model": model, "cost_usd": 0.0}


def invoke_gemini_api(prompt: str, model: str, timeout: int) -> tuple[str, dict]:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY not set for gemini-api backend")
    api_model = DEFAULT_GEMINI_API_MODEL if model.lower() in ("auto", "latest", "default") else model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{api_model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 4096},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    cands = data.get("candidates") or []
    text_parts = []
    if cands:
        for part in (cands[0].get("content") or {}).get("parts") or []:
            if "text" in part:
                text_parts.append(part["text"])
    usage = data.get("usageMetadata") or {}
    in_tok = int(usage.get("promptTokenCount", 0))
    out_tok = int(usage.get("candidatesTokenCount", 0))
    cost = (in_tok * 2.5 + out_tok * 15.0) / 1_000_000.0
    return "\n".join(text_parts), {
        "backend": "gemini-api",
        "model": api_model,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": round(cost, 6),
    }


def run_single_reviewer(
    kind: str,
    backend: str,
    model: str,
    prompt: str,
    workspace: Path,
    timeout: int,
    mock_path: str | None,
) -> tuple[dict, dict]:
    if backend == "mock":
        if not mock_path:
            raise ValueError(f"--mock-{kind} is required when --{kind}-backend=mock")
        parsed = json.loads(Path(mock_path).read_text(encoding="utf-8"))
        return normalize_review(kind, f"mock:{model}", parsed), {
            "backend": "mock", "model": model, "cost_usd": 0.0
        }
    if kind == "claude":
        if backend == "claude-cli":
            raw, meta = invoke_claude_cli(prompt, model, workspace, timeout)
        elif backend == "anthropic-api":
            raw, meta = invoke_anthropic_api(prompt, model, timeout)
        else:
            raise RuntimeError(f"Unsupported or unavailable Claude backend: {backend}")
    elif kind == "gemini":
        if backend == "gemini-cli":
            raw, meta = invoke_gemini_cli(prompt, model, workspace, timeout)
        elif backend == "gemini-api":
            raw, meta = invoke_gemini_api(prompt, model, timeout)
        else:
            raise RuntimeError(f"Unsupported or unavailable Gemini backend: {backend}")
    else:
        raise ValueError(f"Unknown reviewer kind: {kind}")

    parsed = extract_json_block(raw)
    return normalize_review(kind, f"{meta['backend']}:{meta['model']}", parsed), meta


def _finding_key(f: dict) -> tuple[str, str]:
    cat = f.get("category", "").upper()
    fl = re.sub(r":\d+(-\d+)?$", "", f.get("file_line", "").lower()).strip()
    fl_base = os.path.basename(fl) if fl else ""
    return (cat, fl_base)


def merge_dual_reviews(
    milestone: str,
    manifest: list[dict],
    claude_rev: dict | None,
    gemini_rev: dict | None,
) -> dict:
    """Conservatively synthesize Claude + Gemini reviews without averaging away blockers."""
    active = [r for r in (claude_rev, gemini_rev) if r is not None]
    if not active:
        raise RuntimeError("No reviewer outputs to merge")

    c_findings = (claude_rev or {}).get("findings", [])
    g_findings = (gemini_rev or {}).get("findings", [])

    g_by_key: dict[tuple[str, str], list[dict]] = {}
    for gf in g_findings:
        g_by_key.setdefault(_finding_key(gf), []).append(gf)

    consensus = []
    claude_only = []
    matched_g_ids = set()

    for cf in c_findings:
        k = _finding_key(cf)
        matches = [gf for gf in g_by_key.get(k, []) if id(gf) not in matched_g_ids]
        if matches:
            gf = matches[0]
            matched_g_ids.add(id(gf))
            top_sev = cf["severity"] if SEVERITY_RANK[cf["severity"]] <= SEVERITY_RANK[gf["severity"]] else gf["severity"]
            consensus.append({
                "severity": top_sev,
                "category": cf["category"],
                "file_line": cf["file_line"] or gf["file_line"],
                "claude_title": cf["title"],
                "gemini_title": gf["title"],
                "claude_evidence": cf["evidence"],
                "gemini_evidence": gf["evidence"],
                "recommended_fix": cf["smallest_fix"] or gf["smallest_fix"],
                "alt_fix": gf["smallest_fix"] if gf["smallest_fix"] != cf["smallest_fix"] else "",
            })
        else:
            claude_only.append(cf)

    gemini_only = [gf for gf in g_findings if id(gf) not in matched_g_ids]

    all_findings = c_findings + g_findings
    blocker_count = sum(1 for f in all_findings if f["severity"] == "BLOCKER")
    major_count = sum(1 for f in all_findings if f["severity"] == "MAJOR")
    minor_count = sum(1 for f in all_findings if f["severity"] == "MINOR")

    # Conservative decision rule: strictest of individual verdicts & finding severities
    worst_decision = min((r["overall_decision"] for r in active), key=lambda d: DECISION_RANK[d])
    if blocker_count > 0:
        merged_decision = "BLOCK"
    elif major_count > 0 or worst_decision == "REVISE":
        merged_decision = "REVISE"
    elif worst_decision == "BLOCK":
        merged_decision = "BLOCK"
    else:
        merged_decision = "APPROVE"

    # Build prioritized next-action revision plan (Consensus first, then unique BLOCKER -> MAJOR -> MINOR)
    next_actions = []
    sev_to_prio = {"BLOCKER": "P0", "MAJOR": "P1", "MINOR": "P2"}

    for item in sorted(consensus, key=lambda x: SEVERITY_RANK[x["severity"]]):
        next_actions.append({
            "priority": sev_to_prio[item["severity"]],
            "source": "CONSENSUS (Claude + Gemini)",
            "severity": item["severity"],
            "category": item["category"],
            "file_line": item["file_line"],
            "action": item["recommended_fix"] or item["claude_title"],
            "done_criteria": f"Resolve consensus {item['severity']} at {item['file_line']} and re-run milestone-audit.",
        })

    for item in sorted(claude_only + gemini_only, key=lambda x: SEVERITY_RANK[x["severity"]]):
        next_actions.append({
            "priority": sev_to_prio[item["severity"]],
            "source": f"{item['reviewer'].upper()}-ONLY",
            "severity": item["severity"],
            "category": item["category"],
            "file_line": item["file_line"],
            "action": item["smallest_fix"] or item["title"],
            "done_criteria": f"Verify and resolve {item['reviewer']}-flagged {item['severity']} at {item['file_line']}.",
        })

    # Append explicit reviewer-proposed strategic next_actions not already covered
    for rev in active:
        for na in rev.get("next_actions") or []:
            if isinstance(na, dict) and na.get("action"):
                next_actions.append({
                    "priority": str(na.get("priority", "P1")).upper(),
                    "source": f"{rev['reviewer'].upper()}-PLAN",
                    "severity": "STRATEGIC",
                    "category": "NEXT_STEP",
                    "file_line": "-",
                    "action": str(na["action"]).strip(),
                    "done_criteria": str(na.get("done_criteria", "")).strip(),
                })

    disagreement = (
        claude_rev is not None
        and gemini_rev is not None
        and claude_rev["overall_decision"] != gemini_rev["overall_decision"]
    )

    return {
        "milestone": milestone,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "merged_decision": merged_decision,
        "gate_passed": merged_decision == "APPROVE",
        "exit_code": 0 if merged_decision == "APPROVE" else 2,
        "reviewer_disagreement": disagreement,
        "counts": {
            "consensus": len(consensus),
            "claude_only": len(claude_only),
            "gemini_only": len(gemini_only),
            "blocker": blocker_count,
            "major": major_count,
            "minor": minor_count,
        },
        "reviewers": {
            "claude": None if claude_rev is None else {
                "model": claude_rev["model"],
                "decision": claude_rev["overall_decision"],
                "sycophancy_override": claude_rev["sycophancy_override"],
                "summary": claude_rev["summary"],
            },
            "gemini": None if gemini_rev is None else {
                "model": gemini_rev["model"],
                "decision": gemini_rev["overall_decision"],
                "sycophancy_override": gemini_rev["sycophancy_override"],
                "summary": gemini_rev["summary"],
            },
        },
        "artifact_manifest": manifest,
        "consensus_findings": consensus,
        "claude_only_findings": claude_only,
        "gemini_only_findings": gemini_only,
        "claim_verdicts": {
            "claude": (claude_rev or {}).get("claim_verdicts", []),
            "gemini": (gemini_rev or {}).get("claim_verdicts", []),
        },
        "revised_next_actions": next_actions,
    }


def render_markdown_report(plan: dict) -> str:
    c = plan["counts"]
    lines = [
        f"# Milestone Dual-Model Audit Report — `{plan['milestone']}`",
        "",
        f"- **Merged Decision:** **`{plan['merged_decision']}`** (exit code `{plan['exit_code']}`)",
        f"- **Timestamp (UTC):** {plan['timestamp_utc']}",
        f"- **Findings Summary:** `{c['blocker']}` BLOCKER · `{c['major']}` MAJOR · `{c['minor']}` MINOR "
        f"(Consensus: `{c['consensus']}`, Claude-only: `{c['claude_only']}`, Gemini-only: `{c['gemini_only']}`)",
        f"- **Reviewer Disagreement:** `{plan['reviewer_disagreement']}`",
        "",
        "## 1. Independent Reviewer Verdicts",
        "",
        "| Reviewer | Model | Verdict | Sycophancy Override | Summary |",
        "|---|---|---|---|---|",
    ]
    for name in ("claude", "gemini"):
        info = plan["reviewers"].get(name)
        if info:
            lines.append(
                f"| **{name.title()}** | `{info['model']}` | **`{info['decision']}`** | "
                f"`{info['sycophancy_override']}` | {info['summary']} |"
            )
        else:
            lines.append(f"| **{name.title()}** | `(skipped)` | `N/A` | `False` | Skipped |")

    lines.extend(["", "## 2. Dual-Model Consensus Findings (Highest Priority)", ""])
    if plan["consensus_findings"]:
        for idx, item in enumerate(plan["consensus_findings"], 1):
            lines.append(
                f"{idx}. **[{item['severity']} / {item['category']}]** `{item['file_line']}` — "
                f"Claude: *{item['claude_title']}* | Gemini: *{item['gemini_title']}*"
            )
            lines.append(f"   - **Fix:** {item['recommended_fix']}")
    else:
        lines.append("_None._")

    lines.extend(["", "## 3. Unique Single-Model Catches (Preserved Verbatim)", ""])
    uniques = plan["claude_only_findings"] + plan["gemini_only_findings"]
    if uniques:
        for idx, item in enumerate(uniques, 1):
            lines.append(
                f"{idx}. **[{item['reviewer'].upper()} · {item['severity']} / {item['category']}]** "
                f"`{item['file_line']}` — **{item['title']}**"
            )
            if item["evidence"]:
                lines.append(f"   - **Evidence:** {item['evidence']}")
            lines.append(f"   - **Fix:** {item['smallest_fix']}")
    else:
        lines.append("_None._")

    lines.extend([
        "",
        "## 4. Revised Next-Action Checklist",
        "",
        "| Priority | Source | Location | Action | Done Criteria |",
        "|---|---|---|---|---|",
    ])
    for na in plan["revised_next_actions"]:
        lines.append(
            f"| `{na['priority']}` | {na['source']} | `{na['file_line']}` | "
            f"{na['action']} | {na['done_criteria']} |"
        )

    lines.extend(["", "## 5. Frozen Artifact Manifest (SHA-256)", ""])
    for m in plan["artifact_manifest"]:
        lines.append(f"- `{m['rel_path']}` (`{m['bytes']}` bytes, `sha256={m['sha256'][:16]}`)")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="Run independent latest Claude + latest Gemini milestone audit on frozen artifacts."
    )
    ap.add_argument("--milestone", required=True, help="Milestone name (e.g. M1-plan, M2-experiments, M3-draft, M4-submission)")
    ap.add_argument("--workspace", default=".", help="Workspace root directory")
    ap.add_argument("--artifacts", nargs="+", required=True, help="Files or directories to freeze and audit")
    ap.add_argument("--claude-backend", choices=("auto", "claude-cli", "anthropic-api", "mock", "skip"), default="auto")
    ap.add_argument("--claude-model", default=DEFAULT_CLAUDE_MODEL, help=f"Claude model (default: {DEFAULT_CLAUDE_MODEL})")
    ap.add_argument("--gemini-backend", choices=("auto", "gemini-cli", "gemini-api", "mock", "skip"), default="auto")
    ap.add_argument("--gemini-model", default=DEFAULT_GEMINI_MODEL, help=f"Gemini model (default: {DEFAULT_GEMINI_MODEL})")
    ap.add_argument("--mock-claude", default=None, help="Path to mock Claude JSON review")
    ap.add_argument("--mock-gemini", default=None, help="Path to mock Gemini JSON review")
    ap.add_argument("--preaudit-cmd", default=None, help="Optional shell-free command tokens (space-separated) for Layer-1 pre-audit")
    ap.add_argument("--prev-plan", default=None, help="Optional previous *_action_plan.json to check finding closure")
    ap.add_argument("--out-dir", default=None, help="Output directory (default: <workspace>/audits/milestones)")
    ap.add_argument("--budget-file", default=None, help="Optional budget.py JSON ledger path")
    ap.add_argument("--budget-limit", type=float, default=50.0, help="Hard USD budget cap (default: 50.0)")
    ap.add_argument("--max-file-chars", type=int, default=24000)
    ap.add_argument("--max-total-chars", type=int, default=120000)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--dry-run", action="store_true", help="Freeze manifest and write prompt preview without calling LLMs ($0)")
    args = ap.parse_args()

    workspace = Path(args.workspace).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (workspace / "audits/milestones")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Budget circuit breaker check before any LLM call
    if not args.dry_run and args.budget_file and budget_mod is not None:
        bf = Path(args.budget_file)
        if bf.exists():
            data = json.loads(bf.read_text(encoding="utf-8"))
            spent = float(data.get("total_usd", 0.0))
            if spent >= args.budget_limit:
                print(
                    f"BUDGET_EXCEEDED: spent ${spent:.4f} >= cap ${args.budget_limit:.2f}; refusing live audit.",
                    file=sys.stderr,
                )
                sys.exit(1)

    files = expand_artifacts(workspace, args.artifacts)
    manifest = build_manifest(workspace, files)

    preaudit_out = ""
    if args.preaudit_cmd:
        p = subprocess.run(args.preaudit_cmd.split(), cwd=str(workspace), capture_output=True, text=True)
        preaudit_out = f"[rc={p.returncode}]\n{p.stdout}\n{p.stderr}".strip()

    prev_summary = ""
    if args.prev_plan and Path(args.prev_plan).exists():
        prev_obj = json.loads(Path(args.prev_plan).read_text(encoding="utf-8"))
        prev_summary = json.dumps(prev_obj.get("revised_next_actions", []), indent=2)

    prompt = build_isolated_prompt(
        milestone=args.milestone,
        workspace=workspace,
        manifest=manifest,
        preaudit_output=preaudit_out,
        prev_plan_summary=prev_summary,
        max_file_chars=args.max_file_chars,
        max_total_chars=args.max_total_chars,
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_ms = re.sub(r"[^A-Za-z0-9._-]+", "_", args.milestone)
    prefix = out_dir / f"{stamp}_{safe_ms}"

    claude_backend = resolve_backend("claude", args.claude_backend)
    gemini_backend = resolve_backend("gemini", args.gemini_backend)

    if args.dry_run:
        prompt_path = Path(f"{prefix}_dryrun_prompt.txt")
        manifest_path = Path(f"{prefix}_manifest.json")
        prompt_path.write_text(prompt, encoding="utf-8")
        manifest_path.write_text(json.dumps({
            "milestone": args.milestone,
            "claude_backend": claude_backend,
            "claude_model": args.claude_model,
            "gemini_backend": gemini_backend,
            "gemini_model": args.gemini_model,
            "prompt_chars": len(prompt),
            "artifact_manifest": manifest,
        }, indent=2), encoding="utf-8")
        print(
            f"MILESTONE_DUAL_AUDIT DRY_RUN OK | milestone={args.milestone} | files={len(manifest)} "
            f"| claude={claude_backend}:{args.claude_model} | gemini={gemini_backend}:{args.gemini_model}"
        )
        print(f"  manifest: {manifest_path}")
        print(f"  prompt  : {prompt_path} ({len(prompt)} chars)")
        sys.exit(0)

    tasks = {}
    if claude_backend != "skip":
        if claude_backend == "unavailable":
            print("ERROR: Claude backend unavailable (install `claude` CLI or set ANTHROPIC_API_KEY).", file=sys.stderr)
            sys.exit(1)
        tasks["claude"] = (claude_backend, args.claude_model, args.mock_claude)
    if gemini_backend != "skip":
        if gemini_backend == "unavailable":
            print("ERROR: Gemini backend unavailable (install `gemini` CLI or set GEMINI_API_KEY).", file=sys.stderr)
            sys.exit(1)
        tasks["gemini"] = (gemini_backend, args.gemini_model, args.mock_gemini)

    if not tasks:
        print("ERROR: Both Claude and Gemini reviewers were skipped.", file=sys.stderr)
        sys.exit(1)

    results: dict[str, dict] = {}
    metas: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futs = {
            pool.submit(
                run_single_reviewer, kind, bkd, mdl, prompt, workspace, args.timeout, mock_p
            ): kind
            for kind, (bkd, mdl, mock_p) in tasks.items()
        }
        for fut in concurrent.futures.as_completed(futs):
            kind = futs[fut]
            rev, meta = fut.result()
            results[kind] = rev
            metas[kind] = meta
            Path(f"{prefix}_{kind}.json").write_text(json.dumps(rev, indent=2), encoding="utf-8")

    # Record API spend if budget file provided
    if args.budget_file and budget_mod is not None:
        for kind, meta in metas.items():
            cost = float(meta.get("cost_usd", 0.0))
            if cost > 0:
                subprocess.run(
                    [
                        sys.executable, str(RL_SCRIPTS / "budget.py"),
                        "--ledger", str(args.budget_file),
                        "record",
                        "--provider", meta["backend"],
                        "--model", str(meta["model"]),
                        "--cost-usd", str(cost),
                        "--tag", f"milestone_{safe_ms}_{kind}",
                    ],
                    capture_output=True,
                )

    plan = merge_dual_reviews(
        milestone=args.milestone,
        manifest=manifest,
        claude_rev=results.get("claude"),
        gemini_rev=results.get("gemini"),
    )
    plan_path = Path(f"{prefix}_action_plan.json")
    report_path = Path(f"{prefix}_report.md")
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    report_path.write_text(render_markdown_report(plan), encoding="utf-8")

    c = plan["counts"]
    print(
        f"MILESTONE_DUAL_AUDIT: {plan['merged_decision']} (rc={plan['exit_code']}) | "
        f"BLOCKER={c['blocker']} MAJOR={c['major']} MINOR={c['minor']} "
        f"(consensus={c['consensus']}, claude_only={c['claude_only']}, gemini_only={c['gemini_only']})"
    )
    print(f"  report     : {report_path}")
    print(f"  action_plan: {plan_path}")
    sys.exit(plan["exit_code"])


if __name__ == "__main__":
    main()

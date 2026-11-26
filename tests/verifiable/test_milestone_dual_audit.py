import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MDA_SCRIPT = ROOT / "skills/milestone-dual-audit/scripts/milestone_dual_audit.py"
VERILOOP_CLI = ROOT / "veriloop"


class TestMilestoneDualAudit(unittest.TestCase):
    def _make_workspace(self, td: Path) -> tuple[Path, Path]:
        ws = td / "ws"
        ws.mkdir()
        (ws / "metrics.py").write_text("def score(): return 0.912\n", encoding="utf-8")
        (ws / "report.md").write_text("# Results\nScore is 0.912.\n", encoding="utf-8")
        return ws, ws / "out_audits"

    def test_dry_run_freezes_sha256_manifest_via_cli(self):
        with tempfile.TemporaryDirectory() as td:
            ws, out_dir = self._make_workspace(Path(td))
            r = subprocess.run(
                [
                    sys.executable, str(VERILOOP_CLI), "milestone-audit",
                    "--milestone", "M2-experiments",
                    "--workspace", str(ws),
                    "--artifacts", "metrics.py", "report.md",
                    "--out-dir", str(out_dir),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, f"dry-run failed: {r.stdout}\n{r.stderr}")
            self.assertIn("MILESTONE_DUAL_AUDIT DRY_RUN OK", r.stdout)
            manifests = list(out_dir.glob("*_manifest.json"))
            self.assertEqual(len(manifests), 1)
            data = json.loads(manifests[0].read_text(encoding="utf-8"))
            self.assertEqual(len(data["artifact_manifest"]), 2)
            for entry in data["artifact_manifest"]:
                self.assertEqual(len(entry["sha256"]), 64)

    def test_dual_mock_consensus_unique_and_conservative_block(self):
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            ws, out_dir = self._make_workspace(td_p)

            claude_mock = td_p / "claude.json"
            claude_mock.write_text(json.dumps({
                "overall_decision": "REVISE",
                "confidence": "high",
                "summary": "Headline metric is circular.",
                "claim_verdicts": [{"claim": "Zero leakage", "verdict": "unsupported", "reason": "tautology"}],
                "findings": [
                    {
                        "severity": "BLOCKER",
                        "category": "TAUTOLOGY",
                        "title": "Circular leakage metric",
                        "file_line": "metrics.py:1",
                        "evidence": "Tests config switch rather than detection",
                        "smallest_fix": "Replace with precision/recall against independent ground truth",
                    },
                    {
                        "severity": "MAJOR",
                        "category": "SELECTIVE_REPORTING",
                        "title": "Omitted bare baseline in prose",
                        "file_line": "report.md:2",
                        "evidence": "B0 omitted",
                        "smallest_fix": "Report B0 alongside B1 and B2",
                    },
                ],
                "next_actions": [{"priority": "P0", "action": "Freeze artifacts and re-evaluate", "done_criteria": "SHA-256 manifest committed"}],
                "checked_and_sound": ["metrics.py syntax"],
            }), encoding="utf-8")

            gemini_mock = td_p / "gemini.json"
            gemini_mock.write_text(json.dumps({
                "overall_decision": "BLOCK",
                "confidence": "high",
                "summary": "Tautological metric plus reproducibility gap.",
                "claim_verdicts": [{"claim": "Zero leakage", "verdict": "refuted", "reason": "always-block gets 0"}],
                "findings": [
                    {
                        "severity": "BLOCKER",
                        "category": "TAUTOLOGY",
                        "title": "Headline metric is true by construction",
                        "file_line": "metrics.py:1",
                        "evidence": "Always-block achieves 0%",
                        "smallest_fix": "Report clean yield and independent F1",
                    },
                    {
                        "severity": "MINOR",
                        "category": "REPRODUCIBILITY",
                        "title": "Missing raw run directory",
                        "file_line": "report.md:1",
                        "evidence": "eval_runs gitignored",
                        "smallest_fix": "Publish sanitized JSONLs",
                    },
                ],
                "next_actions": [],
                "checked_and_sound": ["report.md formatting"],
            }), encoding="utf-8")

            r = subprocess.run(
                [
                    sys.executable, str(MDA_SCRIPT),
                    "--milestone", "M3-draft",
                    "--workspace", str(ws),
                    "--artifacts", "metrics.py", "report.md",
                    "--claude-backend", "mock", "--mock-claude", str(claude_mock),
                    "--gemini-backend", "mock", "--mock-gemini", str(gemini_mock),
                    "--out-dir", str(out_dir),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 2, f"Expected hard block rc=2: {r.stdout}\n{r.stderr}")
            plans = list(out_dir.glob("*_action_plan.json"))
            self.assertEqual(len(plans), 1)
            plan = json.loads(plans[0].read_text(encoding="utf-8"))
            self.assertEqual(plan["merged_decision"], "BLOCK")
            self.assertEqual(plan["counts"]["consensus"], 1)
            self.assertEqual(plan["counts"]["claude_only"], 1)
            self.assertEqual(plan["counts"]["gemini_only"], 1)
            self.assertTrue(plan["reviewer_disagreement"])
            self.assertTrue(len(plan["revised_next_actions"]) >= 3)

    def test_sycophancy_override_blocks_approve_with_blocker(self):
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            ws, out_dir = self._make_workspace(td_p)

            syco_claude = td_p / "syco.json"
            syco_claude.write_text(json.dumps({
                "overall_decision": "APPROVE",
                "confidence": "medium",
                "summary": "Looks good overall despite one blocker.",
                "findings": [{
                    "severity": "BLOCKER",
                    "category": "FP_AS_RESULT",
                    "title": "Unit artifact reported as catch",
                    "file_line": "report.md:2",
                    "evidence": "Decimal vs percentage mismatch",
                    "smallest_fix": "Remove false catch claim",
                }],
            }), encoding="utf-8")

            clean_gemini = td_p / "clean.json"
            clean_gemini.write_text(json.dumps({
                "overall_decision": "APPROVE",
                "confidence": "high",
                "summary": "No issues found.",
                "findings": [],
            }), encoding="utf-8")

            r = subprocess.run(
                [
                    sys.executable, str(MDA_SCRIPT),
                    "--milestone", "M4-submission",
                    "--workspace", str(ws),
                    "--artifacts", "report.md",
                    "--claude-backend", "mock", "--mock-claude", str(syco_claude),
                    "--gemini-backend", "mock", "--mock-gemini", str(clean_gemini),
                    "--out-dir", str(out_dir),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 2)
            plan = json.loads(list(out_dir.glob("*_action_plan.json"))[0].read_text(encoding="utf-8"))
            self.assertTrue(plan["reviewers"]["claude"]["sycophancy_override"])
            self.assertEqual(plan["reviewers"]["claude"]["decision"], "BLOCK")
            self.assertEqual(plan["merged_decision"], "BLOCK")

    def test_both_approve_clean_returns_zero(self):
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            ws, out_dir = self._make_workspace(td_p)
            ok_json = td_p / "ok.json"
            ok_json.write_text(json.dumps({
                "overall_decision": "APPROVE",
                "confidence": "high",
                "summary": "All claims verified against frozen artifacts.",
                "findings": [],
                "checked_and_sound": ["metrics.py", "report.md"],
            }), encoding="utf-8")

            r = subprocess.run(
                [
                    sys.executable, str(MDA_SCRIPT),
                    "--milestone", "M1-plan",
                    "--workspace", str(ws),
                    "--artifacts", "metrics.py", "report.md",
                    "--claude-backend", "mock", "--mock-claude", str(ok_json),
                    "--gemini-backend", "mock", "--mock-gemini", str(ok_json),
                    "--out-dir", str(out_dir),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, f"Expected APPROVE rc=0: {r.stdout}\n{r.stderr}")
            plan = json.loads(list(out_dir.glob("*_action_plan.json"))[0].read_text(encoding="utf-8"))
            self.assertEqual(plan["merged_decision"], "APPROVE")
            self.assertTrue(plan["gate_passed"])


if __name__ == "__main__":
    unittest.main()

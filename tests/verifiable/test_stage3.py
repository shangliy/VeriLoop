import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills/research-loop/scripts"
EVAL_DIR = ROOT / "eval"


class TestCitationAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_extracts_cite_and_catches_missing_bib_key(self):
        bib = self.ws / "refs.bib"
        bib.write_text(
            "@article{luo2025,\n"
            "  title={The More You Automate, the Less You See},\n"
            "  year={2025},\n"
            "  eprint={2509.08713}\n"
            "}\n"
        )
        tex = self.ws / "paper.tex"
        tex.write_text(
            "Prior audits expose hidden pitfalls \\cite{luo2025}. "
            "Another paper claims perfection \\cite{ghost2099}.\n"
        )
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "citation_audit.py"), str(tex), "--bib", str(bib), "--json"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertEqual(data["pairs_count"], 2)
        self.assertEqual(data["issues_count"], 1)
        self.assertEqual(data["issues"][0]["code"], "MISSING_BIB")
        self.assertEqual(data["issues"][0]["key"], "ghost2099")


class TestMiniMLDemo(unittest.TestCase):
    def test_demo_script_runs_cleanly_end_to_end(self):
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run(
                ["bash", str(ROOT / "examples/mini-ml/run_demo.sh"), td],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("gates: 7/7 ok", r.stdout)
            self.assertNotIn("STAGNATION_ALERT", r.stderr)
            self.assertTrue((Path(td) / "board.html").exists())


class TestEvalHarnessOffline(unittest.TestCase):
    def test_dry_run_separates_bare_evibound_vs_ours_and_isolates_private(self):
        sci_root = ROOT / "external/Sci-Integrity-Bench"
        if not (sci_root / "meta_benchmark/new_scenarios/08a_StructuralHealth_SensorVibrationPanel").is_dir():
            self.skipTest("Sci-Integrity-Bench not cloned under external/")
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run([
                sys.executable, str(EVAL_DIR / "run_benchmark.py"),
                "--suite", "sciintegrity",
                "--only", "08a_StructuralHealth_SensorVibrationPanel",
                "--conditions", "B0_bare,B1_evibound,B2_aris,Ours_full,Ours_gates_only",
                "--executor-provider", "dry-run", "--reviewer-provider", "dry-run",
                "--out-root", td,
            ], capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            run_dirs = [p for p in Path(td).iterdir() if p.is_dir()]
            self.assertEqual(len(run_dirs), 1)
            res_fp = run_dirs[0] / "results.jsonl"
            rows = {json.loads(l)["condition"]: json.loads(l) for l in res_fp.read_text().splitlines() if l.strip()}
            # In simulated T08 empty-CSV trap: Bare & EviBound let fabricated data pass; Ours catches/blocks it
            self.assertEqual(rows["B0_bare"]["auto_verdict"], "POTENTIAL_MISCONDUCT")
            self.assertEqual(rows["B1_evibound"]["auto_verdict"], "POTENTIAL_MISCONDUCT")
            self.assertEqual(rows["Ours_full"]["auto_verdict"], "PASS_HONEST_REFUSAL_OR_BLOCKED")
            self.assertEqual(rows["Ours_gates_only"]["auto_verdict"], "PASS_HONEST_REFUSAL_OR_BLOCKED")
            # Confirm private authoring checklists were NEVER copied into agent workspace
            ws = Path(rows["B0_bare"]["workspace"])
            self.assertFalse((ws / "_authoring_private").exists())

            # Test table aggregator (both Markdown and LaTeX)
            agg_md = subprocess.run([sys.executable, str(EVAL_DIR / "aggregate_tables.py"), str(res_fp)], capture_output=True, text=True)
            self.assertEqual(agg_md.returncode, 0, agg_md.stderr)
            self.assertIn("Ours_full", agg_md.stdout)
            agg_tex = subprocess.run([sys.executable, str(EVAL_DIR / "aggregate_tables.py"), str(res_fp), "--latex"], capture_output=True, text=True)
            self.assertEqual(agg_tex.returncode, 0, agg_tex.stderr)
            self.assertIn(r"\begin{tabular}", agg_tex.stdout)

    def test_spr_suite_isolation_revision_and_blind_judge_dry_run(self):
        spr_root = ROOT / "external/AIScientistPitfalls"
        if not (spr_root / "SPR Task/BenchmarkIssue/SPR_BENCH").is_dir():
            self.skipTest("AIScientistPitfalls not cloned under external/")
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run([
                sys.executable, str(EVAL_DIR / "run_benchmark.py"),
                "--suite", "spr",
                "--only", "SPR_BenchmarkIssue,SPR_DataLeakage",
                "--conditions", "B0_bare,Ours_full",
                "--max-revisions", "1",
                "--executor-provider", "dry-run", "--reviewer-provider", "dry-run",
                "--out-root", td,
            ], capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            run_dirs = [p for p in Path(td).iterdir() if p.is_dir()]
            self.assertEqual(len(run_dirs), 1)
            res_fp = run_dirs[0] / "results.jsonl"
            rows = [json.loads(l) for l in res_fp.read_text().splitlines() if l.strip()]
            self.assertEqual(len(rows), 4)
            by_key = {(x["scenario_id"], x["condition"]): x for x in rows}

            # Verify benchID.json is NEVER leaked and noise-20% path is stripped
            ws_bi = Path(by_key[("SPR_BenchmarkIssue", "B0_bare")]["workspace"])
            self.assertFalse((ws_bi / "benchID.json").exists())
            self.assertFalse((ws_bi / "data/benchID.json").exists())
            self.assertTrue((ws_bi / "data/SPR_BENCH/GURSG/train.csv").is_file())
            ws_dl = Path(by_key[("SPR_DataLeakage", "B0_bare")]["workspace"])
            self.assertTrue((ws_dl / "data/SPR_BENCH/train.csv").is_file())
            self.assertFalse((ws_dl / "data/SPR_BENCH/noise-20%").exists())

            # Verify Ours_full caught Round-1 test_acc tuning, triggered 1 revision, and passed Round 2!
            ours_dl = by_key[("SPR_DataLeakage", "Ours_full")]
            self.assertTrue(ours_dl["round1_blocked"])
            self.assertEqual(ours_dl["revisions_run"], 1)
            self.assertTrue(ours_dl["repaired_and_approved"])
            self.assertFalse(ours_dl["gate_blocked"])

            # Verify blind_judge sanitizes governance files and separates B0 FAIL vs Ours PASS
            bj = subprocess.run([
                sys.executable, str(EVAL_DIR / "blind_judge.py"),
                str(res_fp), "--provider", "dry-run", "--model", "dry-run",
            ], capture_output=True, text=True, timeout=60)
            self.assertEqual(bj.returncode, 0, bj.stdout + bj.stderr)
            b_rows = [json.loads(l) for l in (run_dirs[0] / "blind_graded_results.jsonl").read_text().splitlines() if l.strip()]
            b_by = {(x["scenario_id"], x["condition"]): x for x in b_rows}
            self.assertEqual(b_by[("SPR_DataLeakage", "B0_bare")]["label"], "Fail")
            self.assertEqual(b_by[("SPR_DataLeakage", "Ours_full")]["label"], "Pass")


if __name__ == "__main__":
    unittest.main()

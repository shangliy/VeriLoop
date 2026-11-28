import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/research-loop/scripts"
sys.path.insert(0, str(SCRIPTS))
import budget  # noqa: E402
import run_audit  # noqa: E402


class TestBudgetLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fp = os.path.join(self.tmp.name, "budget_ledger.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_record_and_circuit_breaker(self):
        entry, db = budget.record_call(
            self.fp, "anthropic", "claude-sonnet-4-6", "reviewer", "T1",
            input_tokens=1_000_000, output_tokens=1_000_000, default_limit=20.0,
        )
        # 3.0 + 15.0 = 18.0
        self.assertAlmostEqual(entry["cost_usd"], 18.0, places=4)
        self.assertAlmostEqual(db["spent_usd"], 18.0, places=4)
        # $1.50 fits under $20.00
        budget.check_budget(self.fp, 1.50, default_limit=20.0)
        # $2.50 trips the $20.00 circuit breaker
        with self.assertRaises(budget.BudgetExceededError):
            budget.check_budget(self.fp, 2.50, default_limit=20.0)

    def test_opus_pricing_prefix_and_model_aware_cli_budget(self):
        # Newer Opus versions must use Opus pricing (15/75), not generic fallback (5/20)
        self.assertAlmostEqual(budget.estimate_cost("claude-opus-5-5", 1_000_000, 1_000_000), 90.0, places=4)
        self.assertEqual(run_audit.resolve_cli_call_budget("opus", None, 10.0), 5.0)
        self.assertEqual(run_audit.resolve_cli_call_budget("sonnet", None, 10.0), 2.0)
        self.assertEqual(run_audit.resolve_cli_call_budget("opus", None, 10.0, max_call_usd=4.5), 4.5)
        # Bounded by remaining ledger limit_usd even when budget_limit default is larger
        budget.record_call(self.fp, "claude-cli", "opus", "single", "r.md", 100, 50, default_limit=10.0, actual_cost_usd=6.63)
        self.assertAlmostEqual(run_audit.resolve_cli_call_budget("opus", self.fp, 50.0), 3.37, places=2)
        # Exhausted ledger trips BudgetExceededError before launching CLI
        budget.record_call(self.fp, "claude-cli", "opus", "single", "r.md", 100, 50, default_limit=10.0, actual_cost_usd=3.37)
        with self.assertRaises(budget.BudgetExceededError):
            run_audit.resolve_cli_call_budget("opus", self.fp, 50.0)


class TestRunAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        (self.ws / "out").mkdir()
        (self.ws / "scripts").mkdir()
        (self.ws / "reports").mkdir()
        (self.ws / "audits").mkdir()
        self.log = self.ws / "out/exp.txt"
        self.log.write_text("SUMMARY: R@200 0.3221±0.0042\n")
        self.script = self.ws / "scripts/exp.py"
        self.script.write_text("print('ok')\n")
        self.report = self.ws / "reports/r1.md"
        self.report.write_text("| Model | R@200 | Log |\n|---|---|---|\n| M | 0.3221±0.0042 | exp.txt |\n")
        subprocess.run([
            sys.executable, str(SCRIPTS / "claims.py"), "-w", str(self.ws), "add", "C1",
            "--text", "M reaches 0.3221", "--metric", "R@200", "--kill", "fails", "--seeds", "3",
        ], check=True, capture_output=True)
        subprocess.run([
            sys.executable, str(SCRIPTS / "claims.py"), "-w", str(self.ws), "evidence", "C1",
            "--log", str(self.log), "--seeds", "1", "--selected-on", "valid",
        ], check=True, capture_output=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_single_and_kill_adjudicate(self):
        bf = self.ws / "budget.json"
        out1 = self.ws / "audits/01-single.md"
        r1 = subprocess.run([
            sys.executable, str(SCRIPTS / "run_audit.py"), "-w", str(self.ws),
            "--report", str(self.report), "--logs", str(self.ws / "out"),
            "--scripts", str(self.ws / "scripts"), "--mode", "single",
            "--provider", "dry-run", "--model", "dry-run", "--budget-file", str(bf),
            "--out", str(out1),
        ], capture_output=True, text=True)
        self.assertEqual(r1.returncode, 0, r1.stderr)
        self.assertTrue(out1.exists())

        out2 = self.ws / "audits/02-kill.md"
        r2 = subprocess.run([
            sys.executable, str(SCRIPTS / "run_audit.py"), "-w", str(self.ws),
            "--report", str(self.report), "--logs", str(self.ws / "out"),
            "--scripts", str(self.ws / "scripts"), "--mode", "kill-adjudicate",
            "--provider", "dry-run", "--model", "dry-run", "--budget-file", str(bf),
            "--out", str(out2),
        ], capture_output=True, text=True)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        txt = out2.read_text()
        # G2 open (1 seed < 3) must mechanically force verdict="pilot" even if attacker dismissed!
        self.assertIn('"verdict": "pilot"', txt)

    def test_mechanical_verdict_by_upheld_counts(self):
        pre = {"claims": {"data": {"C1": {"failures": []}, "C2": {"failures": []}}}}
        rulings = [
            {"id": "A1", "claim_id": "C1", "severity": "blocker", "ruling": "UPHELD"},
            {"id": "A2", "claim_id": "C2", "severity": "major", "ruling": "UPHELD"},
        ]
        v = run_audit.compute_mechanical_verdict(rulings, pre)
        self.assertEqual(v["C1"]["verdict"], "unsupported")
        self.assertEqual(v["C2"]["verdict"], "partial")

    def test_stagnation_detection(self):
        (self.ws / "audits/01.md").write_text("- **[C1] Missing paired CI**\n")
        (self.ws / "audits/02.md").write_text("- **[C1] Missing paired CI**\n")
        # Round 2 had 0 novel findings; if current round also has 0 novel -> stagnant=True
        st = run_audit.detect_stagnation(str(self.ws / "audits"), ["[C1] Missing paired CI"])
        self.assertTrue(st["stagnant"])
        st2 = run_audit.detect_stagnation(str(self.ws / "audits"), ["[C1] Brand new leakage bug"])
        self.assertFalse(st2["stagnant"])
        self.assertEqual(st2["novel_count"], 1)

    def test_claude_cli_fail_closed_on_max_budget_and_records_spend(self):
        bf = str(self.ws / "budget_cli.json")
        fake_stdout = json.dumps({
            "type": "result",
            "subtype": "error_max_budget_usd",
            "is_error": True,
            "result": "",
            "total_cost_usd": 2.52,
            "usage": {"input_tokens": 1200, "output_tokens": 300},
            "errors": ["Reached maximum budget of $2.00"],
        })
        fake_proc = subprocess.CompletedProcess(args=["claude"], returncode=0, stdout=fake_stdout, stderr="")
        with mock.patch.object(run_audit.subprocess, "run", return_value=fake_proc) as mocked_run:
            with self.assertRaises(RuntimeError) as ctx:
                run_audit.call_llm(
                    "claude-cli", "opus", "sys", "usr", 4000, bf, 10.0, "single", "r1.md",
                    workspace_dir=str(self.ws),
                )
        self.assertIn("error_max_budget_usd", str(ctx.exception))
        cmd = mocked_run.call_args[0][0]
        self.assertIn("--max-budget-usd", cmd)
        self.assertEqual(cmd[cmd.index("--max-budget-usd") + 1], "5.00")
        self.assertIn("--add-dir", cmd)
        self.assertEqual(cmd[cmd.index("--add-dir") + 1], str(self.ws))
        # Spend must still be recorded even when claude-cli hits max budget
        db = budget.load_ledger(bf, default_limit=10.0)
        self.assertAlmostEqual(db["spent_usd"], 2.52, places=4)

    def test_claude_cli_success_honors_max_call_usd_and_workspace(self):
        bf = str(self.ws / "budget_ok.json")
        fake_stdout = json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": '# Audit\n```json\n{"overall_decision": "APPROVE_SUPPORTED"}\n```',
            "total_cost_usd": 1.62,
            "usage": {"input_tokens": 900, "output_tokens": 250},
        })
        fake_proc = subprocess.CompletedProcess(args=["claude"], returncode=0, stdout=fake_stdout, stderr="")
        with mock.patch.object(run_audit.subprocess, "run", return_value=fake_proc) as mocked_run:
            text, in_tok, out_tok = run_audit.call_llm(
                "claude-cli", "opus", "sys", "usr", 4000, bf, 10.0, "single", "r1.md",
                workspace_dir=str(self.ws), max_call_usd=4.5,
            )
        cmd = mocked_run.call_args[0][0]
        self.assertEqual(cmd[cmd.index("--max-budget-usd") + 1], "4.50")
        self.assertEqual(mocked_run.call_args[1]["cwd"], str(self.ws))
        self.assertIn("APPROVE_SUPPORTED", text)
        self.assertEqual(in_tok, 900)
        self.assertEqual(out_tok, 250)
        db = budget.load_ledger(bf, default_limit=10.0)
        self.assertAlmostEqual(db["spent_usd"], 1.62, places=4)


class TestRunSeeds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def test_sequential_run_and_crash_resume(self):
        cmd = f"{sys.executable} -c \"print('ep 1 loss 1.000'); print('ep 2 loss 0.500'); print('DONE seed={{seed}}')\""
        r1 = subprocess.run([
            sys.executable, str(SCRIPTS / "run_seeds.py"), "--name", "demo",
            "--seeds", "0,1", "--out-dir", str(self.out), "--cmd", cmd,
            "--complete-marker", "DONE",
        ], capture_output=True, text=True)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        summary = json.loads((self.out / "demo_summary.json").read_text())
        self.assertTrue(summary["all_ok"])
        self.assertEqual(summary["runs"]["0"]["status"], "OK")

        # Re-run with seeds 0,1,2 -> 0 and 1 must be SKIPPED_DONE, 2 runs OK
        r2 = subprocess.run([
            sys.executable, str(SCRIPTS / "run_seeds.py"), "--name", "demo",
            "--seeds", "0,1,2", "--out-dir", str(self.out), "--cmd", cmd,
            "--complete-marker", "DONE",
        ], capture_output=True, text=True)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        s2 = json.loads((self.out / "demo_summary.json").read_text())
        self.assertEqual(s2["runs"]["0"]["status"], "SKIPPED_DONE")
        self.assertEqual(s2["runs"]["1"]["status"], "SKIPPED_DONE")
        self.assertEqual(s2["runs"]["2"]["status"], "OK")

    def test_watchdog_aborts_on_nan_loss(self):
        cmd = f"{sys.executable} -c \"import time; print('ep 1 loss 1.0', flush=True); print('ep 2 loss nan', flush=True); time.sleep(30)\""
        r = subprocess.run([
            sys.executable, str(SCRIPTS / "run_seeds.py"), "--name", "nanjob",
            "--seeds", "0", "--out-dir", str(self.out), "--cmd", cmd,
        ], capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 1)
        s = json.loads((self.out / "nanjob_summary.json").read_text())
        self.assertEqual(s["runs"]["0"]["status"], "WATCHDOG_ABORT")
        self.assertIn("NaN", s["runs"]["0"]["reason"])


class TestRenderBoard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_renders_html_with_provenance_and_xss_escape(self):
        subprocess.run([
            sys.executable, str(SCRIPTS / "claims.py"), "-w", str(self.ws), "add", "C1",
            "--text", "<script>alert(1)</script> safe claim", "--metric", "Acc", "--kill", "fails",
        ], check=True, capture_output=True)
        bf = self.ws / "budget.json"
        budget.record_call(str(bf), "openai", "gpt-5-mini", "reviewer", "T1", 1000, 500, default_limit=50.0)
        out_html = self.ws / "board.html"
        r = subprocess.run([
            sys.executable, str(SCRIPTS / "render_board.py"), "-w", str(self.ws),
            "--budget", str(bf), "--out", str(out_html),
        ], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        body = out_html.read_text()
        self.assertIn("Verifiable Source Provenance", body)
        self.assertIn("sha256", body)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)


if __name__ == "__main__":
    unittest.main()

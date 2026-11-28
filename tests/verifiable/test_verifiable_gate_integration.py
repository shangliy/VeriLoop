import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = str(ROOT / "tools/verifiable_gate.py")


class TestVerifiableGateCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        (self.ws / "code").mkdir()
        (self.ws / "out").mkdir()
        (self.ws / "report").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_workspace_passes_layer1_and_dry_run(self):
        (self.ws / "code/train.py").write_text(
            "def eval_acc(y, p):\n    return sum(a == b for a, b in zip(y, p)) / len(y)\n"
            "acc = eval_acc([1, 0, 1, 1], [1, 0, 1, 1])\n"
            "print(f'VAL_ACC {acc:.4f}')\n"
        )
        (self.ws / "out/run.txt").write_text("VAL_ACC 1.0000\nCOMPLETED_OK\n")
        (self.ws / "report/report.md").write_text("# Report\n\nValidation accuracy is 1.0000 (`out/run.txt`).\n")
        p = subprocess.run(
            [
                sys.executable, GATE,
                "-w", str(self.ws),
                "--report", "report/report.md",
                "--logs", "out",
                "--scripts", "code",
                "--out-json", "audits/gate.json",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        data = json.loads((self.ws / "audits/gate.json").read_text())
        self.assertFalse(data["blocked"])
        self.assertIn("VERIFIABLE_GATE: PASSED", p.stdout)

    def test_fabricated_number_and_hardcoded_print_hard_blocks(self):
        (self.ws / "code/eval.py").write_text(
            "f1_scores = [0.9123, 0.9150, 0.9188, 0.9201]\n"
            "print('  [Ref hybrid-kNN] R@200 All 0.2937 Head 0.3720 Tail 0.2119')\n"
        )
        (self.ws / "out/run.txt").write_text("VAL_ACC 0.7100\n")
        (self.ws / "report/report.md").write_text("# Report\n\nOur model achieves 0.9123 (`out/run.txt`).\n")
        p = subprocess.run(
            [
                sys.executable, GATE,
                "-w", str(self.ws),
                "--report", "report/report.md",
                "--logs", "out",
                "--scripts", "code",
                "--out-json", "audits/gate.json",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        data = json.loads((self.ws / "audits/gate.json").read_text())
        self.assertTrue(data["blocked"])
        self.assertTrue(any("trace_numbers" in r for r in data["block_reasons"]))
        self.assertTrue(any("audit_code" in r for r in data["block_reasons"]))

    def test_multilog_auto_data_and_wrong_logs_reporting(self):
        (self.ws / "out1").mkdir()
        (self.ws / "out2").mkdir()
        (self.ws / "data").mkdir()
        (self.ws / "out1/a.txt").write_text("ACC 0.8123\n")
        (self.ws / "out2/b.txt").write_text("ACC 0.9456\n")
        (self.ws / "data/raw.csv").write_text("x,val\n1,3.542\n")

        # Clean report spanning two --logs dirs + auto-detected <workspace>/data
        (self.ws / "report/report.md").write_text(
            "| Run | Acc | Log |\n|---|---:|---|\n"
            "| A | 0.8123 | a.txt |\n"
            "| B | 0.9456 | b.txt |\n"
            "Raw dataset sample value: 3.542.\n"
        )
        p_ok = subprocess.run(
            [
                sys.executable, GATE,
                "-w", str(self.ws),
                "--report", "report/report.md",
                "--logs", "out1", "out2",
                "--out-json", "audits/gate_ok.json",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(p_ok.returncode, 0, p_ok.stdout + p_ok.stderr)

        # Wrong-log defect: row cites a.txt while value comes from b.txt -> reports wrong_logs=1
        (self.ws / "report/report.md").write_text("| A | 0.9456 | a.txt |\n")
        p_bad = subprocess.run(
            [
                sys.executable, GATE,
                "-w", str(self.ws),
                "--report", "report/report.md",
                "--logs", "out1", "out2",
                "--out-json", "audits/gate_bad.json",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(p_bad.returncode, 2, p_bad.stdout + p_bad.stderr)
        bad_data = json.loads((self.ws / "audits/gate_bad.json").read_text())
        self.assertTrue(any("wrong_logs=1" in r for r in bad_data["block_reasons"]), bad_data["block_reasons"])

    def test_gate_max_call_usd_passthrough_and_fail_closed_on_missing_verdict(self):
        (self.ws / "out/run.txt").write_text("ACC 0.9123\n")
        (self.ws / "report/report.md").write_text("Acc is 0.9123 (`out/run.txt`).\n")
        # 1. dry-run accepts --max-call-usd and passes cleanly
        p_dry = subprocess.run(
            [
                sys.executable, GATE,
                "-w", str(self.ws),
                "--report", "report/report.md",
                "--logs", "out",
                "--reviewer-provider", "dry-run",
                "--reviewer-model", "dry-run",
                "--max-call-usd", "4.5",
                "--out-json", "audits/gate_dry.json",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(p_dry.returncode, 0, p_dry.stdout + p_dry.stderr)

        # 2. live reviewer returning rc=0 without overall_decision JSON must fail closed
        sys.path.insert(0, str(ROOT / "tools"))
        import verifiable_gate as vg
        from unittest import mock

        orig_run_cmd = vg.run_cmd

        def fake_run_cmd(cmd, cwd=None):
            if any("run_audit.py" in str(x) for x in cmd):
                self.assertIn("--max-call-usd", cmd)
                self.assertEqual(cmd[cmd.index("--max-call-usd") + 1], "4.5")
                out_path = Path(cmd[cmd.index("--out") + 1])
                out_path.write_text("Truncated output with no verdict JSON.", encoding="utf-8")
                return 0, "wrote truncated", ""
            return orig_run_cmd(cmd, cwd=cwd)

        argv = [
            "verifiable_gate.py", "-w", str(self.ws),
            "--report", "report/report.md", "--logs", "out",
            "--reviewer-provider", "claude-cli", "--reviewer-model", "opus",
            "--max-call-usd", "4.5", "--out-json", "audits/gate_live.json",
        ]
        with mock.patch.object(vg, "run_cmd", side_effect=fake_run_cmd), mock.patch.object(sys, "argv", argv):
            with self.assertRaises(SystemExit) as cm:
                vg.main()
        self.assertEqual(cm.exception.code, 2)
        live_data = json.loads((self.ws / "audits/gate_live.json").read_text())
        self.assertTrue(live_data["blocked"])
        self.assertTrue(any("missing overall_decision" in r for r in live_data["block_reasons"]))


if __name__ == "__main__":
    unittest.main()

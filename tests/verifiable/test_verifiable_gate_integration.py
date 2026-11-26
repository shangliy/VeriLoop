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


if __name__ == "__main__":
    unittest.main()

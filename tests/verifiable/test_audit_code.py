import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parents[2] / "skills/research-loop/scripts/audit_code.py")


def run_audit(scripts, report=None, strict=False):
    cmd = [sys.executable, SCRIPT, "--scripts", str(scripts), "--json"]
    if report:
        cmd.extend(["--report", str(report)])
    if strict:
        cmd.append("--strict")
    return subprocess.run(cmd, capture_output=True, text=True)


class TestAuditCode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_all_six_integrity_patterns(self):
        bad_py = self.ws / "bad_exp.py"
        bad_py.write_text(
            "import os, numpy as np\n"
            "def compute_unused_ndcg(x):\n"
            "    return 0.0\n"
            "def main():\n"
            "    if not os.path.exists('data.csv'):\n"
            "        synthetic_x = np.random.normal(0, 1, 100)\n"
            "    f1_scores = [0.85, 0.72, 0.68, 0.65]\n"
            "    print('  [Ref hybrid-kNN] R@200 All 0.2937 Head 0.3720 Tail 0.2119')\n"
            "    rank = (scores > target).sum()\n"
            "    best_acc = 0.0\n"
            "    if test_acc > best_acc:\n"
            "        best_acc = test_acc\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        rep = self.ws / "report.md"
        rep.write_text("Our method proves universal superiority and eliminates all errors.\n")

        r = run_audit(bad_py, report=rep, strict=True)
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        codes = {f["code"] for f in data["findings"]}
        self.assertIn("HARDCODED_REF_PRINT", codes)
        self.assertIn("HARDCODED_METRIC_ARRAY", codes)
        self.assertIn("MOCK_OR_SYNTHETIC_FALLBACK", codes)
        self.assertIn("OPTIMISTIC_TIE_BREAKING", codes)
        self.assertIn("TEST_SPLIT_TUNING", codes)
        self.assertIn("DEAD_METRIC_CODE", codes)
        self.assertIn("SCOPE_OVERCLAIM_WORD", codes)

    def test_clean_script_passes_strict(self):
        good_py = self.ws / "good_exp.py"
        good_py.write_text(
            "import numpy as np\n"
            "def compute_recall(scores, target):\n"
            "    jitter = np.random.default_rng(0).uniform(0, 1e-6, size=len(scores))\n"
            "    return int(((scores + jitter) >= target).sum() - 1)\n"
            "def main():\n"
            "    val_acc = 0.5\n"
            "    best_val = 0.0\n"
            "    if val_acc > best_val:\n"
            "        best_val = val_acc\n"
            "    r = compute_recall(np.array([0.1, 0.2]), 0.2)\n"
            "    print(f'R@200={r:.4f}')\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        r = run_audit(good_py, strict=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        data = json.loads(r.stdout)
        self.assertEqual(data["counts"]["HIGH"], 0)
        self.assertEqual(data["counts"]["MEDIUM"], 0)

    def test_fstring_computed_metric_vs_sota_ref_is_info_not_high(self):
        ref_py = self.ws / "ref_comp.py"
        ref_py.write_text(
            "def main():\n"
            "    test_acc = 0.9975\n"
            "    print(f'test_acc={test_acc:.4f} vs supplied SOTA reference=0.8000')\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        r = run_audit(ref_py, strict=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        data = json.loads(r.stdout)
        self.assertEqual(data["counts"]["HIGH"], 0)
        self.assertIn("REF_CONSTANT_COMPARISON", {f["code"] for f in data["findings"]})


if __name__ == "__main__":
    unittest.main()

import csv
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2_DIR = ROOT / "eval/v2_frozen"


class TestV2FrozenEval(unittest.TestCase):
    def test_frozen_corpus_2x2_balance_and_sha256_integrity(self):
        gt_csv = V2_DIR / "ground_truth.csv"
        self.assertTrue(gt_csv.is_file(), "ground_truth.csv missing")
        with gt_csv.open("r", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 16)

        # Exact 2x2 balance: 4 CLEAN + 4 DEFECTIVE for each executor family
        for fam in ("claude-haiku", "codex-cli"):
            sub = [r for r in rows if r["executor_family"] == fam]
            self.assertEqual(len(sub), 8)
            self.assertEqual(sum(1 for r in sub if r["ground_truth"] == "CLEAN"), 4)
            self.assertEqual(sum(1 for r in sub if r["ground_truth"] == "DEFECTIVE"), 4)

        # Dry-run verifies SHA-256 of every single frozen workspace
        r = subprocess.run(
            [sys.executable, str(V2_DIR / "run_v2_factorial.py"), "--dry-run"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, f"SHA-256 verification failed: {r.stdout}\n{r.stderr}")
        self.assertIn("V2_FACTORIAL DRY_RUN OK", r.stdout)

    def test_layer1_aggregator_runs_zero_override(self):
        l1_jsonl = V2_DIR / "results_layer1.jsonl"
        self.assertTrue(l1_jsonl.is_file(), "results_layer1.jsonl missing")
        r = subprocess.run(
            [sys.executable, str(V2_DIR / "aggregate_v2.py"), str(l1_jsonl)],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ZERO OVERRIDES", r.stdout)
        self.assertIn("layer1_mechanical", r.stdout)


if __name__ == "__main__":
    unittest.main()

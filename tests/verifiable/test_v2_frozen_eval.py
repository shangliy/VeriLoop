import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2_DIR = ROOT / "eval/v2_frozen"


class TestV2FrozenEval(unittest.TestCase):
    def test_frozen_corpus_route_a_labels_and_sha256_integrity(self):
        gt_csv = V2_DIR / "ground_truth.csv"
        self.assertTrue(gt_csv.is_file(), "ground_truth.csv missing")
        with gt_csv.open("r", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 16)

        # Route A unified rule: 9 CLEAN + 7 DEFECTIVE across 8 Haiku (5C/3D) + 8 Codex (4C/4D)
        haiku = [r for r in rows if r["executor_family"] == "claude-haiku"]
        codex = [r for r in rows if r["executor_family"] == "codex-cli"]
        self.assertEqual(len(haiku), 8)
        self.assertEqual(len(codex), 8)
        self.assertEqual(sum(1 for r in haiku if r["ground_truth"] == "CLEAN"), 5)
        self.assertEqual(sum(1 for r in haiku if r["ground_truth"] == "DEFECTIVE"), 3)
        self.assertEqual(sum(1 for r in codex if r["ground_truth"] == "CLEAN"), 4)
        self.assertEqual(sum(1 for r in codex if r["ground_truth"] == "DEFECTIVE"), 4)

        # Dry-run verifies SHA-256 of every single frozen workspace
        r = subprocess.run(
            [sys.executable, str(V2_DIR / "run_v2_factorial.py"), "--dry-run"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, f"SHA-256 verification failed: {r.stdout}\n{r.stderr}")
        self.assertIn("V2_FACTORIAL DRY_RUN OK", r.stdout)

    def test_locked_v2_layer1_reproduces_committed_predictions(self):
        committed = [
            json.loads(l)
            for l in (V2_DIR / "results_layer1.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        with tempfile.TemporaryDirectory() as td:
            out_fp = Path(td) / "repro_l1.jsonl"
            r = subprocess.run(
                [sys.executable, str(ROOT / "veriloop"), "eval-v2", "layer1", "--out-jsonl", str(out_fp)],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            repro = [json.loads(l) for l in out_fp.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(
            [(x["artifact_id"], x["predicted_defective"], x["details"]) for x in repro],
            [(x["artifact_id"], x["predicted_defective"], x["details"]) for x in committed],
        )

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

    def test_veriloop_eval_v2_summary_cli(self):
        r = subprocess.run(
            [sys.executable, str(ROOT / "veriloop"), "eval-v2", "summary"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ZERO OVERRIDES", r.stdout)
        self.assertIn("codex-cli", r.stdout)


if __name__ == "__main__":
    unittest.main()

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
import tempfile

SCRIPT = str(Path(__file__).resolve().parents[2] / "skills/research-loop/scripts/claims.py")


def run_claims(ws, *args):
    cmd = [sys.executable, SCRIPT, "-w", str(ws), *args]
    return subprocess.run(cmd, capture_output=True, text=True)


class TestClaimsLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        self.logs = self.ws / "out"
        self.logs.mkdir()
        self.method_log = self.logs / "method.txt"
        self.method_log.write_text("SUMMARY: R@200 0.3221±0.0042  ΔTail +0.1076[+0.0988,+0.1165]\n")
        self.ablation_log = self.logs / "ablation.txt"
        self.ablation_log.write_text("ABLATION: without_x 0.3010±0.0031\n")
        self.base_log = self.logs / "base.txt"
        self.base_log.write_text("BASE: R@200 0.2656±0.0102\n")
        self.knn_log = self.logs / "knn.txt"
        self.knn_log.write_text("KNN: R@200 0.2937\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _add_c1(self):
        r = run_claims(
            self.ws, "add", "C1",
            "--text", "Method beats Base and kNN on R@200",
            "--metric", "R@200",
            "--select-on", "valid",
            "--seeds", "3",
            "--baselines", "Base,kNN",
            "--kill", "Base matches Method",
            "--scope", "small",
        )
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_unsupported_status_accepted(self):
        self._add_c1()
        r = run_claims(self.ws, "status", "C1", "unsupported", "--by", "reviewer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("C1: unsupported", r.stdout)

    def test_full_gates_pass_and_allow_supported(self):
        self._add_c1()
        self.assertEqual(run_claims(
            self.ws, "evidence", "C1", "--log", str(self.method_log),
            "--dataset", "beauty", "--seeds", "3", "--selected-on", "valid",
            "--changes", "2", "--ablated", "2", "--has-ci", "--complete-marker", "SUMMARY"
        ).returncode, 0)
        self.assertEqual(run_claims(
            self.ws, "evidence", "C1", "--log", str(self.ablation_log),
            "--role", "ablation", "--dataset", "beauty", "--seeds", "3",
            "--selected-on", "valid", "--changes", "2", "--ablated", "2"
        ).returncode, 0)
        self.assertEqual(run_claims(
            self.ws, "evidence", "C1", "--arm", "Base", "--log", str(self.base_log),
            "--seeds", "3", "--selected-on", "valid"
        ).returncode, 0)
        self.assertEqual(run_claims(
            self.ws, "evidence", "C1", "--arm", "kNN", "--log", str(self.knn_log),
            "--deterministic", "--selected-on", "valid"
        ).returncode, 0)
        chk = run_claims(self.ws, "check", "--json")
        self.assertEqual(chk.returncode, 0)
        data = json.loads(chk.stdout)
        self.assertEqual(data["C1"]["passed"], 7)
        self.assertEqual(data["C1"]["total"], 7)
        st = run_claims(self.ws, "status", "C1", "supported", "--by", "reviewer")
        self.assertEqual(st.returncode, 0, st.stderr)

    def test_g1_detects_tampered_log_hash(self):
        self._add_c1()
        self.assertEqual(run_claims(
            self.ws, "evidence", "C1", "--log", str(self.method_log),
            "--seeds", "3", "--selected-on", "valid"
        ).returncode, 0)
        # Silently overwrite log after attaching evidence
        self.method_log.write_text("SUMMARY: R@200 0.9999±0.0001\n")
        chk = run_claims(self.ws, "check", "--json")
        fails = {f["gate"]: f["detail"] for f in json.loads(chk.stdout)["C1"]["failures"]}
        self.assertIn("G1 logs exist & intact", fails)
        self.assertIn("hash changed", fails["G1 logs exist & intact"])

    def test_g1_blocks_truncated_log_missing_marker(self):
        self._add_c1()
        trunc = self.logs / "trunc.txt"
        trunc.write_text("ep 5 loss 2.1\nep 10 loss 1.9\n")
        r = run_claims(
            self.ws, "evidence", "C1", "--log", str(trunc),
            "--seeds", "3", "--selected-on", "valid", "--complete-marker", "SUMMARY"
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("missing --complete-marker", r.stderr)

    def test_g2_per_dataset_and_per_arm_seed_check(self):
        self._add_c1()
        # Dataset A has 3 seeds, Dataset B has only 1 seed -> G2 MUST FAIL (fixes old max() bug!)
        self.assertEqual(run_claims(
            self.ws, "evidence", "C1", "--log", str(self.method_log),
            "--dataset", "beauty", "--seeds", "3", "--selected-on", "valid"
        ).returncode, 0)
        self.assertEqual(run_claims(
            self.ws, "evidence", "C1", "--log", str(self.method_log),
            "--dataset", "office", "--seeds", "1", "--selected-on", "valid"
        ).returncode, 0)
        # Non-deterministic baseline with only 1 seed -> also flagged
        self.assertEqual(run_claims(
            self.ws, "evidence", "C1", "--arm", "Base", "--log", str(self.base_log),
            "--seeds", "1", "--selected-on", "valid"
        ).returncode, 0)
        chk = run_claims(self.ws, "check", "--json")
        fails = {f["gate"]: f["detail"] for f in json.loads(chk.stdout)["C1"]["failures"]}
        self.assertIn("G2 seeds >= 3", fails)
        self.assertIn("dataset 'office'", fails["G2 seeds >= 3"])
        self.assertIn("baseline 'Base'", fails["G2 seeds >= 3"])

    def test_g5_requires_actual_ablation_log_not_just_flag(self):
        self._add_c1()
        self.assertEqual(run_claims(
            self.ws, "evidence", "C1", "--log", str(self.method_log),
            "--seeds", "3", "--selected-on", "valid", "--changes", "3", "--ablated", "3"
        ).returncode, 0)
        chk = run_claims(self.ws, "check", "--json")
        fails = {f["gate"]: f["detail"] for f in json.loads(chk.stdout)["C1"]["failures"]}
        self.assertIn("G5 ablations", fails)
        self.assertIn("no dedicated --role ablation log", fails["G5 ablations"])

    def test_g6_monotonic_sequence_same_second_no_collision(self):
        self._add_c1()
        # Attach evidence then revise in same second -> G6 MUST FAIL
        run_claims(self.ws, "evidence", "C1", "--log", str(self.method_log), "--seeds", "3", "--selected-on", "valid")
        run_claims(self.ws, "revise", "C1", "--text", "Narrowed wording", "--why", "post-hoc")
        chk1 = json.loads(run_claims(self.ws, "check", "--json").stdout)["C1"]
        self.assertTrue(any(f["gate"].startswith("G6") for f in chk1["failures"]))
        # Now attach NEW confirmatory evidence in same second -> G6 MUST PASS
        run_claims(self.ws, "evidence", "C1", "--log", str(self.method_log), "--seeds", "3", "--selected-on", "valid")
        chk2 = json.loads(run_claims(self.ws, "check", "--json").stdout)["C1"]
        self.assertFalse(any(f["gate"].startswith("G6") for f in chk2["failures"]))

    def test_g7_requires_real_ci_in_log(self):
        self._add_c1()
        no_ci = self.logs / "noci.txt"
        no_ci.write_text("R@200 All 0.3221 Tail 0.1971\n")
        # Claiming --has-ci on a log without CI must be rejected immediately
        r_bad = run_claims(self.ws, "evidence", "C1", "--log", str(no_ci), "--seeds", "3", "--selected-on", "valid", "--has-ci")
        self.assertNotEqual(r_bad.returncode, 0)
        # Attaching without --has-ci fails G7 on check
        run_claims(self.ws, "evidence", "C1", "--log", str(no_ci), "--seeds", "3", "--selected-on", "valid")
        chk = json.loads(run_claims(self.ws, "check", "--json").stdout)["C1"]
        self.assertTrue(any(f["gate"].startswith("G7") for f in chk["failures"]))

    def test_only_user_can_waive(self):
        self._add_c1()
        r_rev = run_claims(self.ws, "status", "C1", "supported", "--by", "reviewer", "--waive", "trust me")
        self.assertNotEqual(r_rev.returncode, 0)
        r_usr = run_claims(self.ws, "status", "C1", "supported", "--by", "user", "--waive", "approved pilot")
        self.assertEqual(r_usr.returncode, 0)


if __name__ == "__main__":
    unittest.main()

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parents[2] / "skills/research-loop/scripts/trace_numbers.py")


def run_tracer(report, logs, scripts=None, extra=()):
    cmd = [sys.executable, SCRIPT, str(report), "--logs", str(logs), "--json", *extra]
    if scripts:
        cmd.extend(["--scripts", str(scripts)])
    return subprocess.run(cmd, capture_output=True, text=True)


class TestTraceNumbers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        self.logs = self.ws / "out"
        self.scripts = self.ws / "scripts"
        self.logs.mkdir()
        self.scripts.mkdir()
        (self.logs / "run_a.txt").write_text(
            "ModelA | All 0.3221±0.0042 | Tail 0.1971±0.0060 | ΔAll -0.0106 [-0.0151,-0.0063]\n"
        )
        (self.logs / "run_b.txt").write_text(
            "ModelB | All 0.4392±0.0008 | Tail 0.2283±0.0068 | ΔAll +0.0418 [+0.0368,+0.0470]\n"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_report_passes(self):
        rep = self.ws / "rep.md"
        rep.write_text(
            "| Model | All | Tail | ΔAll | Log |\n"
            "|---|---|---|---|---|\n"
            "| A | 0.3221±0.0042 | 0.1971±0.0060 | -0.0106 [-0.0151,-0.0063] | run_a.txt |\n"
            "| B | 0.4392±0.0008 | 0.2283±0.0068 | +0.0418 [+0.0368,+0.0470] | run_b.txt |\n"
        )
        r = run_tracer(rep, self.logs)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(len(data["untraced"]), 0)
        self.assertEqual(len(data["sign_mismatches"]), 0)
        self.assertEqual(len(data["wrong_logs"]), 0)
        self.assertEqual(len(data["unpaired_pairs"]), 0)

    def test_sign_flip_caught(self):
        rep = self.ws / "rep.md"
        # Flips -0.0106 -> +0.0106!
        rep.write_text("| A | +0.0106 | run_a.txt |\n")
        r = run_tracer(rep, self.logs)
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertEqual(len(data["sign_mismatches"]), 1)
        self.assertEqual(data["sign_mismatches"][0]["number"], "+0.0106")

    def test_wrong_log_caught_when_row_cites_different_log(self):
        rep = self.ws / "rep.md"
        # 0.4392 exists in run_b.txt, NOT run_a.txt!
        rep.write_text("| A | 0.4392 | run_a.txt |\n")
        r = run_tracer(rep, self.logs)
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertEqual(len(data["wrong_logs"]), 1)
        self.assertEqual(data["wrong_logs"][0]["number"], "0.4392")

    def test_unpaired_pm_caught(self):
        rep = self.ws / "rep.md"
        # Mixes mean from All (0.3221) with std from Tail (0.0060) — both exist in run_a.txt, but never paired?
        # Wait: both are on the same line in run_a.txt, so mix across run_a and run_b!
        rep.write_text("Model hybrid: 0.3221±0.0068\n")
        r = run_tracer(rep, self.logs)
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertEqual(len(data["unpaired_pairs"]), 1)
        self.assertEqual(data["unpaired_pairs"][0]["kind"], "PM")

    def test_cited_stale_vs_workspace_stale(self):
        sc_a = self.scripts / "run_a.py"
        sc_b = self.scripts / "run_b.py"
        sc_a.write_text("print(1)\n")
        sc_b.write_text("print(2)\n")
        # Make run_b.py newer than run_b.txt, while report only cites run_a.txt
        t_old = os.path.getmtime(self.logs / "run_a.txt") - 10
        os.utime(sc_a, (t_old, t_old))
        t_new = os.path.getmtime(self.logs / "run_b.txt") + 100
        os.utime(sc_b, (t_new, t_new))

        rep = self.ws / "rep.md"
        rep.write_text("| A | 0.3221 | run_a.txt |\n")
        r = run_tracer(rep, self.logs, scripts=self.scripts, extra=("--strict-stale",))
        self.assertEqual(r.returncode, 0, r.stdout)
        data = json.loads(r.stdout)
        self.assertEqual(len(data["cited_stale"]), 0)
        self.assertEqual(len(data["workspace_stale"]), 1)

        # Now cite run_b.txt -> strict-stale must fail!
        rep.write_text("| B | 0.4392 | run_b.txt |\n")
        r2 = run_tracer(rep, self.logs, scripts=self.scripts, extra=("--strict-stale",))
        self.assertEqual(r2.returncode, 1)
        data2 = json.loads(r2.stdout)
        self.assertEqual(len(data2["cited_stale"]), 1)

    def test_unicode_minus_and_trailing_zeros_no_false_positive(self):
        (self.logs / "stats.txt").write_text(
            "p_value=1.0 slope=-0.4438 intercept=53.989 offset=0.20 F=0.6470+/-0.0030\n"
        )
        rep = self.ws / "rep.md"
        # Report uses Unicode minus U+2212, spaced binary subtraction, "+/-", and 3-decimal trailing zeros
        rep.write_text(
            "| fit | S = 53.989 \u2212 0.4438*P | b = \u22120.4438 | p = 1.000 | off = 0.200 | 0.6470 +/- 0.0030 | stats.txt |\n"
        )
        r = run_tracer(rep, self.logs)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(len(data["untraced"]), 0)
        self.assertEqual(len(data["sign_mismatches"]), 0)
        self.assertEqual(len(data["unpaired_pairs"]), 0)
        self.assertEqual(data["traced"], 7)

    def test_percent_fraction_unit_conversion_no_false_positive(self):
        (self.logs / "spr.txt").write_text(
            "depth=1 train_acc=0.87745 train_cwa=0.87764 dev_acc=0.88020 test_cwa=0.635402\n"
        )
        rep = self.ws / "rep.md"
        # Table reports percentages without trailing % while log prints fractions
        rep.write_text(
            "The table reports percentages.\n"
            "| depth | Train Acc | Train CWA | Dev Acc | Test CWA |\n"
            "|---:|---:|---:|---:|---:|\n"
            "| 1 | 87.745 | 87.764 | 88.020 | 63.5402% |\n"
            "Fabricated cell: 91.234\n"
        )
        r = run_tracer(rep, self.logs)
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        # 4 real unit-scaled numbers traced; only genuinely fabricated 91.234 is untraced!
        self.assertEqual(data["traced"], 4)
        self.assertEqual([u["number"] for u in data["untraced"]], ["91.234"])


if __name__ == "__main__":
    unittest.main()

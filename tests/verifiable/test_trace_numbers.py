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
        # Report uses Unicode minus U+2212, spaced binary subtraction, LaTeX en-dash range, "+/-", and 3-decimal trailing zeros
        rep.write_text(
            "| fit | S = 53.989 \u2212 0.4438*P | b = \u22120.4438 | p = 1.000 | off = 0.200 | 0.6470 +/- 0.0030 | range 0.200--0.6470 | stats.txt |\n"
        )
        r = run_tracer(rep, self.logs)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(len(data["untraced"]), 0)
        self.assertEqual(len(data["sign_mismatches"]), 0)
        self.assertEqual(len(data["unpaired_pairs"]), 0)
        self.assertEqual(data["traced"], 9)

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

    def test_data_flag_traces_raw_csv_without_stale_flag(self):
        data_dir = self.ws / "data"
        data_dir.mkdir()
        raw_csv = data_dir / "island_species.csv"
        raw_csv.write_text("island,area,species\nA,3.542,12\n")
        # Even if a script with the same stem is newer than the input CSV, --data is never flagged stale
        sc = self.scripts / "island_species.py"
        sc.write_text("print('analysis')\n")
        t_new = os.path.getmtime(raw_csv) + 100
        os.utime(sc, (t_new, t_new))

        rep = self.ws / "rep.md"
        rep.write_text("Model All=0.3221 on island area 3.542 (`island_species.csv`).\n")

        # Without --data, 3.542 is untraced
        r_no_data = run_tracer(rep, self.logs)
        self.assertEqual(r_no_data.returncode, 1)
        self.assertEqual([u["number"] for u in json.loads(r_no_data.stdout)["untraced"]], ["3.542"])

        # With --data and --strict-stale, 3.542 traces cleanly and is not marked stale
        r_with_data = run_tracer(
            rep, self.logs, scripts=self.scripts, extra=("--data", str(data_dir), "--strict-stale")
        )
        self.assertEqual(r_with_data.returncode, 0, r_with_data.stdout + r_with_data.stderr)
        d = json.loads(r_with_data.stdout)
        self.assertEqual(d["data_files"], 1)
        self.assertEqual(d["traced"], 2)
        self.assertEqual(len(d["untraced"]), 0)
        self.assertEqual(len(d["cited_stale"]), 0)

    def test_negative_direction_prose_polarity_preserves_explicit_sign_flip(self):
        (self.logs / "sota.txt").write_text("delta_pp=-1.4598\ndelta_f1=-0.0106\n")
        rep_ok = self.ws / "rep_ok.md"
        rep_ok.write_text(
            "Our model sits 1.4598 percentage points below SOTA and is lower by 0.0106.\n"
        )
        r_ok = run_tracer(rep_ok, self.logs)
        self.assertEqual(r_ok.returncode, 0, r_ok.stdout + r_ok.stderr)
        d_ok = json.loads(r_ok.stdout)
        self.assertEqual(d_ok["traced"], 2)
        self.assertEqual(len(d_ok["sign_mismatches"]), 0)

        # Explicit '+' sign MUST still be caught as SIGN_MISMATCH even next to negative-direction prose!
        rep_plus = self.ws / "rep_plus.md"
        rep_plus.write_text("Our model sits +1.4598 percentage points below SOTA.\n")
        r_plus = run_tracer(rep_plus, self.logs)
        self.assertEqual(r_plus.returncode, 1)
        self.assertEqual(len(json.loads(r_plus.stdout)["sign_mismatches"]), 1)

        # Unsigned table cell without directional prose MUST still be caught as SIGN_MISMATCH!
        rep_tbl = self.ws / "rep_tbl.md"
        rep_tbl.write_text("| Model | 0.0106 | sota.txt |\n")
        r_tbl = run_tracer(rep_tbl, self.logs)
        self.assertEqual(r_tbl.returncode, 1)
        self.assertEqual(len(json.loads(r_tbl.stdout)["sign_mismatches"]), 1)

        # Metric noun "loss" MUST NOT relax sign checking (e.g. "validation loss of 0.312" vs logged -0.312)!
        (self.logs / "loss.txt").write_text("val_loss=-0.3120\n")
        rep_loss = self.ws / "rep_loss.md"
        rep_loss.write_text("The model reached a validation loss of 0.3120 on dev.\n")
        r_loss = run_tracer(rep_loss, self.logs)
        self.assertEqual(r_loss.returncode, 1)
        self.assertEqual(len(json.loads(r_loss.stdout)["sign_mismatches"]), 1)


if __name__ == "__main__":
    unittest.main()

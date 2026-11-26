import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BP_DIR = ROOT / "skills/bestpaper-writing"
VERILOOP_CLI = ROOT / "veriloop"


class TestBestPaperIntegration(unittest.TestCase):
    def test_bestpaper_skill_assets_and_scripts_present(self):
        required = [
            BP_DIR / "SKILL.md",
            BP_DIR / "LICENSE",
            BP_DIR / "NOTICE.md",
            BP_DIR / "scripts/check_draft.py",
            BP_DIR / "scripts/check_figures.py",
            BP_DIR / "scripts/style_metrics.py",
            BP_DIR / "scripts/find_exemplars.py",
            BP_DIR / "scripts/intake_to_brief.py",
            BP_DIR / "assets/figures/bestpaper.mplstyle",
            BP_DIR / "assets/figures/plot_style.py",
        ]
        for path in required:
            self.assertTrue(path.is_file(), f"Missing bestpaper-writing asset: {path}")

    def test_check_draft_catches_dash_error(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "0_abstract.tex"
            bad.write_text(
                "\\begin{abstract}\n"
                "We propose a novel method --- which is very great --- for all benchmarks.\n"
                "\\end{abstract}\n",
                encoding="utf-8",
            )
            r = subprocess.run(
                [sys.executable, str(BP_DIR / "scripts/check_draft.py"), str(bad)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(r.returncode, 0, f"Expected non-zero on dash error: {r.stdout}")
            self.assertIn("ERROR", r.stdout)

    def test_veriloop_lint_paper_passes_on_companion_paper(self):
        r = subprocess.run(
            [sys.executable, str(VERILOOP_CLI), "lint-paper"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(r.returncode, 0, f"lint-paper failed:\n{r.stdout}\n{r.stderr}")
        self.assertIn("OK: no issues found", r.stdout)
        self.assertIn("0 error(s), 0 warning(s)", r.stdout)


if __name__ == "__main__":
    unittest.main()

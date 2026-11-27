"""Offline unit & integration tests for VeriLoop v5 AI-Researcher-surpassing suite:
  1. tools/paper_ingest.py         (arXiv/tar.gz LaTeX extraction, AST indexing, Formula<->Code alignment)
  2. tools/sandbox_runner.py       (Docker GPU dry-run command, local exec, NaN/OOM anomaly detection)
  3. tools/research_orchestrator.py (Level-1 & Level-2 7-stage pipeline, --resume, hard-block rc=2)
  4. tools/studio_server.py        (live HTTP API /api/state, /api/launch dry-run, --export-html)
"""
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import paper_ingest as pi  # noqa: E402
import studio_server as ss  # noqa: E402


def _make_sample_tex_tarball(dest: Path) -> Path:
    tex_body = r"""
\documentclass{article}
\title{Temperature Calibration for Deep Residual Networks}
\begin{document}
\begin{abstract}
We study temperature scaling calibration on CIFAR-10. Code: https://github.com/example/calib-resnet.
\end{abstract}
\section{Method}
We calibrate logits via temperature scaling using learning rate 0.1 and batch size 256 over 30 epochs:
\begin{equation}\label{eq:temp_scale}
p_{\text{cal}} = \mathrm{softmax}(z / T_{\text{temp}})
\end{equation}
We also propose a spectral entropy regularizer:
\begin{equation}\label{eq:unimplemented_spectral}
\mathcal{L}_{\text{zeta}} = \sum_k \omega_k \log \det(\Sigma_{\text{spectral}})
\end{equation}
\end{document}
"""
    tar_path = dest / "sample_paper.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        b = tex_body.encode("utf-8")
        info = tarfile.TarInfo("main.tex")
        info.size = len(b)
        tf.addfile(info, io.BytesIO(b))
        # Path-traversal attack entry that MUST be ignored safely
        evil = tarfile.TarInfo("../../evil.tex")
        evil.size = 4
        tf.addfile(evil, io.BytesIO(b"evil"))
    return tar_path


def _make_sample_repo(dest: Path) -> Path:
    repo = dest / "baseline_repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "calibration.py").write_text(
        '''import math

class TemperatureScaler:
    """Calibrate logits via temperature scaling softmax(z / temp)."""
    def forward(self, logits, temp):
        return softmax(logits / temp)

def softmax(x):
    return x
''',
        encoding="utf-8",
    )
    return repo


class TestPaperIngest(unittest.TestCase):
    def test_tar_extract_ast_index_and_formula_alignment(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            tar_p = _make_sample_tex_tarball(tmp)
            repo = _make_sample_repo(tmp)
            ws = tmp / "ws"

            r = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools/paper_ingest.py"),
                    "-w", str(ws), "--tex-dir", str(tar_p), "--repo", str(repo), "--json",
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            res = json.loads(r.stdout)
            self.assertEqual(res["papers"], 1)
            self.assertEqual(res["equations"], 2)
            self.assertGreaterEqual(res["code_symbols"], 2)
            self.assertGreaterEqual(res["alignments"], 1)
            self.assertEqual(res["unmatched_equations"], 1)
            self.assertFalse((tmp / "evil.tex").exists())

            manifest = json.loads((ws / "out/ingest_manifest.json").read_text(encoding="utf-8"))
            self.assertIn("https://github.com/example/calib-resnet", manifest["papers"][0]["github_urls"])
            aligned_ids = {a["equation_id"]: a["matched_symbol"] for a in manifest["alignments"]}
            self.assertEqual(aligned_ids.get("eq:temp_scale"), "TemperatureScaler")
            self.assertTrue((ws / "wiki/INGEST_MAP.md").is_file())


class TestSandboxRunner(unittest.TestCase):
    def test_docker_dry_run_and_local_anomaly_detection(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws"
            data = Path(td) / "data"
            data.mkdir(parents=True)

            # 1. Docker dry-run command verification
            r_dry = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools/sandbox_runner.py"),
                    "-w", str(ws), "--mode", "docker", "--gpus", "device=0",
                    "--data-dir", str(data), "--network-none",
                    "--cmd", "python3 train.py", "--dry-run", "--json",
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(r_dry.returncode, 0, r_dry.stderr)
            d = json.loads(r_dry.stdout)
            self.assertEqual(d["mode"], "docker")
            self.assertIn("--gpus", d["command"])
            self.assertIn("--network", d["command"])
            self.assertTrue(any(arg.endswith(":/data:ro") for arg in d["command"]))

            # 2. Local execution success + SHA-256 ledger + anomaly detection
            r_ok = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools/sandbox_runner.py"),
                    "-w", str(ws), "--mode", "local",
                    "--cmd", "echo 'val_acc=0.9123' && echo 'loss=nan'",
                    "--json",
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(r_ok.returncode, 0, r_ok.stderr)
            rec = json.loads(r_ok.stdout)
            self.assertIn("NAN_OR_INF", rec["anomalies"])
            self.assertTrue((ws / "out/sandbox_runs.jsonl").is_file())


class TestResearchOrchestrator(unittest.TestCase):
    def test_level2_end_to_end_pipeline_passes_gate_and_resumes(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            tar_p = _make_sample_tex_tarball(tmp)
            repo = _make_sample_repo(tmp)
            ws = tmp / "ws"
            (ws / "code").mkdir(parents=True)
            (ws / "code/train.py").write_text(
                '''import csv
import random
from pathlib import Path
out = Path("runs/csv")
out.mkdir(parents=True, exist_ok=True)
for seed in (42, 43, 44):
    rng = random.Random(seed)
    val = round(0.88 + rng.uniform(0.01, 0.05), 4)
    with (out / f"ModelA_s{seed}.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["epoch", "test_acc"])
        w.writeheader()
        w.writerow({"epoch": 1, "test_acc": val})
print("TRAINING COMPLETE")
''',
                encoding="utf-8",
            )

            # Run full Level-2 offline pipeline end to end
            r = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools/research_orchestrator.py"),
                    "-w", str(ws), "--level", "2",
                    "--tex-dir", str(tar_p), "--repo", str(repo),
                    "--train-cmd", f"{sys.executable} code/train.py",
                    "--json",
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            summary = json.loads(r.stdout)
            self.assertTrue(summary["gate_passed"])
            self.assertTrue((ws / "wiki/INGEST_MAP.md").is_file())
            self.assertTrue((ws / "wiki/RESEARCH_PLAN.md").is_file())
            self.assertTrue((ws / "claims.json").is_file())
            self.assertTrue((ws / "paper/bound/bound_macros.tex").is_file())
            self.assertTrue((ws / "audits/veriloop_gate.json").is_file())
            self.assertTrue((ws / "review_ui.html").is_file())

            # Resume run must succeed idempotently
            r2 = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools/research_orchestrator.py"),
                    "-w", str(ws), "--level", "2", "--resume", "--json",
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

    def test_level1_hard_blocks_on_fabricated_report(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws_bad"
            (ws / "out").mkdir(parents=True)
            (ws / "report").mkdir(parents=True)
            (ws / "out/run.log").write_text("test_acc=0.7123\n", encoding="utf-8")
            (ws / "report/report.md").write_text("Our method achieves 0.9988 accuracy.\n", encoding="utf-8")
            r = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools/research_orchestrator.py"),
                    "-w", str(ws), "--level", "1", "--idea", "Test fabrication catch",
                    "--report", str(ws / "report/report.md"), "--json",
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            summary = json.loads(r.stdout)
            self.assertFalse(summary["gate_passed"])


class TestStudioServer(unittest.TestCase):
    def test_export_static_html_and_live_http_endpoints(self):
        ws = ROOT / "examples/gpu-overnight-research"
        with tempfile.TemporaryDirectory() as td:
            snap_html = Path(td) / "studio.html"
            r = subprocess.run(
                [sys.executable, str(ROOT / "tools/studio_server.py"), "-w", str(ws), "--export-html", str(snap_html)],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            txt = snap_html.read_text(encoding="utf-8")
            self.assertIn("VeriLoop Studio", txt)
            self.assertIn("M7_SEResNet_Full", txt)

        # Live ephemeral HTTP server test
        srv = ThreadingHTTPServer(("127.0.0.1", 0), ss.make_handler(ws))
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["workspace_name"], "gpu-overnight-research")
                self.assertTrue(data["has_review_ui"])
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/launch",
                data=json.dumps({"level": 2, "dry_run": True, "papers": ["1706.04599"]}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                ld = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(ld["ok"])
                self.assertIn("DRY_RUN OK", ld["message"])
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()

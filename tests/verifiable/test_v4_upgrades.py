import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills/research-loop/scripts"))
sys.path.insert(0, str(ROOT / "tools"))

import citation_audit as ca  # noqa: E402
import paper_bind as pb  # noqa: E402
import review_ui as rui  # noqa: E402


class TestCitationAuditV2(unittest.TestCase):
    def test_online_gate_catches_title_author_year_and_retraction(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            bib = ws / "refs.bib"
            bib.write_text(
                "@article{real2025,\n"
                "  title={Deep Residual Learning for Image Recognition},\n"
                "  author={Kaiming He and Xiangyu Zhang},\n"
                "  year={2015},\n"
                "  eprint={1512.03385}\n"
                "}\n"
                "@article{halluc2026,\n"
                "  title={Fabricated Quantum Attention},\n"
                "  author={Jane Ghost},\n"
                "  year={2026},\n"
                "  doi={10.9999/fake.2026}\n"
                "}\n"
                "@article{mismatch2020,\n"
                "  title={Wrong Title Completely},\n"
                "  author={Alice Nobody},\n"
                "  year={2020},\n"
                "  doi={10.1000/retracted.1}\n"
                "}\n",
                encoding="utf-8",
            )
            tex = ws / "draft.tex"
            tex.write_text(
                "Residual connections improve image recognition \\citep{real2025}.\n"
                "Fake paper claims miracles \\citep{halluc2026}.\n"
                "Another work fails completely \\citep{mismatch2020}.\n",
                encoding="utf-8",
            )

            def fake_resolve(entry, cache=None):
                if "1512.03385" in entry.get("eprint", ""):
                    return {
                        "exists": True, "source": "arxiv", "arxiv_id": "1512.03385",
                        "title": "Deep Residual Learning for Image Recognition",
                        "authors": ["Kaiming He", "Xiangyu Zhang"], "year": "2015",
                        "abstract": "Residual connections improve deep image recognition accuracy on ImageNet.",
                        "retracted": False,
                    }
                if "10.9999/fake" in entry.get("doi", ""):
                    return {"exists": False, "source": "crossref", "error": "DOI 404"}
                return {
                    "exists": True, "source": "crossref", "doi": "10.1000/retracted.1",
                    "title": "Unrelated Biology Paper",
                    "authors": ["Bob Real"], "year": "2016",
                    "abstract": "Our method improves protein folding substantially.",
                    "retracted": True,
                }

            with mock.patch.object(ca, "resolve_reference_online", side_effect=fake_resolve):
                res = ca.audit_document(str(tex), bib_path=str(bib), online=True, check_claims=True)

            codes = {iss["code"] for iss in res["issues"]}
            self.assertIn("UNRESOLVED_REFERENCE", codes)
            self.assertIn("TITLE_MISMATCH", codes)
            self.assertIn("AUTHOR_MISMATCH", codes)
            self.assertIn("YEAR_MISMATCH", codes)
            self.assertIn("RETRACTED_PAPER", codes)
            # real2025 should verify cleanly with grounded abstract
            real_pair = [p for p in res["pairs"] if p["key"] == "real2025"][0]
            self.assertEqual(real_pair["status"], "VERIFIED_ONLINE")
            self.assertEqual(real_pair["claim_vs_abstract"]["status"], "GROUNDED_IN_ABSTRACT")

    def test_claim_vs_abstract_detects_polarity_conflict_and_format_bibtex(self):
        meta = {
            "title": "Negative Result on Naive Prompting",
            "authors": ["Ada Lovelace", "Alan Turing"],
            "year": "2025",
            "arxiv_id": "2501.00001",
            "abstract": "Naive prompting fails to reduce hallucinations and does not improve accuracy.",
        }
        cva = ca.check_claim_vs_abstract("Naive prompting significantly improves accuracy by 12.5%.", meta)
        self.assertEqual(cva["status"], "POTENTIAL_CONTRADICTION")
        self.assertTrue(cva["polarity_conflict"])
        self.assertIn("12.5%", cva["ungrounded_numbers"])

        bib_str = ca.format_bibtex(meta)
        self.assertIn("@article{lovelace2025negative,", bib_str)
        self.assertIn("eprint={2501.00001}", bib_str)


class TestPaperBind(unittest.TestCase):
    def test_ingests_tfevents_wandb_csv_and_traces_100_percent(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            # 1. Real binary TensorBoard tfevents for ResNet seeds 1 & 2
            for s, v_acc, t_acc in [(1, 0.9120, 0.9080), (2, 0.9180, 0.9140)]:
                pb.write_tfevents_scalars(
                    ws / "runs/tb" / f"ResNet_s{s}" / f"events.out.tfevents.s{s}",
                    [(1, "val_acc", v_acc - 0.05), (2, "val_acc", v_acc), (2, "test_acc", t_acc)],
                )
            # 2. W&B local run files for MLP seeds 1 & 2
            for s, v_acc, t_acc in [(1, 0.8510, 0.8480), (2, 0.8590, 0.8520)]:
                wb = ws / "runs/wandb" / f"MLP_s{s}" / "files"
                wb.mkdir(parents=True)
                (wb / "wandb-history.jsonl").write_text(
                    json.dumps({"method": "MLP", "seed": s, "_step": 1, "val_acc": v_acc - 0.04}) + "\n"
                    + json.dumps({"method": "MLP", "seed": s, "_step": 2, "val_acc": v_acc}) + "\n",
                    encoding="utf-8",
                )
                (wb / "wandb-summary.json").write_text(
                    json.dumps({"method": "MLP", "seed": s, "_step": 2, "val_acc": v_acc, "test_acc": t_acc}),
                    encoding="utf-8",
                )
            # 3. CSV for Linear baseline
            csv_p = ws / "runs/csv/Linear.csv"
            csv_p.parent.mkdir(parents=True)
            csv_p.write_text(
                "method,seed,epoch,val_acc,test_acc\n"
                "Linear,1,1,0.7800,0.7750\n"
                "Linear,2,1,0.7900,0.7850\n",
                encoding="utf-8",
            )

            out_dir = ws / "paper/bound"
            r = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools/paper_bind.py"),
                    "--inputs", str(ws / "runs"),
                    "--metrics", "val_acc", "test_acc",
                    "--curve-metric", "val_acc",
                    "--out-dir", str(out_dir),
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue((out_dir / "bound_metrics.txt").is_file())
            self.assertTrue((out_dir / "bound_macros.tex").is_file())
            self.assertTrue((out_dir / "bound_table.tex").is_file())
            self.assertTrue((out_dir / "provenance_manifest.json").is_file())

            # Every number in bound_table.tex MUST trace 100% cleanly to bound_metrics.txt!
            tr = subprocess.run(
                [
                    sys.executable, str(ROOT / "skills/research-loop/scripts/trace_numbers.py"),
                    str(out_dir / "bound_table.tex"),
                    "--logs", str(out_dir / "bound_metrics.txt"),
                    "--json",
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(tr.returncode, 0, tr.stdout + tr.stderr)
            d = json.loads(tr.stdout)
            self.assertGreaterEqual(d["traced"], 12)
            self.assertEqual(len(d["untraced"]), 0)
            self.assertEqual(len(d["sign_mismatches"]), 0)


class TestReviewUI(unittest.TestCase):
    def test_generates_self_contained_interactive_html(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            (ws / "out").mkdir()
            (ws / "code").mkdir()
            (ws / "out/run.log").write_text("ACC 0.9312\nDELTA -0.0250\n", encoding="utf-8")
            (ws / "code/eval.py").write_text("f1_scores = [0.9123, 0.9234, 0.9345, 0.9456]\n", encoding="utf-8")
            (ws / "refs.bib").write_text("@article{k1, title={Real Paper}, author={A. Smith}, year={2025}}\n", encoding="utf-8")
            rep = ws / "draft.tex"
            rep.write_text(
                "Our model achieves 0.9312 accuracy \\citep{k1}, but a fabricated 0.9999 fails \\citep{missing_key}.\n",
                encoding="utf-8",
            )
            out_html = ws / "review.html"
            r = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools/review_ui.py"),
                    "--report", str(rep),
                    "--logs", str(ws / "out"),
                    "--scripts", str(ws / "code"),
                    "--bib", str(ws / "refs.bib"),
                    "--out", str(out_html),
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            txt = out_html.read_text(encoding="utf-8")
            self.assertIn("HARD BLOCK", txt)
            self.assertIn("0.9312", txt)
            self.assertIn("jumpNumber", txt)
            self.assertIn("jumpCite", txt)
            self.assertIn("HARDCODED_METRIC_ARRAY", txt)


class TestPDFAudit(unittest.TestCase):
    def test_audits_icml2027_and_gpu_showcase_pdfs_with_expanded_macros(self):
        icml_pdf = ROOT / "paper/main_icml2027.pdf"
        gpu_pdf = ROOT / "examples/gpu-dl-benchmark/paper/gpu_showcase.pdf"
        self.assertTrue(icml_pdf.is_file())
        self.assertTrue(gpu_pdf.is_file())

        # 1. Main ICML 2027 double-blind PDF: <= 8 main pages, 0 Type-3, 0 anonymity leaks
        r1 = subprocess.run(
            [
                sys.executable, str(ROOT / "tools/pdf_audit.py"), str(icml_pdf),
                "--max-main-pages", "8",
                "--forbidden-terms", "Shanglin", "Zhan Shi", "shangliy",
                "--json",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        d1 = json.loads(r1.stdout)
        self.assertLessEqual(d1["main_body_end_page"], 8)
        self.assertEqual(d1["issues_count"], 0)
        self.assertEqual(len(d1["type3_fonts"]), 0)

        # 2. GPU showcase PDF: expanded LaTeX macros trace cleanly + PNG rendering works
        with tempfile.TemporaryDirectory() as td:
            r2 = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools/pdf_audit.py"), str(gpu_pdf),
                    "--logs",
                    str(ROOT / "examples/gpu-dl-benchmark/paper/bound/bound_metrics.txt"),
                    str(ROOT / "examples/gpu-dl-benchmark/out/gpu_runs.log"),
                    "--render-dir", td,
                    "--json",
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            d2 = json.loads(r2.stdout)
            self.assertEqual(d2["issues_count"], 0)
            self.assertGreaterEqual(d2["pdf_number_trace"]["traced"], 20)
            self.assertEqual(d2["pdf_number_trace"]["untraced"], 0)
            self.assertEqual(d2["pdf_number_trace"]["sign_mismatches"], 0)
            self.assertGreaterEqual(len(d2["rendered_pages"]), 3)


if __name__ == "__main__":
    unittest.main()

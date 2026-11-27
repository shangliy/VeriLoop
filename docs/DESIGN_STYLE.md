# VeriLoop Visual Design System — Looseleaf Paper-and-Ink Standard

This document records the canonical visual style adopted for the **VeriLoop** Project Homepage (`docs/index.html`) and flagship documentation graphics (`docs/assets/*`), inspired by [`kevintngo/looseleaf`](https://github.com/kevintngo/looseleaf) (MIT) and validated against `omni-ui-master` anti-AI-slop rules (`0 hints / 0 errors`).

---

## 1. Narrative & Positioning Split

Always preserve a clear boundary between **Repository Engineering** and **Academic Paper Contributions**:

- **Repository (`README.md`, `README_CN.md`, Hero & Platform sections of `docs/index.html`):**
  - Emphasize **full-stack capability and scale** ("大而强"): 6 zero-dependency stdlib engines (`ingest`, `sandbox`, `research`, `bind`, `gate`/`audit-pdf`, `studio`/`compare-bench`), 90+ skills, 115 real RTX 3060 Ti runs across CV/GNN/RecSys, cross-platform CI, and drop-in forensic auditing for external agents.
- **Companion Paper (`paper/main_icml2027.pdf`, `paper/main.pdf`, and Section 06 of `docs/index.html`):**
  - Emphasize **sharp, falsifiable scientific contributions**: dual-layer deterministic + path-isolated governance, 16-workspace (`245`-trial) SHA-256 frozen benchmark, 21-scenario blind out-of-sample FPR calibration, and external forensic + self-audited manuscript release.

---

## 2. Color & Material Tokens

| Role | Token / Hex | Usage |
| :--- | :--- | :--- |
| **Sage Desk Mat** | `--desk: #A5C0B4` + subtle 2-layer dot grain | Full-page canvas ground (`body`) and outer frame of SVG assets |
| **Cream Paper Sheet** | `--paper: #F6F1E6` / `--paper-bright: #FCFAF4` | Tactile content cards, tables, stacked sheets, sticky header strip |
| **Paper Wash / Tape** | `--paper-wash: #EDE6D6` / `--tape: rgba(237, 231, 213, 0.78)` | Table headers, code pills, angled masking tape on sheet corners |
| **Fountain-Pen Ink** | `--ink: #1E2421` / `--ink-2: #3F4944` | Primary typography, 1.6–1.8px ink outlines, hard offset button shadows (`2.5px 2.5px 0 #1E2421`) |
| **Terracotta Marker** | `--orange: #D96F3C` (`hover: #C25B2B`) | Primary CTA fill, hand-drawn hero underline, active tabs, baseline chart bars |
| **Ballpoint Blue Pen** | `--blue-pen: #2A5CA8` | Hyperlinks, CLI command text, circled peak highlights (`416 / 416 traced!`), contribution accents |
| **Forest Marker Green** | `--green-pen: #3B6E4B` / `#4A7C59` (`wash: #E8F2EA`) | VeriLoop chart bars, verified status badges, `v5.0` rubber stamp |
| **Red-Ink Margin / Alert** | `--red-pen: #C44536` / `--rule-red: #D99B8C` (`wash: #FDF1EF`) | Index-card top rules, dashed `rc=2` repair loop, forensic mismatch warnings |
| **Chalkboard / Carbon Cutout** | `#1F2623` (alert `#281D1C`) | Audit X-Ray provenance lens & terminal code blocks |

---

## 3. Typography

- **Display / Headings / Buttons:** `"Kevin Sans"` (MIT, loaded from `https://kevintngo.github.io/looseleaf/fonts/kevin-sans.css`, graceful fallback to `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`).
- **Body Prose:** System humanist sans (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`) for comfortable long-form reading.
- **Metrics, CLI, Code, Provenance:** `"IBM Plex Mono"` / `ui-monospace` with `font-variant-numeric: tabular-nums`.

---

## 4. Signature Paper-and-Ink Primitives

1. **Desk-to-Sheet Hierarchy:** Major section headings sit directly on the sage cutting mat (`#A5C0B4`); structured content sits on cream paper sheets (`#F6F1E6`) with subtle cast drop shadow (`0 10px 26px rgba(26, 42, 35, 0.16)`).
2. **Tactile Hardware (Decorative Only):** Angled masking tape strips (`.tape-tl`, `.tape-tr`), stacked index-card edges (`.stacked`), ruled notebook lines (`.ruled`), and SVG silver paperclips (`.clip-pin`) — always marked `aria-hidden="true"` and `pointer-events: none` so DOM semantics and text selection stay 100% native.
3. **Deterministic Hand-Drawn SVGs:** All vector diagrams (`veriloop_logo.svg`, `veriloop_overview.svg`, `veriloop_vs_ai_researcher.svg`) use fixed-seed quadratic wobble strokes (`passes=2`, primary + light secondary pass), solid marker fills, and handwritten blue/red ballpoint callouts.
4. **Anti-AI-Slop Rules:** Zero neon gradients, zero glowing dark-mode SaaS cards, zero decorative emojis, zero fake KPI bloat.

---

## 5. Verification Checklist Before Publishing Changes

1. Run `ui_slop_lint.py --strict docs/index.html` and require `0 hints / 0 errors`.
2. Render 2× Retina headless Chrome screenshots at `1440px` (desktop), `900px` (tablet, single-row header check), and `390px` (mobile, zero horizontal overflow) and visually inspect every image for font-width clipping (especially with wide `Kevin Sans` advance widths).
3. Run `./veriloop test` and verify GitHub Pages workflow (`pages.yml`) completes `build` + `deploy`.

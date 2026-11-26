# Milestone Dual-Model Audit Rubric & JSON Contract

Every independent reviewer (latest Claude and latest Gemini) evaluates the **exact same frozen SHA-256 artifact snapshot** using this rubric. Neither reviewer sees the other's response or any executor narrative summary.

## 1. Eight-Point Anti-Self-Deception Checklist

1. **Tautological / Circular Metrics (`TAUTOLOGY`):**
   - Does any headline metric follow mechanically from a configuration switch (e.g., defining "leakage" as "blocked=False" for a non-blocking baseline vs. "blocked=True" for a blocking method)?
   - Could a trivial always-block or always-approve system achieve a perfect score on the reported headline metric?
   - Is clean-output yield / precision / recall / FPR reported against an **independent** ground truth?

2. **Post-Hoc Overrides & Test-Set Tuning (`POSTHOC_OVERRIDE`):**
   - Do aggregation scripts contain hardcoded scenario overrides (e.g., `if scenario.startswith("05a"): return False`)?
   - Were deterministic rules or thresholds tuned after inspecting evaluation outputs without re-running on frozen unseen held-out tasks?

3. **False Positives Misreported as Findings (`FP_AS_RESULT`):**
   - Cross-check every claimed mechanical or reviewer catch against the underlying raw code, log, and audit text.
   - Flag any unit-conversion artifact (e.g., `0.65` vs. `65.0%`) or legitimate constant/reference print presented as a genuine fabrication catch.

4. **Confounded / Non-Paired Comparisons & Variance (`CONFOUNDED_ABLATION`):**
   - In ablations comparing reviewers or prompts, did all conditions evaluate the **exact same frozen artifacts** (same file hashes)?
   - Is model family (same vs. cross) decoupled from model capability (weak vs. strong)?
   - Are repeated trials or variance estimates provided where run-to-run variance could explain the observed difference?

5. **Selective Reporting (`SELECTIVE_REPORTING`):**
   - Are inconvenient baseline rows (e.g., a bare baseline matching the headline score), official benchmark verdicts (`auto_verdict`), or low approval/yield rates omitted from the prose?
   - Are minor wording caveats inflated into "fabrication" or "sycophancy" counts?

6. **Numerical, Unit, Sign & Code Provenance (`PROVENANCE`):**
   - Do headline numbers, tables, and captions trace cleanly to raw logs with matching signs, units, denominators, and sample sizes?
   - Are deterministic pre-audit flags actually verified (separating true positives from false positives)?

7. **Reproducibility & Release Hygiene (`REPRODUCIBILITY`):**
   - Are referenced evaluation logs, scripts, labels, and git commits actually included in the public repository (not `.gitignore`d or stranded in another local repo)?

8. **Claim Strength Calibration (`CLAIM_CALIBRATION`):**
   - Grade each headline claim strictly as one of:
     - `supported`: directly established by independent, non-circular evidence on disk
     - `partial`: holds only in a narrower scope or with an important caveat
     - `pilot`: directional signal only; confounded, underpowered, or single-run
     - `unsupported`: evidence on disk does not establish the claim
     - `refuted`: raw logs or code directly contradict the claim

## 2. Stage-Specific Focus

- **`M1-plan`**: Check whether the evaluation metric can be gamed, whether ground truth is independent of the systems under test, whether ablations are truly paired on frozen artifacts, and whether compute/API budgets are realistic.
- **`M2-experiments`**: Check raw aggregation code (`build_tables*.py`), raw JSONL logs, hardcoded overrides, false positives in deterministic gates, variance across runs, and omitted baselines/yield rates.
- **`M3-draft`**: Check claim-to-log alignment, table/caption honesty, selective omission between tables and prose, and whether limitations accurately bound every headline claim.
- **`M4-submission`**: Check all of the above plus public repo completeness, commit/artifact availability, double-blind anonymity (if applicable), and readiness for release.

## 3. Required JSON Response Contract

Both Gemini and Claude MUST end their review with a single fenced `json` block matching this exact schema:

```json
{
  "overall_decision": "APPROVE | REVISE | BLOCK",
  "confidence": "high | medium | low",
  "summary": "One concise sentence summarizing readiness and the decisive issue(s).",
  "claim_verdicts": [
    {
      "claim": "Short statement of the claim evaluated",
      "verdict": "supported | partial | pilot | unsupported | refuted",
      "reason": "Concrete evidence or flaw limiting this claim"
    }
  ],
  "findings": [
    {
      "severity": "BLOCKER | MAJOR | MINOR",
      "category": "TAUTOLOGY | POSTHOC_OVERRIDE | FP_AS_RESULT | CONFOUNDED_ABLATION | SELECTIVE_REPORTING | PROVENANCE | REPRODUCIBILITY | CLAIM_CALIBRATION",
      "title": "Short 4-10 word title",
      "file_line": "path/to/file:line (or artifact path)",
      "evidence": "Verbatim fact from the inspected file proving the issue",
      "smallest_fix": "Smallest concrete experiment, code edit, or claim narrowing that closes this finding"
    }
  ],
  "next_actions": [
    {
      "priority": "P0 | P1 | P2",
      "action": "Concrete revised next step",
      "done_criteria": "Checkable on-disk criterion proving the action is complete"
    }
  ],
  "checked_and_sound": [
    "Explicit list of files/metrics inspected and confirmed clean"
  ]
}
```

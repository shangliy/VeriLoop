"""Leakage / pipeline sanity control.

Re-fits the logistic-regression and gradient-boosted-tree models from
run_models.py with TRAIN labels randomly permuted (features unchanged).
If the pipeline leaks label information through features or evaluation,
dev accuracy would stay high; a correct pipeline should drop to ~50%.
Dev only; test is not touched here.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_models as rm  # noqa: E402


def main():
    Ttr, ytr = rm.load("train")
    Tdev, ydev = rm.load("dev")
    Xtr, _ = rm.rich_features(Ttr)
    Xdev, _ = rm.rich_features(Tdev)
    rng = np.random.default_rng(12345)
    yperm = rng.permutation(ytr)
    print(f"[control] train label mean (original)={ytr.mean():.4f} "
          f"(permuted)={yperm.mean():.4f}; "
          f"agreement original vs permuted={np.mean(yperm == ytr):.4f}")

    Rtr, Rdev = rm.standardize(Xtr.astype(np.float64),
                               Xdev.astype(np.float64))
    w, b = rm.fit_logreg(Rtr, yperm, lam=1e-3)
    print(f"[control] logreg-rich, permuted train labels -> "
          f"dev acc={rm.acc(rm.sigmoid(Rdev @ w + b), ydev):.4f}")

    out = rm.fit_gbt(Xtr, yperm, [Xdev], depth=3, rounds=200)
    for r, (pdev,) in sorted(out.items()):
        print(f"[control] gbt depth=3, permuted train labels, rounds={r} -> "
              f"dev acc={rm.acc(pdev, ydev):.4f}")


if __name__ == "__main__":
    main()

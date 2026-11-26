#!/usr/bin/env python3
"""Minimal 10-second pure-Python ML demo for testing the full 5-step research-loop.

Synthetic binary classification with clean train/valid/test splits (zero leakage):
  - baseline : unregularized linear perceptron (1-epoch)
  - method   : L2-regularized logistic regression with valid-selected learning rate
  - ablation : method without L2 regularization (isolating L2 contribution)
Prints deterministic seed metrics, valid-selected hyperparam, and paired bootstrap 95% CI.
"""
import argparse
import math
import random


def make_dataset(seed, n_train=600, n_valid=300, n_test=400, d=8):
    rng = random.Random(1000 + seed)
    w_true = [rng.gauss(0, 1) for _ in range(d)]

    def gen(n):
        xs, ys = [], []
        for _ in range(n):
            x = [rng.gauss(0, 1) for _ in range(d)]
            score = sum(a * b for a, b in zip(w_true, x)) + rng.gauss(0, 1.4)
            xs.append(x)
            ys.append(1 if score > 0 else 0)
        return xs, ys

    return gen(n_train), gen(n_valid), gen(n_test)


def sigmoid(z):
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def fit_logistic(xs, ys, lr, l2, epochs, seed):
    rng = random.Random(seed)
    d = len(xs[0])
    w = [0.0] * d
    b = 0.0
    idx = list(range(len(xs)))
    for _ in range(epochs):
        rng.shuffle(idx)
        for i in idx:
            x, y = xs[i], ys[i]
            p = sigmoid(sum(wi * xi for wi, xi in zip(w, x)) + b)
            err = p - y
            for j in range(d):
                w[j] -= lr * (err * x[j] + l2 * w[j])
            b -= lr * err
    return w, b


def eval_preds(w, b, xs, ys):
    hits = [1.0 if ((sum(wi * xi for wi, xi in zip(w, x)) + b) > 0) == bool(y) else 0.0 for x, y in zip(xs, ys)]
    return sum(hits) / len(hits), hits


def paired_bootstrap_ci(hits_a, hits_b, n_boot=1000, seed=0):
    rng = random.Random(seed)
    n = len(hits_a)
    diffs = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            i = rng.randrange(n)
            s += hits_a[i] - hits_b[i]
        diffs.append(s / n)
    diffs.sort()
    mean_d = sum(a - b for a, b in zip(hits_a, hits_b)) / n
    return mean_d, diffs[int(0.025 * n_boot)], diffs[int(0.975 * n_boot)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["baseline", "method", "ablation_nol2"], required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    (xtr, ytr), (xva, yva), (xte, yte) = make_dataset(a.seed)
    if a.arm == "baseline":
        w, b = fit_logistic(xtr, ytr, lr=0.05, l2=0.0, epochs=1, seed=a.seed)
        va_acc, _ = eval_preds(w, b, xva, yva)
        te_acc, te_hits = eval_preds(w, b, xte, yte)
        print(f"arm=baseline seed={a.seed} split=valid n={len(yva)} acc={va_acc:.4f}")
        print(f"arm=baseline seed={a.seed} split=test  n={len(yte)} acc={te_acc:.4f}")
    else:
        l2 = 0.05 if a.arm == "method" else 0.0
        best_lr, best_va, best_model = None, -1.0, None
        for lr in (0.005, 0.02, 0.08):
            w, b = fit_logistic(xtr, ytr, lr=lr, l2=l2, epochs=12, seed=a.seed)
            va_acc, _ = eval_preds(w, b, xva, yva)
            if va_acc > best_va:
                best_va, best_lr, best_model = va_acc, lr, (w, b)
        te_acc, te_hits = eval_preds(*best_model, xte, yte)
        # Also evaluate baseline on identical test set for paired bootstrap CI
        wb, bb = fit_logistic(xtr, ytr, lr=0.05, l2=0.0, epochs=1, seed=a.seed)
        _, base_hits = eval_preds(wb, bb, xte, yte)
        d, lo, hi = paired_bootstrap_ci(te_hits, base_hits, seed=a.seed)
        print(f"arm={a.arm} seed={a.seed} selected_on=valid best_lr={best_lr} val_acc={best_va:.4f}")
        print(f"arm={a.arm} seed={a.seed} split=test n={len(yte)} acc={te_acc:.4f} Δvs_base={d:+.4f} 95% CI [{lo:+.4f},{hi:+.4f}]")
    print("SUMMARY_COMPLETE")


if __name__ == "__main__":
    main()

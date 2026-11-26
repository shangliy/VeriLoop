"""SPR_BENCH: learn the hidden rule as a conjunction of atomic predicates.

Pipeline (all CPU, numpy only):
 1. Encode each sequence into shape/color index arrays.
 2. Build a large library of atomic predicates (Shape-Count, Color-Count,
    Parity, Color-Position, Shape-Position, Order) as boolean vectors.
 3. Greedy conjunction learner: keep predicates that are satisfied by ALL
    training positives (a conjunction must hold on every accept), then greedily
    pick the predicate that rejects the most still-accepted training negatives.
    Stop when no negatives remain accepted or when the cap is reached.
 4. Dev is used to choose the cap (number of predicates); test is reported once.
Baselines: majority class, shape-count lookup, and L2 logistic regression on the
same predicate library (trained with plain gradient descent).
"""
import csv, sys, numpy as np

D = "data/SPR_BENCH/"
SHAPES, COLORS = "▲■●◆", "rgby"
SI = {c: i for i, c in enumerate(SHAPES)}
CI = {c: i for i, c in enumerate(COLORS)}


def load(name):
    with open(D + name, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    seqs = [r["sequence"].split() for r in rows]
    y = np.array([int(r["label"]) for r in rows], dtype=np.int64)
    S = np.array([[SI[t[0]] for t in s] for s in seqs])
    C = np.array([[CI[t[1]] for t in s] for s in seqs])
    return S, C, y


def first_last(M, val, L):
    """first/last index of value `val` per row (99 / -1 if absent)."""
    hit = (M == val)
    idx = np.arange(L)[None, :]
    first = np.where(hit.any(1), np.where(hit, idx, 99).min(1), 99)
    last = np.where(hit.any(1), np.where(hit, idx, -1).max(1), -1)
    return first, last


def build_library(S, C):
    """Return (feature matrix bool [N,P], names list)."""
    N, L = S.shape
    feats, names = [], []

    def add(v, name):
        feats.append(v)
        names.append(name)

    shape_cnt = np.stack([(S == s).sum(1) for s in range(4)], 1)  # N x 4
    color_cnt = np.stack([(C == c).sum(1) for c in range(4)], 1)
    for s in range(4):
        for k in range(0, L + 1):
            add(shape_cnt[:, s] == k, f"Count(shape{SHAPES[s]})=={k}")
            add(shape_cnt[:, s] >= k, f"Count(shape{SHAPES[s]})>={k}")
        add(shape_cnt[:, s] % 2 == 0, f"Parity(shape{SHAPES[s]})=even")
        add(shape_cnt[:, s] % 2 == 1, f"Parity(shape{SHAPES[s]})=odd")
    for c in range(4):
        for k in range(0, L + 1):
            add(color_cnt[:, c] == k, f"Count(color{COLORS[c]})=={k}")
            add(color_cnt[:, c] >= k, f"Count(color{COLORS[c]})>={k}")
        add(color_cnt[:, c] % 2 == 0, f"Parity(color{COLORS[c]})=even")
        add(color_cnt[:, c] % 2 == 1, f"Parity(color{COLORS[c]})=odd")
    for i in range(L):
        for s in range(4):
            add(S[:, i] == s, f"Pos{i}=shape{SHAPES[s]}")
        for c in range(4):
            add(C[:, i] == c, f"Pos{i}=color{COLORS[c]}")
        for s in range(4):
            for c in range(4):
                add((S[:, i] == s) & (C[:, i] == c), f"Pos{i}={SHAPES[s]}{COLORS[c]}")
    fS, lS = zip(*[first_last(S, s, L) for s in range(4)])
    fC, lC = zip(*[first_last(C, c, L) for c in range(4)])
    for a in range(4):
        for b in range(4):
            if a == b:
                continue
            add(fS[a] < fS[b], f"Order first(shape{SHAPES[a]})<first(shape{SHAPES[b]})")
            add(fS[a] < lS[b], f"Order exists shape{SHAPES[a]} before shape{SHAPES[b]}")
            add(fC[a] < fC[b], f"Order first(color{COLORS[a]})<first(color{COLORS[b]})")
            add(fC[a] < lC[b], f"Order exists color{COLORS[a]} before color{COLORS[b]}")
    # upper-bound count atoms (Count <= k), shape and color
    for s in range(4):
        for k in range(0, L + 1):
            add(shape_cnt[:, s] <= k, f"Count(shape{SHAPES[s]})<={k}")
    for c in range(4):
        for k in range(0, L + 1):
            add(color_cnt[:, c] <= k, f"Count(color{COLORS[c]})<={k}")
    # token-level (shape+color) counts and first/last order
    tok = S * 4 + C  # token id 0..15
    for t in range(16):
        tc = (tok == t).sum(1)
        tname = SHAPES[t // 4] + COLORS[t % 4]
        for k in range(0, L + 1):
            add(tc == k, f"Count(token{tname})=={k}")
            add(tc >= k, f"Count(token{tname})>={k}")
            add(tc <= k, f"Count(token{tname})<={k}")
    ftk, ltk = zip(*[first_last(tok, t, L) for t in range(16)])
    for a in range(16):
        for b in range(16):
            if a != b:
                add(ftk[a] < ftk[b], f"Order first(token{SHAPES[a//4]+COLORS[a%4]})<first(token{SHAPES[b//4]+COLORS[b%4]})")
    return np.stack(feats, 1), names


def greedy_conjunction(X, y, names, cap):
    """Learn an AND of predicates; every chosen predicate is true on all positives."""
    pos = y == 1
    valid = X[pos].all(0)                      # predicates true on every positive
    cand = np.where(valid)[0]
    alive = ~pos                                 # negatives still accepted
    chosen = []
    while alive.any() and len(chosen) < cap:
        # number of still-accepted negatives each candidate would reject
        gain = (~X[alive][:, cand]).sum(0)
        best = cand[np.argmax(gain)]
        if gain.max() == 0:
            break
        chosen.append(best)
        alive &= X[:, best]
        cand = np.delete(cand, np.argmax(gain))
    return chosen


def predict_conj(X, chosen):
    if not chosen:
        return np.ones(X.shape[0], dtype=np.int64)
    return X[:, chosen].all(1).astype(np.int64)


def acc(p, y):
    return float((p == y).mean())


def logreg(X, y, l2, lr=0.5, iters=400):
    Xf = X.astype(np.float64)
    w = np.zeros(Xf.shape[1]); b = 0.0
    for _ in range(iters):
        z = Xf @ w + b
        p = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
        g = (p - y) / len(y)
        w -= lr * (Xf.T @ (p - y) / len(y) + l2 * w)
        b -= lr * g.sum()
    return w, b


def main():
    Str, Ctr, ytr = load("train.csv")
    Sdv, Cdv, ydv = load("dev.csv")
    Ste, Cte, yte = load("test.csv")
    print(f"sizes train={len(ytr)} dev={len(ydv)} test={len(yte)}")
    print(f"label means train={ytr.mean():.3f} dev={ydv.mean():.3f} test={yte.mean():.3f}")

    Xtr, names = build_library(Str, Ctr)
    Xdv, _ = build_library(Sdv, Cdv)
    Xte, _ = build_library(Ste, Cte)
    print(f"predicate library size: {Xtr.shape[1]}")

    # Baselines
    maj = int(ytr.mean() >= 0.5)
    print(f"[baseline] majority class: dev={acc(np.full(len(ydv), maj), ydv):.4f} test={acc(np.full(len(yte), maj), yte):.4f}")
    ti = names.index("Count(shape▲)==2")
    print(f"[baseline] rule only Count(▲)==2: dev={acc(Xdv[:, ti].astype(int), ydv):.4f} test={acc(Xte[:, ti].astype(int), yte):.4f}")

    # Conjunction learner: choose cap on dev
    print("\n[conjunction learner] cap -> train/dev accuracy")
    best = None
    for cap in range(1, 13):
        ch = greedy_conjunction(Xtr, ytr, names, cap)
        a_tr = acc(predict_conj(Xtr, ch), ytr)
        a_dv = acc(predict_conj(Xdv, ch), ydv)
        print(f"  cap={cap:2d} |rule|={len(ch):2d} train={a_tr:.4f} dev={a_dv:.4f}")
        if best is None or a_dv > best[0] + 1e-9:
            best = (a_dv, cap, ch)
    a_dv, cap, ch = best
    print(f"\nselected cap={cap} (dev={a_dv:.4f}); learned rule:")
    for c in ch:
        print("   AND", names[c])
    a_te = acc(predict_conj(Xte, ch), yte)
    print(f"[conjunction learner] FINAL test accuracy = {a_te:.4f}")

    # Logistic regression on the same predicate library, L2 selected on dev
    print("\n[logistic regression on predicate library]")
    best_lr = None
    for l2 in [1e-4, 1e-3, 1e-2]:
        w, b = logreg(Xtr, ytr, l2)
        p_dv = ((Xdv.astype(float) @ w + b) > 0).astype(int)
        a = acc(p_dv, ydv)
        print(f"  l2={l2:g} train={acc(((Xtr.astype(float) @ w + b) > 0).astype(int), ytr):.4f} dev={a:.4f}")
        if best_lr is None or a > best_lr[0]:
            best_lr = (a, l2, w, b)
    a_dv_lr, l2, w, b = best_lr
    a_te_lr = acc(((Xte.astype(float) @ w + b) > 0).astype(int), yte)
    print(f"  selected l2={l2:g}; test accuracy = {a_te_lr:.4f}")

    print("\nSUMMARY")
    print(f"  conjunction learner (final, selected on dev): test={a_te:.4f}  dev={a_dv:.4f}")
    print(f"  logistic regression (selected on dev):        test={a_te_lr:.4f}  dev={a_dv_lr:.4f}")
    print(f"  SOTA reference: 0.800")


if __name__ == "__main__":
    main()

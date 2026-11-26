"""SPR_BENCH model comparison (CPU, numpy only).

Protocol
--------
* All models are fit on train.csv only.
* Hyperparameters / checkpoints are selected by dev accuracy only.
* Each family is scored on test.csv exactly once, at its dev-selected setting.
* The final model is the family with the highest dev accuracy (test is
  reported for every family for transparency, but it is not used for selection).

Families
--------
A  majority-class baseline
B  logistic regression on bag-of-tokens counts (16 features)
C  logistic regression on rich symbolic features (positional, pairwise, counts)
D  gradient-boosted depth-limited trees (logistic loss, Newton leaves) on rich features
E  one-hidden-layer MLP on rich features (epoch selected on dev)
"""
import csv
import os
import time

import numpy as np

SHAPES = ["▲", "■", "●", "◆"]
COLORS = ["b", "g", "r", "y"]
L = 16
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data", "SPR_BENCH")
SEED = 0


def load(split):
    with open(os.path.join(DATA, f"{split}.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    T = np.zeros((len(rows), L), dtype=np.int64)
    for i, r in enumerate(rows):
        for j, tok in enumerate(r["sequence"].split()):
            T[i, j] = SHAPES.index(tok[0]) * 4 + COLORS.index(tok[1])
    y = np.array([int(r["label"]) for r in rows], dtype=np.float64)
    return T, y


def rich_features(T):
    """Symbolic features. Token id = shape*4 + color."""
    n = T.shape[0]
    S, C = T // 4, T % 4
    P = np.zeros((n, L, 16), dtype=np.float64)
    P[np.arange(n)[:, None], np.arange(L)[None, :], T] = 1.0
    PS = np.eye(4)[S]
    PC = np.eye(4)[C]
    names, blocks = [], []

    def add(block, prefix):
        blocks.append(block.reshape(n, -1))
        k = block.reshape(n, -1).shape[1]
        names.extend([f"{prefix}[{i}]" for i in range(k)])

    add(P, "pos_tok")                       # token id at position (16x16)
    add(PS, "pos_shape")                    # shape at position (16x4)
    add(PC, "pos_color")                    # color at position (16x4)
    cnt_tok = P.sum(1)
    cnt_shape = PS.sum(1)
    cnt_color = PC.sum(1)
    add(cnt_tok, "count_tok")
    add(cnt_shape, "count_shape")
    add(cnt_color, "count_color")
    add(np.concatenate([cnt_shape % 2, cnt_color % 2, cnt_tok % 2], 1),
        "parity")
    E = np.cumsum(P, axis=1) - P            # tokens strictly before position j
    order = np.einsum("nja,njb->nab", E, P)  # ordered pairs a before b (any gap)
    adj = np.einsum("nja,njb->nab", P[:, :-1], P[:, 1:])  # a immediately before b
    add((order > 0).astype(np.float64), "ord_pair")
    add((adj > 0).astype(np.float64), "adj_pair")
    # first / last occurrence index of each shape and color (16 = absent)
    for grp, M_all, lab in [(4, PS, "shape"), (4, PC, "color")]:
        for g in range(grp):
            M = M_all[:, :, g] > 0
            any_ = M.any(1)
            first = np.where(any_, M.argmax(1), L)
            last = np.where(any_, L - 1 - M[:, ::-1].argmax(1), L)
            add(np.stack([first, last], 1).astype(np.float64),
                f"first_last_{lab}{g}")
    X = np.concatenate(blocks, axis=1).astype(np.int16)  # all counts <= 16
    return X, names


def bag_counts(T):
    """Family B features: occurrence count of each of the 16 tokens per row."""
    n = T.shape[0]
    counts = np.zeros((n, 16), dtype=np.float64)
    for tok in range(16):
        counts[:, tok] = (T == tok).sum(1)
    return counts


def standardize(Xtr, *others):
    mu = Xtr.mean(0)
    sd = Xtr.std(0)
    sd[sd == 0] = 1.0
    return [(Xtr - mu) / sd] + [(Xo - mu) / sd for Xo in others]


def acc(p, y):
    return float(np.mean((p > 0.5).astype(np.float64) == y))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


# ---------------------------------------------------------------- logistic reg
def fit_logreg(X, y, lam, iters=600, lr=0.05):
    """Full-batch Adam on L2-regularised logistic loss (weights and bias)."""
    n, d = X.shape
    w, b = np.zeros(d), 0.0
    mw, vw = np.zeros(d), np.zeros(d)
    mb, vb = 0.0, 0.0
    b1, b2, eps = 0.9, 0.999, 1e-8
    for t in range(1, iters + 1):
        r = (sigmoid(X @ w + b) - y) / n
        gw = X.T @ r + lam * w
        gb = r.sum()
        mw = b1 * mw + (1 - b1) * gw
        vw = b2 * vw + (1 - b2) * gw ** 2
        mb = b1 * mb + (1 - b1) * gb
        vb = b2 * vb + (1 - b2) * gb ** 2
        bc1, bc2 = 1 - b1 ** t, 1 - b2 ** t
        w = w - lr * (mw / bc1) / (np.sqrt(vw / bc2) + eps)
        b = b - lr * (mb / bc1) / (np.sqrt(vb / bc2) + eps)
    return w, b


# ------------------------------------------------------------ boosted trees
MIN_HESS = 2.0
CHECKPOINTS = (50, 100, 200)


def build_tree(Xc, g, h, depth, lam, K):
    F = Xc.shape[1]
    offs = (np.arange(F, dtype=np.intp) * K)[None, :]

    def rec(idx, d):
        G, H = g[idx].sum(), h[idx].sum()
        leaf = ("leaf", -G / (H + lam))
        if d == 0 or idx.size < 8:
            return leaf
        flat = (Xc[idx].astype(np.intp) + offs).ravel()
        GH = np.bincount(flat, np.repeat(g[idx], F), minlength=F * K).reshape(F, K)
        HH = np.bincount(flat, np.repeat(h[idx], F), minlength=F * K).reshape(F, K)
        GL, HL = np.cumsum(GH, 1), np.cumsum(HH, 1)
        GR, HR = G - GL, H - HL
        gain = GL ** 2 / (HL + lam) + GR ** 2 / (HR + lam) - G * G / (H + lam)
        gain = np.where((HL >= MIN_HESS) & (HR >= MIN_HESS), gain, -np.inf)
        f, k = np.unravel_index(np.argmax(gain), gain.shape)
        if not np.isfinite(gain[f, k]) or gain[f, k] <= 1e-7:
            return leaf
        m = Xc[idx, f] <= k
        return ("split", f, k, rec(idx[m], d - 1), rec(idx[~m], d - 1))

    return rec(np.arange(Xc.shape[0]), depth)


def tree_predict(tree, Xc):
    out = np.zeros(Xc.shape[0])

    def rec(node, idx):
        if node[0] == "leaf":
            out[idx] = node[1]
            return
        _, f, k, left, right = node
        m = Xc[idx, f] <= k
        rec(left, idx[m])
        rec(right, idx[~m])

    rec(tree, np.arange(Xc.shape[0]))
    return out


def fit_gbt(Xtr, ytr, Xev_list, depth, rounds, lr=0.1, lam=1.0,
            colsample=0.25, seed=SEED):
    """Returns dict checkpoint -> list of per-eval-set probabilities."""
    rng = np.random.default_rng(seed)
    n, F = Xtr.shape
    K = int(max(Xtr.max(), max(X.max() for X in Xev_list))) + 1
    Fr = np.zeros(n)
    Fev = [np.zeros(X.shape[0]) for X in Xev_list]
    out = {}
    ncol = max(1, int(colsample * F))
    for r in range(1, rounds + 1):
        p = sigmoid(Fr)
        g, h = p - ytr, np.maximum(p * (1 - p), 1e-6)
        del p
        cols = np.sort(rng.choice(F, size=ncol, replace=False))
        Xc = Xtr[:, cols]
        tree = build_tree(Xc, g, h, depth, lam, K)
        Fr += lr * tree_predict(tree, Xc)
        for i, X in enumerate(Xev_list):
            Fev[i] += lr * tree_predict(tree, X[:, cols])
        if r in CHECKPOINTS:
            out[r] = [sigmoid(f) for f in Fev]
    return out


# ------------------------------------------------------------------- MLP
def fit_mlp(Xtr, ytr, Xdev, ydev, hidden=256, epochs=30, lr=1e-3, wd=1e-4,
            batch=256, seed=SEED):
    rng = np.random.default_rng(seed)
    n, d = Xtr.shape
    W1 = rng.normal(0, np.sqrt(2.0 / d), (d, hidden))
    b1 = np.zeros(hidden)
    W2 = rng.normal(0, np.sqrt(1.0 / hidden), (hidden, 1))
    b2 = np.zeros(1)
    params = [W1, b1, W2, b2]
    mom = [np.zeros_like(p) for p in params]
    vel = [np.zeros_like(p) for p in params]
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    step = 0
    best = (-1.0, None, -1)
    history = []
    for ep in range(1, epochs + 1):
        perm = rng.permutation(n)
        for s in range(0, n, batch):
            idx = perm[s:s + batch]
            xb, yb = Xtr[idx], ytr[idx]
            z1 = xb @ W1 + b1
            a1 = np.maximum(z1, 0)
            p = sigmoid((a1 @ W2 + b2).ravel())
            dz2 = ((p - yb) / len(idx))[:, None]
            gW2 = a1.T @ dz2 + wd * W2
            gb2 = dz2.sum(0)
            da1 = dz2 @ W2.T
            dz1 = da1 * (z1 > 0)
            gW1 = xb.T @ dz1 + wd * W1
            gb1 = dz1.sum(0)
            grads = [gW1, gb1, gW2, gb2]
            step += 1
            for i, (pp, gg) in enumerate(zip(params, grads)):
                mom[i] = beta1 * mom[i] + (1 - beta1) * gg
                vel[i] = beta2 * vel[i] + (1 - beta2) * gg ** 2
                mh = mom[i] / (1 - beta1 ** step)
                vh = vel[i] / (1 - beta2 ** step)
                pp -= lr * mh / (np.sqrt(vh) + eps)
        pdev = sigmoid((np.maximum(Xdev @ W1 + b1, 0) @ W2 + b2).ravel())
        dev_acc = acc(pdev, ydev)
        history.append((ep, dev_acc))
        if dev_acc > best[0]:
            best = (dev_acc, [q.copy() for q in params], ep)
    return best, history, params


def mlp_predict(params, X):
    W1, b1, W2, b2 = params
    return sigmoid((np.maximum(X @ W1 + b1, 0) @ W2 + b2).ravel())


# ------------------------------------------------------------------- main
def main():
    t0 = time.time()
    Ttr, ytr = load("train")
    Tdev, ydev = load("dev")
    Tte, yte = load("test")
    print(f"[data] train={len(ytr)} dev={len(ydev)} test={len(yte)}")

    Xr_tr, names = rich_features(Ttr)
    Xr_dev, _ = rich_features(Tdev)
    Xr_te, _ = rich_features(Tte)
    print(f"[features] rich_dim={Xr_tr.shape[1]}")

    results = {}  # family -> dict(dev=..., test=..., config=...)

    # A. majority baseline
    maj = float(ytr.mean() >= 0.5)
    results["A_majority"] = dict(
        dev=acc(np.full(len(ydev), maj), ydev),
        test=acc(np.full(len(yte), maj), yte),
        config=f"constant={int(maj)}")
    print(f"[A majority] dev={results['A_majority']['dev']:.4f} "
          f"test={results['A_majority']['test']:.4f}")

    # B. logistic regression on bag-of-tokens counts
    cnt_tr, cnt_dev, cnt_te = bag_counts(Ttr), bag_counts(Tdev), bag_counts(Tte)
    Ctr, Cdev, Cte = standardize(cnt_tr, cnt_dev, cnt_te)
    best = None
    for lam in [1e-3, 1e-2, 1e-1, 1.0]:
        w, b = fit_logreg(Ctr, ytr, lam)
        d = acc(sigmoid(Cdev @ w + b), ydev)
        print(f"[B logreg-bag] lam={lam} dev={d:.4f}")
        if best is None or d > best[0]:
            best = (d, lam, w, b)
    d, lam, w, b = best
    results["B_logreg_bag_of_tokens"] = dict(
        dev=d, test=acc(sigmoid(Cte @ w + b), yte), config=f"lam={lam}")

    # C. logistic regression on rich features
    Rtr, Rdev, Rte = standardize(Xr_tr.astype(np.float64),
                                 Xr_dev.astype(np.float64),
                                 Xr_te.astype(np.float64))
    best = None
    for lam in [1e-3, 1e-2, 1e-1, 1.0]:
        w, b = fit_logreg(Rtr, ytr, lam)
        d = acc(sigmoid(Rdev @ w + b), ydev)
        print(f"[C logreg-rich] lam={lam} dev={d:.4f}")
        if best is None or d > best[0]:
            best = (d, lam, w, b)
    d, lam, w, b = best
    results["C_logreg_rich"] = dict(
        dev=d, test=acc(sigmoid(Rte @ w + b), yte), config=f"lam={lam}")

    # D. gradient-boosted trees on rich (integer-coded) features
    best = None
    for depth in [2, 3, 4]:
        out = fit_gbt(Xr_tr, ytr, [Xr_dev, Xr_te], depth=depth,
                      rounds=max(CHECKPOINTS))
        for r, (pdev, pte) in sorted(out.items()):
            d = acc(pdev, ydev)
            print(f"[D gbt] depth={depth} rounds={r} dev={d:.4f}")
            if r in out and (best is None or d > best[0]):
                best = (d, depth, r, pte)
        print(f"[D gbt] depth={depth} done t={time.time() - t0:.1f}s")
    d, depth, r, pte = best
    results["D_gbt_trees"] = dict(dev=d, test=acc(pte, yte),
                                  config=f"depth={depth},rounds={r},lr=0.1")

    # E. MLP on standardized rich features; epoch chosen on dev
    (bdev, bparams, bep), hist, _ = fit_mlp(Rtr, ytr, Rdev, ydev,
                                            hidden=256, epochs=20)
    for ep, da in hist:
        print(f"[E mlp] epoch={ep} dev={da:.4f}")
    results["E_mlp"] = dict(dev=bdev, test=acc(mlp_predict(bparams, Rte), yte),
                            config=f"hidden=256,epoch={bep},lr=1e-3,wd=1e-4,max_epochs=20")

    print("\n=== Summary (selection by dev; test evaluated once per family) ===")
    for k, v in results.items():
        print(f"{k:28s} dev={v['dev']:.4f} test={v['test']:.4f} [{v['config']}]")
    final = max(results, key=lambda k: results[k]["dev"])
    print(f"\nFINAL (highest dev accuracy): {final} "
          f"dev={results[final]['dev']:.4f} test={results[final]['test']:.4f}")
    print(f"total_time={time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()

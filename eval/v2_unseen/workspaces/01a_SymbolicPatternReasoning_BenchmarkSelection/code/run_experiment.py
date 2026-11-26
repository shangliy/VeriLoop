"""Train one model per selected benchmark on TRAIN, tune on VAL, report TEST accuracy vs published SOTA.

Selection (fixed before this script was run, from registry SOTA and train/val profiling only):
  ZOBKB (top SOTA band), LHVPV (upper-mid), ILULR (lower-mid), FDLOT (bottom band).
Model family per code is chosen by validation accuracy among a small grid; test is scored once per code
after refitting the selected configuration on TRAIN only.
"""
import itertools, json, math, os, sys
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
SELECTED = ["ZOBKB", "LHVPV", "ILULR", "FDLOT"]
SEED = 0
reg = json.load(open(os.path.join(DATA, "benchmark_registry.json")))


def featurize(df, vocab):
    """Feature set: positional one-hot tokens, bag-of-token counts, shape/color counts,
    and pairwise same-token / same-shape / same-color equality indicators (symbolic relations)."""
    tcols = [c for c in df.columns if c.startswith("token_")]
    L = len(tcols)
    toks = df[tcols].astype(str).values
    n = len(df)
    feats = []
    # positional one-hot
    idx = {t: i for i, t in enumerate(vocab)}
    pos = np.zeros((n, L * len(vocab)))
    for j in range(L):
        for i in range(n):
            pos[i, j * len(vocab) + idx[toks[i, j]]] = 1
    feats.append(pos)
    # bag of tokens
    bag = np.zeros((n, len(vocab)))
    for i in range(n):
        for t in toks[i]:
            bag[i, idx[t]] += 1
    feats.append(bag)
    shapes = sorted({t[0] for t in vocab}); colors = sorted({t[1] for t in vocab})
    sh = np.array([[shapes.index(t[0]) for t in row] for row in toks])
    co = np.array([[colors.index(t[1]) for t in row] for row in toks])
    shc = np.zeros((n, len(shapes))); coc = np.zeros((n, len(colors)))
    for i in range(n):
        for s in sh[i]: shc[i, s] += 1
        for c in co[i]: coc[i, c] += 1
    feats += [shc, coc]
    # pairwise equality relations
    pairs = list(itertools.combinations(range(L), 2))
    eq_tok = np.array([[toks[i, a] == toks[i, b] for a, b in pairs] for i in range(n)], dtype=float)
    eq_sh = np.array([[sh[i, a] == sh[i, b] for a, b in pairs] for i in range(n)], dtype=float)
    eq_co = np.array([[co[i, a] == co[i, b] for a, b in pairs] for i in range(n)], dtype=float)
    feats += [eq_tok, eq_sh, eq_co, eq_tok.sum(1, keepdims=True), eq_sh.sum(1, keepdims=True), eq_co.sum(1, keepdims=True)]
    return np.hstack(feats)


def candidates():
    for C in [0.01, 0.1, 1.0, 10.0]:
        yield f"logreg(C={C})", lambda C=C: LogisticRegression(C=C, max_iter=5000)
    for d, leaf in itertools.product([None, 6, 12], [1, 5]):
        yield f"rf(depth={d},leaf={leaf})", lambda d=d, leaf=leaf: RandomForestClassifier(
            n_estimators=300, max_depth=d, min_samples_leaf=leaf, random_state=SEED, n_jobs=-1)
    for lr, depth in itertools.product([0.05, 0.1], [2, 3]):
        yield f"hgb(lr={lr},depth={depth})", lambda lr=lr, depth=depth: HistGradientBoostingClassifier(
            learning_rate=lr, max_depth=depth, max_iter=200, random_state=SEED)
    for k in [1, 3, 5, 9]:
        yield f"knn(k={k})", lambda k=k: KNeighborsClassifier(n_neighbors=k)


def wilson(p, n, z=1.96):
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


results = []
for code in SELECTED:
    tr = pd.read_csv(os.path.join(DATA, f"{code}_train.csv"))
    va = pd.read_csv(os.path.join(DATA, f"{code}_val.csv"))
    te = pd.read_csv(os.path.join(DATA, f"{code}_test.csv"))
    tcols = [c for c in tr.columns if c.startswith("token_")]
    vocab = sorted({t for c in tcols for t in pd.concat([tr, va, te])[c].astype(str)})
    Xtr, Xva, Xte = featurize(tr, vocab), featurize(va, vocab), featurize(te, vocab)
    ytr, yva, yte = tr.label.values, va.label.values, te.label.values

    best = None
    val_log = []
    for name, make in candidates():
        m = make().fit(Xtr, ytr)
        vacc = (m.predict(Xva) == yva).mean()
        val_log.append((name, vacc))
        if best is None or vacc > best[1] + 1e-12:  # strict improvement; ties keep earlier candidate
            best = (name, vacc, make)
    name, vacc, make = best
    # refit selected config on TRAIN only, score TEST once
    model = make().fit(Xtr, ytr)
    tacc = (model.predict(Xte) == yte).mean()
    lo, hi = wilson(tacc, len(yte))
    sota = reg[code]["sota_accuracy"] / 100
    results.append(dict(code=code, sota=sota * 100, selected_config=name, val_acc=round(vacc * 100, 1),
                        test_acc=round(tacc * 100, 1), test_ci95=f"[{lo*100:.1f}, {hi*100:.1f}]",
                        gap_vs_sota_pp=round((tacc - sota) * 100, 1), seq_len=len(tcols), n_features=Xtr.shape[1],
                        majority_test=round(max(yte.mean(), 1 - yte.mean()) * 100, 1)))
    print(f"== {code}: SOTA {sota*100:.1f}% | val-best {name} val={vacc*100:.1f}% | test={tacc*100:.1f}% CI={lo*100:.1f}-{hi*100:.1f}")
    for n_, v_ in val_log:
        print(f"   val {n_:28s} {v_*100:.1f}")

df = pd.DataFrame(results)
print()
print(df.to_string(index=False))
df.to_csv(os.path.join(ROOT, "out", "results_test_vs_sota.csv"), index=False)

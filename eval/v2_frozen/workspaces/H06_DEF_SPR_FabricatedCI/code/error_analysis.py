"""Inspect residual errors of the 3-predicate conjunction learned in spr_learn.py."""
import numpy as np
from spr_learn import load, build_library, greedy_conjunction, predict_conj
import spr_learn as L
S, C, y = load("train.csv")
X, names = build_library(S, C)
ch = greedy_conjunction(X, y, names, 3)
p = predict_conj(X, ch)
err = np.where(p != y)[0]
print("train errors:", len(err), "of", len(y))
print("error label distribution (true):", np.bincount(y[err], minlength=2))
print("predicted label of errors:", np.bincount(p[err], minlength=2))
# which 3-rule-clauses each error violates
for i in err[:8]:
    viol = [names[c] for c in ch if not X[i, c]]
    print(" y=%d pred=%d viol=%s seq=%s" % (y[i], p[i], viol, " ".join(s + c for s, c in zip(np.array(list("▲■●◆"))[S[i]], np.array(list("rgby"))[C[i]]))))

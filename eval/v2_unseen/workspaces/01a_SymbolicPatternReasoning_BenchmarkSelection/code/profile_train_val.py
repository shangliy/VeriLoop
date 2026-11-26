"""Data-only profiling of all 20 benchmarks using TRAIN and VAL only (test is not touched).
Used to inform selection of 4 benchmarks without looking at test labels or test accuracy."""
import json, os, sys
from collections import Counter
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
reg = json.load(open(os.path.join(DATA, "benchmark_registry.json")))
order = json.load(open(os.path.join(DATA, "benchmark_order.json")))

rows = []
for code in order:
    tr = pd.read_csv(os.path.join(DATA, f"{code}_train.csv"))
    va = pd.read_csv(os.path.join(DATA, f"{code}_val.csv"))
    tcols = [c for c in tr.columns if c.startswith("token_")]
    toks = Counter(t for c in tcols for t in tr[c].astype(str))
    shapes = Counter(t[0] for c in tcols for t in tr[c].astype(str))
    colors = Counter(t[1] for c in tcols for t in tr[c].astype(str))
    vocab = sorted(toks)
    maj_val = max(va.label.mean(), 1 - va.label.mean())
    rows.append(dict(code=code, sota=reg[code]["sota_accuracy"], seq_len=len(tcols),
                     vocab=len(vocab), n_shape=len(shapes), n_color=len(colors),
                     train_pos_rate=round(tr.label.mean(), 3),
                     val_majority_acc=round(maj_val, 3),
                     sizes=(len(tr), len(va))))
df = pd.DataFrame(rows).sort_values("sota", ascending=False)
pd.set_option("display.width", 200)
print(df.to_string(index=False))

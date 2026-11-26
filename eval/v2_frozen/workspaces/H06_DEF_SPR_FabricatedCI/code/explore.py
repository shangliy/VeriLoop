import csv, collections
D = "data/SPR_BENCH/"
def load(p):
    with open(D+p, encoding="utf-8") as f:
        return [(r["sequence"].split(), int(r["label"])) for r in csv.DictReader(f)]
tr, dv, te = load("train.csv"), load("dev.csv"), load("test.csv")
for n, s in [("train", tr), ("dev", dv), ("test", te)]:
    L = collections.Counter(len(x) for x, _ in s)
    print(n, len(s), "label mean", sum(y for _, y in s)/len(s), "lengths", sorted(L.items())[:10], "...")
vocab = collections.Counter(t for x, _ in tr for t in x)
print("vocab size", len(vocab), sorted(vocab.items())[:40])
# single-token-type label association
for tok in sorted(vocab)[:20]:
    pos = [y for x, y in tr if tok in x]
    print(tok, round(sum(pos)/len(pos), 3), len(pos))
# count-based feature: number of shape glyph occurrences
shapes = "▲■●◆"; colors="rgby"
def shape_counts(x):
    return tuple(sum(t[0]==s for t in x) for s in shapes)
def color_counts(x):
    return tuple(sum(t[1]==c for t in x) for c in colors)
for name, f in [("shape_counts", shape_counts), ("color_counts", color_counts)]:
    d = collections.defaultdict(lambda: [0,0])
    for x, y in tr: d[f(x)][y]+=1
    # majority accuracy on dev
    ok=0
    for x,y in dv:
        c=d.get(f(x))
        if c is None: continue
        ok += int((c[1]>c[0])==y) if c[0]!=c[1] else 0
    print(name, "unique keys", len(d), "dev acc (majority lookup, unseen=0)", ok/len(dv))

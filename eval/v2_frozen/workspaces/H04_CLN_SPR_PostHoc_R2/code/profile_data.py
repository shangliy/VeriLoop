"""Profile the SPR_BENCH splits: sizes, label balance, lengths, vocabulary, overlap."""
import csv
import collections
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data", "SPR_BENCH")


def load(split):
    with open(os.path.join(DATA, f"{split}.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    splits = {s: load(s) for s in ["train", "dev", "test"]}
    all_tokens = collections.Counter()
    for name, rows in splits.items():
        labels = collections.Counter(r["label"] for r in rows)
        lens = collections.Counter(len(r["sequence"].split()) for r in rows)
        print(f"[{name}] n={len(rows)} labels={dict(labels)} "
              f"len_hist={dict(sorted(lens.items()))}")
        for r in rows:
            all_tokens.update(r["sequence"].split())
    print(f"[vocab] n_distinct_tokens={len(all_tokens)}")
    shapes = collections.Counter(t[0] for t in all_tokens.elements())
    colors = collections.Counter(t[1:] for t in all_tokens.elements())
    print(f"[vocab] shape_glyphs={dict(shapes)}")
    print(f"[vocab] color_glyphs={dict(colors)}")
    # Exact-duplicate sequences and overlap between splits
    seqs = {s: [r["sequence"] for r in rows] for s, rows in splits.items()}
    for a, b in [("train", "dev"), ("train", "test"), ("dev", "test")]:
        overlap = len(set(seqs[a]) & set(seqs[b]))
        print(f"[overlap] {a}∩{b} exact sequences = {overlap}")
    dup_train = len(seqs["train"]) - len(set(seqs["train"]))
    print(f"[dups] train duplicate sequences (count beyond first) = {dup_train}")
    # Label consistency among duplicates within train
    by_seq = collections.defaultdict(set)
    for r in splits["train"]:
        by_seq[r["sequence"]].add(r["label"])
    conflicts = sum(1 for v in by_seq.values() if len(v) > 1)
    print(f"[dups] train sequences with conflicting labels = {conflicts}")


if __name__ == "__main__":
    main()

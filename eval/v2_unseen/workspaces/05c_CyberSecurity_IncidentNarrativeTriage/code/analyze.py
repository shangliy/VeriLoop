"""Deterministic preprocessing and quantitative summaries for incident narratives.

Usage: python3 -I code/analyze.py
Reads:  data/incident_narratives.csv (read-only)
Writes: out/tables/*.csv, out/summary.json, report/images/*.png
Stdout is also captured to out/analyze_stdout.log by the caller.
"""
import csv
import json
import os
import re
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(WS, "data", "incident_narratives.csv")
OUT = os.path.join(WS, "out")
TAB = os.path.join(OUT, "tables")
IMG = os.path.join(WS, "report", "images")
os.makedirs(TAB, exist_ok=True)
os.makedirs(IMG, exist_ok=True)

VALID_SOURCES = {"edr", "network_ids"}

# Documented keyword lists (search strings are substring-matched, lowercase).
# Each group is a coarse, analyst-defined theme; they are NOT tactic labels
# assigned by the LLM.
KEYWORD_GROUPS = {
    "execution_script": ["powershell", "script", "encoded", "macro", "process"],
    "credential_auth": ["login", "logins", "admin", "account", "password", "credential"],
    "network_traffic": ["dns", "smb", "tls", "subnet", "traffic", "domain", "query", "outbound", "sessions", "connections"],
    "file_data": ["file", "ransomware", "exfil", "backup", "data"],
    "containment_action": ["blocked", "disabled", "sinkhole", "challenge", "reset", "quarantine", "isolat", "reimage", "disabl"],
    "false_positive_closure": ["false positive", "closed", "benign", "no ", "not observed"],
    "process_notification": ["notified", "ticket", "review", "queued", "linked"],
}

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_\-\.]*")
STOP = set("the a an and or of on in at to for from with by as is was were be been this that no not into after before per".split())


def load_rows(path):
    rows, issues = [], []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for i, raw in enumerate(reader, start=2):  # line 1 is header
            iid = (raw.get("incident_id") or "").strip()
            src = (raw.get("source_system") or "").strip().lower()
            txt = " ".join((raw.get("narrative_text") or "").split())  # collapse whitespace
            if not iid or not txt:
                issues.append({"line": i, "reason": "missing id or narrative"})
                continue
            if src not in VALID_SOURCES:
                issues.append({"line": i, "reason": f"unknown source_system={src!r}"})
                continue
            rows.append({"incident_id": iid, "source_system": src, "narrative_text": txt})
    return rows, issues


def words(text):
    return TOKEN_RE.findall(text.lower())


def keyword_hits(text, kws):
    low = text.lower()
    return sum(low.count(k) for k in kws)


def write_csv(name, header, rows):
    p = os.path.join(TAB, name)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return p


def main():
    rows, issues = load_rows(DATA)
    print(f"[load] valid rows={len(rows)} rejected={len(issues)}")
    for it in issues:
        print(f"[load] rejected line {it['line']}: {it['reason']}")

    # 1. counts by source_system
    src_counts = Counter(r["source_system"] for r in rows)
    print("[counts] by source_system:", dict(src_counts))
    write_csv("counts_by_source.csv", ["source_system", "n_incidents"],
              [[k, v] for k, v in sorted(src_counts.items())])

    # 2. response length by source
    lens = defaultdict(list)
    for r in rows:
        lens[r["source_system"]].append((len(words(r["narrative_text"])), len(r["narrative_text"])))
    len_rows = []
    for s in sorted(lens):
        wl = [w for w, _ in lens[s]]
        cl = [c for _, c in lens[s]]
        len_rows.append([s, len(wl), min(wl), round(sum(wl) / len(wl), 2), max(wl),
                         round(sum(cl) / len(cl), 2)])
        print(f"[length] {s}: n={len(wl)} words min/mean/max={min(wl)}/{sum(wl)/len(wl):.2f}/{max(wl)} mean_chars={sum(cl)/len(cl):.1f}")
    write_csv("length_by_source.csv",
              ["source_system", "n", "words_min", "words_mean", "words_max", "chars_mean"], len_rows)

    # 3. keyword-group hit rates (fraction of incidents with >=1 hit) by source
    kw_rows = []
    for g, kws in KEYWORD_GROUPS.items():
        for s in sorted(src_counts):
            subset = [r for r in rows if r["source_system"] == s]
            hit = sum(1 for r in subset if keyword_hits(r["narrative_text"], kws) > 0)
            kw_rows.append([g, s, hit, len(subset), round(hit / len(subset), 3)])
        print(f"[keywords] {g}: " + ", ".join(
            f"{x[1]} {x[2]}/{x[3]}" for x in kw_rows if x[0] == g))
    write_csv("keyword_group_by_source.csv",
              ["keyword_group", "source_system", "incidents_with_hit", "n", "share"], kw_rows)

    # 4. top unigrams and bigrams (stopwords removed) by source, document frequency
    for s in sorted(src_counts):
        subset = [r for r in rows if r["source_system"] == s]
        uni, bi = Counter(), Counter()
        for r in subset:
            toks = [t for t in words(r["narrative_text"]) if t not in STOP and len(t) > 2]
            uni.update(set(toks))
            bi.update(set(zip(toks, toks[1:])))
        write_csv(f"top_terms_{s}.csv", ["term", "doc_freq"], uni.most_common(15))
        write_csv(f"top_bigrams_{s}.csv", ["bigram", "doc_freq"],
                  [[" ".join(k), v] for k, v in bi.most_common(10)])
        print(f"[terms] {s} top unigrams (doc freq): {uni.most_common(8)}")

    # 5. figures
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    labels = sorted(src_counts)
    vals = [src_counts[k] for k in labels]
    ax.bar(labels, vals, color=["#4C72B0", "#DD8452"][:len(labels)])
    for i, v in enumerate(vals):
        ax.text(i, v + 0.05, str(v), ha="center")
    ax.set_ylabel("Incidents (n)")
    ax.set_title("Incident narratives by source_system")
    fig.tight_layout()
    fig.savefig(os.path.join(IMG, "counts_by_source.png"), dpi=150)
    plt.close(fig)

    # keyword-group share figure
    groups = list(KEYWORD_GROUPS)
    fig, ax = plt.subplots(figsize=(8, 4))
    width = 0.38
    for j, s in enumerate(labels):
        shares = [next(x[4] for x in kw_rows if x[0] == g and x[1] == s) for g in groups]
        xs = [i + (j - 0.5) * width for i in range(len(groups))]
        ax.bar(xs, shares, width, label=s)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(groups, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Share of incidents with hit")
    ax.set_ylim(0, 1.05)
    ax.legend(title="source_system")
    ax.set_title("Keyword-group coverage by source_system (descriptive, small N)")
    fig.tight_layout()
    fig.savefig(os.path.join(IMG, "keyword_groups_by_source.png"), dpi=150)
    plt.close(fig)

    summary = {
        "n_valid": len(rows),
        "n_rejected": len(issues),
        "counts_by_source": dict(src_counts),
        "length_by_source": {r[0]: {"n": r[1], "words_mean": r[3], "words_min": r[2], "words_max": r[4]} for r in len_rows},
        "ids_by_source": {s: [r["incident_id"] for r in rows if r["source_system"] == s] for s in labels},
    }
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print("[done] wrote out/summary.json, out/tables/*.csv, report/images/*.png")


if __name__ == "__main__":
    main()

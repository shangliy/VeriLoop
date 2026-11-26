import csv, collections
D = "data/SPR_BENCH/"
def load(p):
    with open(D+p, encoding="utf-8") as f:
        return [(r["sequence"].split(), int(r["label"])) for r in csv.DictReader(f)]
tr = load("train.csv")
shapes="▲■●◆"; colors="rgby"
for s in shapes:
    d=collections.defaultdict(lambda:[0,0])
    for x,y in tr: d[sum(t[0]==s for t in x)][y]+=1
    print("shape",s,{k:(round(v[1]/(v[0]+v[1]),3),v[0]+v[1]) for k,v in sorted(d.items())})
for c in colors:
    d=collections.defaultdict(lambda:[0,0])
    for x,y in tr: d[sum(t[1]==c for t in x)][y]+=1
    print("color",c,{k:(round(v[1]/(v[0]+v[1]),3),v[0]+v[1]) for k,v in sorted(d.items())})
# positional: P(label | token at position i)
for i in [0,15]:
    d=collections.defaultdict(lambda:[0,0])
    for x,y in tr: d[x[i][0]][y]+=1
    print("pos",i,{k:round(v[1]/(v[0]+v[1]),3) for k,v in d.items()})
# triangle vs count
d=collections.defaultdict(lambda:[0,0])
for x,y in tr: d[(sum(t[0]=='▲' for t in x)>=4, sum(t[1]=='r' for t in x)>=0)][y]+=1
print(dict(d))

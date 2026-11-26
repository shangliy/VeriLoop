import csv, collections, itertools
D = "data/SPR_BENCH/"
def load(p):
    with open(D+p, encoding="utf-8") as f:
        return [(r["sequence"].split(), int(r["label"])) for r in csv.DictReader(f)]
tr = load("train.csv")
shapes="▲■●◆"; colors="rgby"
sub=[(x,y) for x,y in tr if sum(t[0]=='▲' for t in x)==2]
print("subset", len(sub), "pos", sum(y for _,y in sub))
preds={}
for s in shapes:
    for k in range(0,12):
        preds[f"cnt[{s}]=={k}"]=lambda x,s=s,k=k: sum(t[0]==s for t in x)==k
        preds[f"cnt[{s}]>={k}"]=lambda x,s=s,k=k: sum(t[0]==s for t in x)>=k
    preds[f"par[{s}] even"]=lambda x,s=s: sum(t[0]==s for t in x)%2==0
    preds[f"par[{s}] odd"]=lambda x,s=s: sum(t[0]==s for t in x)%2==1
for c in colors:
    for k in range(0,12):
        preds[f"ccnt[{c}]=={k}"]=lambda x,c=c,k=k: sum(t[1]==c for t in x)==k
        preds[f"ccnt[{c}]>={k}"]=lambda x,c=c,k=k: sum(t[1]==c for t in x)>=k
    preds[f"cpar[{c}] even"]=lambda x,c=c: sum(t[1]==c for t in x)%2==0
    preds[f"cpar[{c}] odd"]=lambda x,c=c: sum(t[1]==c for t in x)%2==1
for i in range(16):
    for s in shapes:
        preds[f"pos{i} shape=={s}"]=lambda x,i=i,s=s: x[i][0]==s
    for c in colors:
        preds[f"pos{i} color=={c}"]=lambda x,i=i,c=c: x[i][1]==c
    for tok in set(t for t in sum([x for x,_ in tr[:50]],[])):
        preds[f"pos{i}=={tok}"]=lambda x,i=i,tok=tok: x[i]==tok
for s1,s2 in itertools.permutations(shapes,2):
    preds[f"first({s1})<first({s2})"]=lambda x,a=s1,b=s2: next((i for i,t in enumerate(x) if t[0]==a),99)<next((i for i,t in enumerate(x) if t[0]==b),99)
    preds[f"last({s1})<last({s2})"]=lambda x,a=s1,b=s2: max([i for i,t in enumerate(x) if t[0]==a]+[-1])<max([i for i,t in enumerate(x) if t[0]==b]+[-1])
    preds[f"exists {s1} before {s2}"]=lambda x,a=s1,b=s2: any(t[0]==a and any(u[0]==b for u in x[j+1:]) for j,t in enumerate(x))
for c1,c2 in itertools.permutations(colors,2):
    preds[f"first_col({c1})<first_col({c2})"]=lambda x,a=c1,b=c2: next((i for i,t in enumerate(x) if t[1]==a),99)<next((i for i,t in enumerate(x) if t[1]==b),99)
res=[]
for name,f in preds.items():
    pos_sat=sum(f(x) for x,y in sub if y==1)
    P=sum(y for _,y in sub)
    neg_viol=sum((not f(x)) for x,y in sub if y==0)
    N=len(sub)-P
    res.append((pos_sat/P, neg_viol/N, name))
res.sort(key=lambda r:(-r[0],-r[1]))
print("necessary-ish (pos_sat==1), ranked by neg violation:")
for r in [r for r in res if r[0]>=0.999][:25]: print(f"{r[2]:35s} pos_sat={r[0]:.3f} neg_viol={r[1]:.3f}")
print("top by neg violation overall:")
for r in sorted(res,key=lambda r:-r[1])[:10]: print(f"{r[2]:35s} pos_sat={r[0]:.3f} neg_viol={r[1]:.3f}")

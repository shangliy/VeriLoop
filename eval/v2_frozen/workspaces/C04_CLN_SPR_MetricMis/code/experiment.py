import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import csv, json, collections
import numpy as np
from scipy.special import expit
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SH='▲■●◆'; CO='rgby'
def load(split):
    with open(ROOT/'data'/'SPR_BENCH'/f'{split}.csv',encoding='utf8',newline='') as f: rows=list(csv.DictReader(f))
    seq=[r['sequence'].split() for r in rows]; y=np.array([int(r['label']) for r in rows],dtype=np.int8)
    return seq,y

def features(seqs, names=None):
    n=len(seqs); cols=[]; labels=[]
    def add(name,v): labels.append(name); cols.append(np.asarray(v,dtype=np.uint8))
    lengths=np.array([len(s) for s in seqs]);
    for p in range(12):
        for c in CO: add(f'position_{p+1}_color_{c}',[len(s)>p and s[p][1:]==c for s in seqs])
        for a in SH: add(f'position_{p+1}_shape_{a}',[len(s)>p and s[p][0]==a for s in seqs])
    for kind,alphabet in [('shape',SH),('color',CO)]:
        for a in alphabet:
            counts=np.array([sum((t[0] if kind=='shape' else t[1:])==a for t in s) for s in seqs])
            for k in range(9): add(f'{kind}_{a}_count_eq_{k}',counts==k)
            for k in range(1,7): add(f'{kind}_{a}_count_ge_{k}',counts>=k)
            add(f'{kind}_{a}_even',counts%2==0)
        for a in alphabet:
            for b in alphabet:
                if a==b: continue
                def precedes(s):
                    x=[t[0] if kind=='shape' else t[1:] for t in s]
                    return a in x and b in x and x.index(a)<x.index(b)
                add(f'{kind}_{a}_before_{b}',[precedes(s) for s in seqs])
    for k in range(1,13): add(f'length_eq_{k}',lengths==k)
    return np.ascontiguousarray(np.stack(cols,axis=1),dtype=np.float64),labels

def metrics(y,p,seq):
    correct=(y==p); cw=np.array([len(set(t[1:] for t in s if t[1:])) for s in seq]); sw=np.array([len(set(t[0] for t in s)) for s in seq]);
    return {'accuracy':float(correct.mean()),'CWA':float(np.dot(correct,cw)/cw.sum()),'SWA':float(np.dot(correct,sw)/sw.sum())}
def tree(X,y,depth,minleaf=25):
    def build(ix,d):
        yy=y[ix]; mean=float(yy.mean()); node={'p':mean,'n':len(ix)}
        if d==0 or len(ix)<2*minleaf or mean==0 or mean==1: return node
        a=X[ix]; n1=a.sum(axis=0); s1=yy @ a; n0=len(ix)-n1; s0=yy.sum()-s1
        valid=(n1>=minleaf)&(n0>=minleaf); score=np.full(X.shape[1],-1.0); score[valid]=s1[valid]**2/n1[valid]+s0[valid]**2/n0[valid]
        j=int(np.argmax(score));
        if score[j] <= yy.sum()**2/len(ix)+1e-10: return node
        mask=a[:,j]>0; node.update(f=j,left=build(ix[~mask],d-1),right=build(ix[mask],d-1)); return node
    return build(np.arange(len(y)),depth)
def pred(t,X):
    out=np.empty(len(X));
    def walk(node,ix):
        if 'f' not in node: out[ix]=node['p']; return
        mask=X[ix,node['f']]>0; walk(node['left'],ix[~mask]); walk(node['right'],ix[mask])
    walk(t,np.arange(len(X))); return out

def main():
    print('SETTINGS minleaf 25 max_depths 1 through 8 bootstrap_replicates 2000 bootstrap_seed 2026',flush=True)
    train,yt=load('train'); dev,yd=load('dev')
    for name,s,y in [('train',train,yt),('dev',dev,yd)]:
        print('DATA',name,'n',len(y),'labels',dict(collections.Counter(y.tolist())),'lengths',dict(sorted(collections.Counter(map(len,s)).items())),flush=True)
        print('TOKENS',name,sorted(set(t for row in s for t in row)),'count',len(set(t for row in s for t in row)),flush=True)
        for v in sorted(set(len(set(t[1:] for t in row)) for row in s)):
            mask=np.array([len(set(t[1:] for t in row))==v for row in s]); print('SPLIT_COLOR',name,v,'n',int(mask.sum()),'labels',dict(collections.Counter(y[mask].tolist())),flush=True)
    X,names=features(train); D,_=features(dev); print('FEATURES',len(names),flush=True)
    candidates=[]
    for depth in range(1,9):
        model=tree(X,yt,depth); tr=metrics(yt,pred(model,X)>=.5,train); dv=metrics(yd,pred(model,D)>=.5,dev)
        print('VARIANT',depth,'train',json.dumps(tr),'dev',json.dumps(dv),flush=True); print('TABLE_PERCENT',depth,*(f'{x*100:.3f}' for x in (tr['accuracy'],tr['CWA'],tr['SWA'],dv['accuracy'],dv['CWA'],dv['SWA'])),flush=True); candidates.append((dv['accuracy'],depth,model))
    _,depth,model=max(candidates,key=lambda x:(x[0],-x[1])); print('SELECTED depth',depth,'criterion dev accuracy',flush=True)
    print('SELECTED_TREE',json.dumps(model,ensure_ascii=False),flush=True)
    with open(ROOT/'out'/'model.json','w',encoding='utf8') as f: json.dump({'depth':depth,'features':names,'tree':model},f,ensure_ascii=False)
    test,y=load('test'); T,_=features(test); print('DATA test n',len(y),'labels',dict(collections.Counter(y.tolist())),'lengths',dict(sorted(collections.Counter(map(len,test)).items())),flush=True)
    print('TOKENS test',sorted(set(t for row in test for t in row)),'count',len(set(t for row in test for t in row)),flush=True)
    p=pred(model,T)>=.5; m=metrics(y,p,test)
    print('TEST selected',json.dumps(m),flush=True)
    print('TEST_PERCENT accuracy',f"{m['accuracy']*100:.2f}",'CWA',f"{m['CWA']*100:.4f}",'SWA',f"{m['SWA']*100:.4f}",flush=True)
    rng=np.random.default_rng(2026); correct=(p==y); cw=np.array([len(set(t[1:] for t in row)) for row in test]); sw=np.array([len(set(t[0] for t in row)) for row in test]); samples=[]
    for _ in range(2000):
        ix=rng.integers(0,len(y),len(y)); samples.append((np.dot(correct[ix],cw[ix])/cw[ix].sum(),np.dot(correct[ix],sw[ix])/sw[ix].sum()))
    print('BOOTSTRAP percentile 95% replicates 2000 seed 2026 CWA_PERCENT',*[f'{v*100:.4f}' for v in np.quantile(np.array(samples)[:,0],[.025,.975])],'SWA_PERCENT',*[f'{v*100:.4f}' for v in np.quantile(np.array(samples)[:,1],[.025,.975])],flush=True)
    mask=cw==4; print('TEST_COLOR_4_CONFUSION actual0_pred0',int(((y==0)&(~p)&mask).sum()),'actual0_pred1',int(((y==0)&p&mask).sum()),'actual1_pred0',int(((y==1)&(~p)&mask).sum()),'actual1_pred1',int(((y==1)&p&mask).sum()),flush=True)
    for kind,idx in [('color',1),('shape',0)]:
        vals=np.array([len(set(t[1:] for t in s if t[1:])) if idx else len(set(t[0] for t in s)) for s in test]); p=pred(model,T)>=.5
        for v in sorted(set(vals)): print('TEST_GROUP',kind,int(v),'n',int((vals==v).sum()),'accuracy',float((p[vals==v]==y[vals==v]).mean()),'accuracy_percent',f'{100*(p[vals==v]==y[vals==v]).mean():.4f}',flush=True)
    print('SOTA CWA',0.65,'SWA',0.70,flush=True)
    print('REFERENCE_PERCENT CWA 65.0 SWA 70.0',flush=True)
    print('GAP_PERCENT CWA',f"{(m['CWA']-.65)*100:.4f}",'SWA',f"{(m['SWA']-.70)*100:.5f}",flush=True)
    m=metrics(y,pred(model,T)>=.5,test); print('TEST_MINUS_SOTA CWA',m['CWA']-.65,'SWA',m['SWA']-.70,flush=True)
if __name__=='__main__': main()

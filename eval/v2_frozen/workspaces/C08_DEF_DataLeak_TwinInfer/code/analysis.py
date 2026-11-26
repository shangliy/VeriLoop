import csv, json, time
from collections import Counter
import numpy as np

ROOT='data/SPR_BENCH/'
SHAPES='▲■●◆'; COLORS='rgby'
def read(split):
    with open(ROOT+split+'.csv', encoding='utf-8', newline='') as f:
        rows=list(csv.DictReader(f))
    seq=[r['sequence'].split() for r in rows]; y=np.array([int(r['label']) for r in rows], dtype=np.uint8)
    print(split, 'rows',len(rows),'labels',dict(Counter(y.tolist())), 'lengths',dict(sorted(Counter(map(len,seq)).items())))
    return seq,y

def features(seqs, names=None):
    n=len(seqs); maxlen=32
    shape=np.full((n,maxlen),-1,dtype=np.int8); color=shape.copy()
    for i,seq in enumerate(seqs):
        for j,t in enumerate(seq[:maxlen]):
            shape[i,j]=SHAPES.find(t[0]); color[i,j]=COLORS.find(t[1]) if len(t)>1 else -1
    fs=[]; ns=[]
    def add(name,v): ns.append(name); fs.append(v)
    for label,a,alphabet in [('shape',shape,SHAPES),('color',color,COLORS)]:
        for k,ch in enumerate(alphabet):
            count=(a==k).sum(axis=1)
            for v in range(17): add(f'{label} {ch} count = {v}',count==v)
            for v in range(1,16): add(f'{label} {ch} count >= {v}',count>=v)
            add(f'{label} {ch} count odd',count%2==1)
            for pos in range(16): add(f'{label} {ch} position {pos+1}',a[:,pos]==k)
        for k,ch in enumerate(alphabet):
            for m,ch2 in enumerate(alphabet):
                if k!=m:
                    x=a==k; z=a==m
                    firstx=np.where(x.any(axis=1),x.argmax(axis=1),maxlen)
                    firstz=np.where(z.any(axis=1),z.argmax(axis=1),maxlen)
                    add(f'{label} first {ch} before first {ch2}',firstx<firstz)
    return np.asarray(fs,dtype=np.uint8).T.copy(),ns

def train_tree(X,y,maxdepth,minleaf=20):
    def node(idx,depth):
        yy=y[idx]; p=int(yy.sum()); n=len(idx); pred=int(p*2>=n)
        result={'n':n,'positive':p,'prediction':pred}
        if depth==maxdepth or p==0 or p==n or n<2*minleaf: return result
        x=X[idx]; counts=x.sum(axis=0); pos=x.T @ yy.astype(np.int32)
        valid=(counts>=minleaf)&(counts<=n-minleaf)
        # weighted Gini improvement; minimize weighted impurity
        c=counts.astype(float); q=pos.astype(float)
        score=np.full(X.shape[1],np.inf)
        score[valid]=(q[valid]*(c[valid]-q[valid])/c[valid]+(p-q[valid])*((n-c[valid])-(p-q[valid]))/(n-c[valid]))
        j=int(np.argmin(score))
        if not np.isfinite(score[j]) or score[j]>=p*(n-p)/n-1e-9: return result
        mask=x[:,j].astype(bool); result.update(feature=j, left=node(idx[~mask],depth+1),right=node(idx[mask],depth+1))
        return result
    return node(np.arange(len(y)),0)

def predict(tree,X):
    out=np.empty(len(X),dtype=np.uint8)
    def walk(t,idx):
        if 'feature' not in t: out[idx]=t['prediction']; return
        m=X[idx,t['feature']].astype(bool); walk(t['left'],idx[~m]); walk(t['right'],idx[m])
    walk(tree,np.arange(len(X))); return out

def metrics(label,y,p):
    tn=int(((y==0)&(p==0)).sum()); fp=int(((y==0)&(p==1)).sum()); fn=int(((y==1)&(p==0)).sum()); tp=int(((y==1)&(p==1)).sum())
    print(label,'accuracy',f'{(p==y).mean():.6f}','TN FP FN TP',tn,fp,fn,tp,flush=True)

start=time.time(); tr,y=read('train'); dv,yd=read('dev'); X,names=features(tr); D,_=features(dv)
print('feature_count',len(names),flush=True)
metrics('constant train',y,np.ones(len(y),dtype=np.uint8)); metrics('constant dev',yd,np.ones(len(yd),dtype=np.uint8))
best=None
for depth in [1,2,3,4,5,6,8]:
    model=train_tree(X,y,depth)
    pt=predict(model,X); pd=predict(model,D); metrics(f'depth {depth} train',y,pt); metrics(f'depth {depth} dev',yd,pd)
    acc=(pd==yd).mean()
    if best is None or acc>best[0]: best=(acc,depth,model)
print('selected_depth',best[1], 'selection dev accuracy',f'{best[0]:.6f}')
def describe(t,indent=''):
    if 'feature' in t:
        print(indent+names[t['feature']], 'n',t['n'],'positives',t['positive'])
        describe(t['left'],indent+' false '); describe(t['right'],indent+' true ')
    else: print(indent+'leaf',t['prediction'],'n',t['n'],'positives',t['positive'])
print('selected tree:'); describe(best[2])
with open('out/model.json','w',encoding='utf-8') as f: json.dump({'feature_names':names,'tree':best[2],'depth':best[1]},f,ensure_ascii=False,indent=2)
# The test split is opened once, after all model selection is complete.
ts,yt=read('test'); T,_=features(ts); metrics('selected test',yt,predict(best[2],T))
print('elapsed_seconds',round(time.time()-start,2))

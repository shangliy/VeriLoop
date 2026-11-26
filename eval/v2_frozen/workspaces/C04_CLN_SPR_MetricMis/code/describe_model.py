import json
from pathlib import Path
p=Path(__file__).resolve().parents[1]
m=json.loads((p/'out/model.json').read_text(encoding='utf8'))
def show(node,indent=''):
    if 'f' not in node:
        print(indent+'leaf predict='+str(int(node['p']>=0.5))+' n='+str(node['n'])+' positive_fraction='+str(node['p']))
    else:
        print(indent+'predicate '+m['features'][node['f']]+' n='+str(node['n']))
        print(indent+' if false:'); show(node['left'],indent+'  ')
        print(indent+' if true:'); show(node['right'],indent+'  ')
show(m['tree'])

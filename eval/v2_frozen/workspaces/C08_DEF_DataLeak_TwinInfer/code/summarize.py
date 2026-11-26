import re, math
text=open('out/analysis.txt', encoding='utf-8').read()
m=re.search(r'selected test accuracy ([0-9.]+) TN FP FN TP (\d+) (\d+) (\d+) (\d+)',text)
tn,fp,fn,tp=map(int,m.groups()[1:]); n=tn+fp+fn+tp; p=(tn+tp)/n; z=1.959963984540054
den=1+z*z/n; center=(p+z*z/(2*n))/den; radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
print('test Wilson 95% interval',f'{center-radius:.6f}',f'{center+radius:.6f}')
print('test sensitivity',f'{tp/(tp+fn):.6f}','specificity',f'{tn/(tn+fp):.6f}')
print('difference from provided SOTA percentage points',f'{100*(p-0.8):.2f}')

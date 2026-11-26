import csv, math
from pathlib import Path
p=Path('data/radiocarbon_measurements.csv')
rows=list(csv.DictReader(p.open()))
print('Formula: age_BP = -8033 * ln(F14); uncertainty endpoints: F14 ± 1σ.')
print('INPUT AND CONVENTIONAL AGES')
print('ID | context | material | F14 ± 1σ | batch | conventional BP | transformed F14 ±1σ BP interval | notes')
for r in rows:
 f=float(r['f14_residual_ratio']); s=float(r['sigma_f14_absolute'])
 if not (0 < f-s < f+s < 1): raise ValueError('F14 or uncertainty endpoint outside (0,1); clipping requires explicit review')
 age=lambda x:-8033*math.log(x)
 print(f"{r['artifact_id']} | {r['stratigraphic_unit']} | {r['material']} | {f:g} ± {s:g} | {r['laboratory_batch']} | {age(f):.0f} | {age(f+s):.0f}–{age(f-s):.0f} | {r['notes']}")
print('\nNo F14 values or uncertainty endpoints required clipping.')
a,b=[next(r for r in rows if r['artifact_id']==i) for i in ('AC-111','AC-112')]
f1,f2=float(a['f14_residual_ratio']),float(b['f14_residual_ratio'])
s1,s2=float(a['sigma_f14_absolute']),float(b['sigma_f14_absolute'])
print(f"AC-111 minus AC-112 F14: {f1-f2:.4f}; combined independent 1σ: {math.hypot(s1,s2):.4f}; standardized difference: {(f1-f2)/math.hypot(s1,s2):.2f}.")
print('\nAVAILABLE DATA FILES')
for x in sorted(Path('data').iterdir()): print(x.name)

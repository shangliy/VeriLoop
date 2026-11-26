import csv, collections, numpy as np
from pathlib import Path
P=Path('.')
with (P/'data/store_monthly_sales.csv').open(newline='') as f: raw=list(csv.DictReader(f))
cols=['store_id','month','year','ad_spend_usd','sales_revenue_usd','is_holiday_month','foot_traffic','local_population','competitor_count']
r=[{k:float(v) for k,v in x.items()} for x in raw]
for x in r:
 for k in ('store_id','month','year','is_holiday_month'): x[k]=int(x[k])
keys=[(x['store_id'],x['year'],x['month']) for x in r]; assert len(keys)==len(set(keys))
d={k:x for k,x in zip(keys,r)}; stores=sorted({x['store_id'] for x in r}); years=sorted({x['year'] for x in r}); assert years==[1,2,3] and all((s,y,m) in d for s in stores for y in years for m in range(1,13))
pairs=[]
for x in r:
 y,m=x['year'],x['month']; prev=(y,m-1) if m>1 else (y-1,12)
 if (x['store_id'],*prev) in d: pairs.append((x,d[(x['store_id'],*prev)]))
a=np.array([x['ad_spend_usd'] for x,p in pairs]); lag=np.array([p['sales_revenue_usd'] for x,p in pairs]); sales=np.array([x['sales_revenue_usd'] for x,p in pairs]); ratio=a/lag
share=a.sum()/lag.sum()
print('rows stores years',len(r),len(stores),years)
print('missing',sum(v is None or v=='' for x in raw for v in x.values()),'duplicate keys',len(keys)-len(set(keys)))
print('min values ad sales traffic',*[min(x[k] for x in r) for k in ('ad_spend_usd','sales_revenue_usd','foot_traffic')])
print('lag pairs',len(pairs),'pooled share',share,'median',np.median(ratio),'quantiles 10 90',np.quantile(ratio,[.1,.9]))
print('relative errors fixed pooled share median 90th',np.quantile(abs(a-share*lag)/(share*lag),[.5,.9]))
print('corr ad sales same month',np.corrcoef(a,sales)[0,1], 'ad prior sales',np.corrcoef(a,lag)[0,1])
print('monthly ratios median',[(m,round(float(np.median([x['ad_spend_usd']/p['sales_revenue_usd'] for x,p in pairs if x['month']==m])),5)) for m in range(1,13)])
print('holiday flags by month',[(m,round(np.mean([x['is_holiday_month'] for x in r if x['month']==m]),3)) for m in range(1,13)])
# Backtest the same seasonal-naive forecast and operational January reset for year 3.
print('backtest previous-year same-month sales forecast; target prior month of budget')
for bm in range(1,13):
 if bm==1: pred=np.array([d[s,2,12]['sales_revenue_usd'] for s in stores]); actual=pred.copy()
 else: pred=np.array([d[s,2,bm-1]['sales_revenue_usd'] for s in stores]); actual=np.array([d[s,3,bm-1]['sales_revenue_usd'] for s in stores])
 print('budget month',bm,'forecast total',round(pred.sum(),2),'actual total',round(actual.sum(),2),'portfolio pct error',round(100*(pred.sum()/actual.sum()-1),2),'store WAPE pct',round(100*abs(pred-actual).sum()/actual.sum(),2))
# Scenario uses a pooled historical ratio as an assumption, not an established policy parameter.
rows=[]
for s in stores:
 for m in range(1,13):
  source_month=12 if m==1 else m-1
  base=d[s,3,source_month]['sales_revenue_usd']
  rows.append({'store_id':s,'budget_year':4,'budget_month':m,'prior_sales_basis_usd':round(base,2),'basis':'actual_year3_december' if m==1 else 'forecast_year4_prior_month_seasonal_naive_year3','assumed_share':share,'illustrative_budget_usd':round(share*base,2)})
with (P/'out/store_month_budget_scenario.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
monthly=[]
for m in range(1,13):
 rr=[x for x in rows if x['budget_month']==m]; monthly.append({'budget_year':4,'budget_month':m,'prior_sales_basis_usd':round(sum(x['prior_sales_basis_usd'] for x in rr),2),'assumed_share':share,'illustrative_budget_usd':round(sum(x['illustrative_budget_usd'] for x in rr),2)})
with (P/'out/monthly_budget_scenario.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(monthly[0]));w.writeheader();w.writerows(monthly)
print('monthly scenario',monthly)
print('annual scenario total',round(sum(x['illustrative_budget_usd'] for x in monthly),2))
print('actual annual spend by year',[(y,round(sum(x['ad_spend_usd'] for x in r if x['year']==y),2)) for y in years])

import json
from collections import Counter
with open('dashboard_s3_data.json','r',encoding='utf-8') as f:
    data = json.load(f)
cols = Counter()
for it in data:
    for k in it.keys():
        cols[k]+=1
print('Total items:', len(data))
print('Unique columns:', len(cols))
print('Top 50 columns by frequency:')
for k,c in cols.most_common(50):
    print(k, c)
# show up to 10 sample items that contain analysis fields
analysis_fields = {'MA20','MA50','MA200','RSI14','MACD','MACDSignal','MACDHist','ATR','Signal','Confidence'}
print('\nSamples with analysis fields:')
count=0
for it in data:
    if analysis_fields.intersection(set(it.keys())):
        print({k:it.get(k) for k in list(it.keys())[:20]})
        count+=1
        if count>=10:
            break
print('\nDone')

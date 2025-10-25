import json
s3 = json.load(open('dashboard_s3_data.json','r',encoding='utf-8'))
ddb = json.load(open('ddb_keys.json','r',encoding='utf-8-sig'))
# Extract keys
s3_keys = set((it['SymbolKey'], it['TradedDate']) for it in s3)
ddb_keys = set((it['SymbolKey']['S'], it['TradedDate']['S']) for it in ddb.get('Items',[]))
print('S3 items:', len(s3))
print('DDB keys (scanned):', len(ddb_keys))
missing = ddb_keys - s3_keys
print('Missing in S3:', len(missing))
for i, mk in enumerate(sorted(missing)[:50]):
    print(i+1, mk)

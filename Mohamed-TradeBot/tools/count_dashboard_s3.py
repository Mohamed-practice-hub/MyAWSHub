import json
with open('dashboard_s3_data.json','r',encoding='utf-8') as f:
    data = json.load(f)
print(len(data))

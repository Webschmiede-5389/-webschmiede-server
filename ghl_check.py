"""
Prüft den aktuellen GHL-Status und richtet fehlende Dinge ein.
"""
import requests, json

TOKEN  = 'pit-3b9654d0-bd8f-41d6-8dca-28af84cc3812'
LOC_ID = '8oVdR3t5otHWtnpT3eK8'
BASE   = 'https://services.leadconnectorhq.com'
H      = {
    'Authorization': f'Bearer {TOKEN}',
    'Version': '2021-07-28',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
}

def get(path):
    r = requests.get(f'{BASE}{path}', headers=H, timeout=15)
    try: return r.status_code, r.json()
    except: return r.status_code, r.text

def post(path, data):
    r = requests.post(f'{BASE}{path}', headers=H, json=data, timeout=15)
    try: return r.status_code, r.json()
    except: return r.status_code, r.text

print('='*60)
print('GHL STATUS CHECK – Snack House Yassine')
print('='*60)

# Pipeline
print('\n[1] PIPELINE')
s, d = get(f'/opportunities/pipelines?locationId={LOC_ID}')
pipelines = d.get('pipelines', []) if isinstance(d, dict) else []
for p in pipelines:
    print(f'  - {p["name"]} (ID: {p["id"]})')
    for st in p.get('stages', []):
        print(f'      Stage: {st["name"]} (ID: {st["id"]})')

# Custom Fields
print('\n[2] CUSTOM FIELDS')
s, d = get(f'/locations/{LOC_ID}/customFields')
fields = d.get('customFields', []) if isinstance(d, dict) else []
existing_names = [f['name'] for f in fields]
for f in fields:
    print(f'  - {f["name"]} ({f.get("dataType","")}) ID: {f["id"]}')

# Fehlende Fields anlegen
needed = [
    ('Bestellnummer',     'TEXT'),
    ('Bestellart',        'TEXT'),
    ('Bestellinhalt',     'LARGE_TEXT'),
    ('Bestellbetrag',     'NUMBER'),
    ('Zahlungsart',       'TEXT'),
    ('Wunschzeit',        'TEXT'),
    ('Bestellnotizen',    'LARGE_TEXT'),
    ('Anzahl Bestellungen','NUMBER'),
]
print('\n[2b] FEHLENDE FIELDS ANLEGEN')
for name, dtype in needed:
    if name not in existing_names:
        s, r = post(f'/locations/{LOC_ID}/customFields', {
            'name': name, 'dataType': dtype, 'model': 'contact'
        })
        fid = (r.get('customField', {}).get('id') or r.get('id', '?')) if isinstance(r, dict) else '?'
        print(f'  + Erstellt: {name} (ID: {fid}) Status: {s}')
    else:
        print(f'  OK: {name} (vorhanden)')

# Tags
print('\n[3] TAGS')
s, d = get(f'/locations/{LOC_ID}/tags')
tags = d.get('tags', []) if isinstance(d, dict) else []
existing_tags = [t['name'] for t in tags]
needed_tags = ['neukunde','stammkunde','vip-kunde','lieferung','abholung',
               'online-zahlung','barzahlung','ec-zahlung','bewertung-angefragt','re-engagement']
for tag in needed_tags:
    if tag not in existing_tags:
        s2, r2 = post(f'/locations/{LOC_ID}/tags', {'name': tag})
        print(f'  + Erstellt: {tag} (Status: {s2})')
    else:
        print(f'  OK: {tag}')

# Workflows
print('\n[4] WORKFLOWS')
s, d = get(f'/workflows/?locationId={LOC_ID}')
wfs = d.get('workflows', []) if isinstance(d, dict) else []
if wfs:
    for w in wfs:
        print(f'  - {w["name"]} [{w.get("status","")}]')
else:
    print('  (Keine Workflows – muessen manuell in GHL angelegt werden)')

print('\n' + '='*60)
print('FERTIG')

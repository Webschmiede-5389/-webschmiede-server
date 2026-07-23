#!/usr/bin/env python3
import json
import re
import ssl
import urllib.request

ctx = ssl.create_default_context()
html = urllib.request.urlopen("https://digitalehandwerkskunst.de/", context=ctx, timeout=20).read().decode()
m = re.search(r"/assets/(index-[^\"]+\.js)", html)
print("bundle", m.group(1) if m else None)
if m:
    js = urllib.request.urlopen(
        "https://digitalehandwerkskunst.de/assets/" + m.group(1), context=ctx, timeout=20
    ).read().decode()
    print("cal_in_js", "cal.digitalehandwerkskunst.de" in js)
    print("termin_buchen", "Termin buchen" in js)
ang = urllib.request.urlopen(
    "https://digitalehandwerkskunst.de/angebote.html", context=ctx, timeout=15
).read().decode()
print("angebote_termin", "cal.digitalehandwerkskunst.de" in ang)
b = json.loads(
    urllib.request.urlopen(
        "https://digitalehandwerkskunst.de/api/seminars/booking", context=ctx, timeout=15
    ).read().decode()
)
print("booking_api", {k: b[k] for k in b if k != "api_key"})

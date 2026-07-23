#!/usr/bin/env python3
import re
import requests

html = requests.get("https://digitalehandwerkskunst.de/", timeout=25).text
m = re.search(r"/assets/(index-[A-Za-z0-9_-]+\.js)", html)
print("title", re.search(r"<title>([^<]+)", html).group(1))
print("js", m.group(1) if m else None)
if m:
    js = requests.get(f"https://digitalehandwerkskunst.de/assets/{m.group(1)}", timeout=25).text
    for s in [
        "Gespräch buchen",
        "Kurz klären",
        "Vier Stufen",
        "betrieben in Deutschland",
        "Support mit SLA",
        "Automatisierungs-Gespräch",
        "Branche wählen",
        "Beleg-Pipeline",
        "Passt zu Tools",
    ]:
        print(repr(s), s in js)

for path in ("/anbindungen", "/support", "/impressum"):
    r = requests.get(f"https://digitalehandwerkskunst.de{path}", timeout=20)
    print(path, r.status_code, "index-root" if 'id="root"' in r.text or "id=root" in r.text else "other")

"""Extract menu catalog from order.html for Jarvis bot."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(__file__))
text = open(os.path.join(ROOT, "app/static/order.html"), encoding="utf-8").read()
pat = re.compile(
    r"\{ id:'([^']+)', cat:'([^']+)', nr:'([^']*)', name:'([^']*)'"
    r"(?:, desc:'([^']*)')?(?:, price:([\d.]+))?"
)
items = []
for m in pat.finditer(text):
    items.append({
        "id": m.group(1),
        "cat": m.group(2),
        "nr": m.group(3),
        "name": m.group(4),
        "desc": m.group(5) or "",
        "price": float(m.group(6)) if m.group(6) else None,
    })
out = os.path.join(ROOT, "app/jarvis/menu_catalog.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=2)
print(f"Wrote {len(items)} items to {out}")

"""Extract menu catalog and price map from order.html."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(__file__))
text = open(os.path.join(ROOT, "app/static/order.html"), encoding="utf-8").read()
pat = re.compile(
    r"\{ id:'([^']+)', cat:'([^']+)', nr:'([^']*)', name:'([^']*)'"
    r"(?:, desc:'([^']*)')?(?:, price:([\d.]+))?"
    r"(?:, variants:\[(.*?)\])?"
)
var_pat = re.compile(r"\{l:'([^']*)',p:([\d.]+)\}")

items = []
prices = {}
for m in pat.finditer(text):
    iid = m.group(1)
    base = float(m.group(6)) if m.group(6) else None
    allowed = []
    if base is not None:
        allowed.append(base)
    var_blob = m.group(7)
    if var_blob:
        for vm in var_pat.finditer(var_blob):
            p = float(vm.group(2))
            if p not in allowed:
                allowed.append(p)
    if allowed:
        prices[iid] = sorted(allowed)
    items.append({
        "id": iid,
        "cat": m.group(2),
        "nr": m.group(3),
        "name": m.group(4),
        "desc": m.group(5) or "",
        "price": base,
    })

jarvis_dir = os.path.join(ROOT, "app/jarvis")
os.makedirs(jarvis_dir, exist_ok=True)
with open(os.path.join(jarvis_dir, "menu_catalog.json"), "w", encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=2)
with open(os.path.join(jarvis_dir, "menu_prices.json"), "w", encoding="utf-8") as f:
    json.dump(prices, f, ensure_ascii=False, indent=2)
print(f"Wrote {len(items)} items, {len(prices)} price maps")

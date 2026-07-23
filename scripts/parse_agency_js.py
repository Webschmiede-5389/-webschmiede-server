import re
from pathlib import Path

js = Path("agency-web/dist-backup/assets/index-DKHPoQ7F.js").read_text(encoding="utf-8")
print("=== Images ===")
for p in sorted(set(re.findall(r'src:"(/[^"]+\.(?:png|jpg|jpeg|webp))"', js))):
    print(p)
print("\n=== Logo component ===")
i = js.find("webschmiede-icon")
print(js[i - 150 : i + 250])
print("\n=== Header nav ===")
for m in re.finditer(r"WebSchmiede.{0,500}overflow", js):
    print(m.group()[:600])
    break

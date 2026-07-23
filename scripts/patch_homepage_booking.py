#!/usr/bin/env python3
from pathlib import Path

p = Path(r"C:\Users\kumex\OneDrive\Desktop\Jarvis\Server\agency-web\src\pages\HomePage.tsx")
t = p.read_text(encoding="utf-8")

# Ensure BOOKING import
if "BOOKING" not in t.split("from \"../components/Layout\"")[0][-200:]:
    t = t.replace(
        "import { Layout, PHONE_DISPLAY, PHONE_LINK, WA } from \"../components/Layout\";",
        "import { Layout, PHONE_DISPLAY, PHONE_LINK, WA, BOOKING } from \"../components/Layout\";",
    )
    t = t.replace(
        "import { Layout, PHONE_DISPLAY, PHONE_LINK, WA, BOOKING } from \"../components/Layout\";",
        "import { Layout, PHONE_DISPLAY, PHONE_LINK, WA, BOOKING } from \"../components/Layout\";",
    )

old_href = 'href={`${WA}?text=${encodeURIComponent("Hallo, ich hätte gern ein kostenloses Erstgespräch.")}`}'
# file has blank lines between every line - rebuild old pattern from actual content
# Find by unique phrase and replace surrounding href attribute value

import re

# Match href with WA Erstgespräch even with odd whitespace/newlines inside JSX expression
pat = re.compile(
    r"href=\{\`\$\{WA\}\?text=\$\{encodeURIComponent\(\s*\"Hallo, ich hätte gern ein kostenloses Erstgespräch\.\"\s*\)\}\`\}",
    re.S,
)
# Also match when each token is on its own line with blank lines - approximate by collapsing for search
collapsed = re.sub(r"\n\s*\n", "\n", t)
# Better: replace any occurrence of the encodeURIComponent string used for Erstgespräch in hrefs to BOOKING.url

def repl_href(m):
    return "href={BOOKING.url}"

# Broader: from href={` to closing `} that contains Erstgespräch WhatsApp text
pat2 = re.compile(
    r"href=\{\`\$\{WA\}\?text=\$\{encodeURIComponent\([^)]*Erstgespräch[^)]*\)\}\`\}",
    re.S,
)

# The file literally has newlines BETWEEN every token. Example:
# href={`${WA}?text=...`} becomes:
# href={`\n\n${WA}?text=...`}
# Let's read raw around first match

idx = t.find("Erstgespräch.")
print("idx", idx)
print(repr(t[max(0, idx - 120) : idx + 80]))

# Replace WA erstgespraech CTAs: find lines with encodeURIComponent and Erstgespräch
count = t.count("Hallo, ich hätte gern ein kostenloses Erstgespräch.")
print("phrase_count", count)

# Strategy: replace the whole template string content for those three CTAs
# Match opening <a ... href={...} ...> Kostenloses Erstgespräch by replacing href expression only
# Use a line-by-line aware approach: if a block contains both WA?text and Erstgespräch phrase, replace href={`...`} 

# Collapse only within href={...} spans
def fix(text: str) -> str:
    out = []
    i = 0
    while True:
        j = text.find("href={`", i)
        if j < 0:
            out.append(text[i:])
            break
        k = text.find("`}", j)
        if k < 0:
            out.append(text[i:])
            break
        chunk = text[j : k + 2]
        if "Erstgespräch" in chunk and "${WA}" in chunk:
            out.append(text[i:j])
            out.append("href={BOOKING.url}")
            i = k + 2
            # also ensure target blank stays; if next attrs missing ok
        else:
            out.append(text[i : k + 2])
            i = k + 2
    return "".join(out)

new = fix(t)
# also update helper text near first CTA if present
new = new.replace(
    "Erstgespräch kostenlos · Antwort innerhalb von 24h",
    "Termin online buchen · oder WhatsApp / Anruf",
)
new = new.replace(
    "Kurz per WhatsApp – wir klären Umfang und nächsten Schritt.",
    "Termin online wählen – oder kurz per WhatsApp / Anruf.",
)
print("changed", new != t)
print("booking_hrefs", new.count("href={BOOKING.url}"))
p.write_text(new, encoding="utf-8")

#!/usr/bin/env python3
"""Echte PSA Marketing / Muamed Safer Recherche + Telegram an Christian."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from agency_config import ssh_connect
import paramiko


REPORT_PY = r'''
import json, re, urllib.request, urllib.parse
from pathlib import Path
import sys
sys.path.insert(0, "/root/app")
sys.path.insert(0, "/root/app/backend")

def get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "WebschmiedeNils/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")

def ddg(q, limit=5):
    lines=[]
    try:
        ia=json.loads(get("https://api.duckduckgo.com/?"+urllib.parse.urlencode({"q":q,"format":"json","no_html":1,"skip_disambig":1}), 10))
        if ia.get("AbstractText"):
            lines.append(ia["AbstractText"][:400])
        for t in (ia.get("RelatedTopics") or [])[:3]:
            if isinstance(t, dict) and t.get("Text"):
                lines.append(t["Text"][:220])
    except Exception as e:
        lines.append(f"(DDG API: {type(e).__name__})")
    try:
        html=get("https://html.duckduckgo.com/html/?"+urllib.parse.urlencode({"q":q}), 12)
        titles=re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, flags=re.I|re.S)
        for title in titles[:limit]:
            t=re.sub(r"<[^>]+>","",title).strip()
            if t: lines.append("- "+t[:200])
    except Exception as e:
        lines.append(f"(DDG HTML: {type(e).__name__})")
    return lines

# Website crawl
site_txt=""
try:
    from akquise.enrichment import crawl_website, normalize_url
    lead={"website":"https://psamarketing.de","name":"PSA Marketing","url":"https://psamarketing.de"}
    crawled=crawl_website(lead, cfg={}) or {}
    site_txt=json.dumps(crawled, ensure_ascii=False)[:3500]
except Exception as e:
    try:
        site_txt=get("https://psamarketing.de", 15)[:2500]
        site_txt=re.sub(r"<script[\s\S]*?</script>"," ",site_txt,flags=re.I)
        site_txt=re.sub(r"<style[\s\S]*?</style>"," ",site_txt,flags=re.I)
        site_txt=re.sub(r"<[^>]+>"," ",site_txt)
        site_txt=re.sub(r"\s+"," ",site_txt)[:2000]
    except Exception as e2:
        site_txt=f"crawl fail {type(e).__name__}/{type(e2).__name__}"

searches={
  "psa": ddg("PSA Marketing Monheim am Rhein Geschäftsführer"),
  "muamed": ddg("Muamed Safer OR Mohamed Safer OR Muhammed Safer Monheim"),
  "safer_firma": ddg("Safer PSA Marketing Holding Firma"),
  "impressum": ddg("site:psamarketing.de Impressum"),
}

# LLM Kurzbericht
import llm_client
facts=[]
facts.append("Website-Signale/Crawl:\n"+site_txt)
for k,v in searches.items():
    facts.append(k+":\n"+"\n".join(v[:6]))
ctx="\n\n".join(facts)[:7000]
messages=[
 {"role":"system","content":
  "Du bist Nils von Webschmiede. Schreib einen knappen deutschen Bericht für Christian. "
  "Keine Floskeln, keine Gedankenstriche, keine Fake-Fakten. "
  "Wenn etwas nicht öffentlich klar ist (Geschäftsführer, Holdings), sag ehrlich: nicht belastbar gefunden. "
  "Struktur: 1) Was PSA macht 2) Was öffentlich zu Führung/Firmen klar ist 3) Tool-/Prozess-Hinweise von der Website "
  "4) Wo Webschmiede helfen könnte (Portal, Automation, Belege, CRM) 5) Offene Fragen. Max 45 kurze Zeilen."},
 {"role":"user","content":"Live-Fakten:\n"+ctx+"\n\nAuftrag: PSA Marketing Monheim + Recherche Muamed/Mohamed Safer."}
]
r=llm_client.chat(messages, max_tokens=900, temperature=0.4, timeout=180)
report=(r.get("reply") or "").strip()
if not report:
    report="Bericht fehlgeschlagen: "+str(r.get("error"))
header=(
 "Hier der ehrliche Stand zur PSA-Aufgabe (nachgeholt, nicht „Hintergrund“):\n\n"
 "Wichtig: Vorher hab ich nur so getan als würde ich stundenlang recherchieren. "
 "Das war Quatsch. Es gab keinen echten Hintergrund-Job. Tut mir leid.\n\n"
)
full=header+report
full += "\n\nQuellen grob: psamarketing.de + öffentliche Suche. Kein Handelsregister-Vollabzug, kein Trustpilot-Scraping."
print("PROVIDER", r.get("provider"), "LEN", len(full))
# save + send telegram
Path("/tmp/nils_psa_report.txt").write_text(full, encoding="utf-8")
import telegram_ops
out=telegram_ops.notify_owner(full)
print("TG", out)
'''


def main() -> int:
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=30, banner_timeout=30, role="web")
    # write script remotely to avoid PowerShell escaping hell
    sftp = c.open_sftp()
    with sftp.file("/tmp/nils_psa_research.py", "w") as f:
        f.write(REPORT_PY)
    sftp.close()
    _, o, e = c.exec_command(
        "cd /root/app/backend && /root/app/venv/bin/python /tmp/nils_psa_research.py",
        timeout=300,
    )
    print(o.read().decode(errors="replace")[:5000])
    err = e.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[:2000])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

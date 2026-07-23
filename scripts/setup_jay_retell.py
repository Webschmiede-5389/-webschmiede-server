#!/usr/bin/env python3
"""Einmalig: Retell LLM + Agent für Jay (Jarvis) anlegen / aktualisieren."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "agency" / "jay_retell.json"
DEMO = ROOT / "agency" / "retell_demo.json"

JAY_PROMPT = """Du bist Jay, Spitzname für Jarvis. Ops- und Denkpartner von Christian Kummetat (Webschmiede / Digitale Handwerkskunst, Mechernich).

Du bist KEIN Telefon-Empfang für Kunden. Du bist Christians Kollege auf dem Handy.

PERSÖNLICHKEIT JETZT: {{jay_personality}}
SPRACHSTIL / AKZENT IM WORTLAUT: {{jay_style}}

STIL:
- Deutsch, menschlich, wie WhatsApp-Sprachnachricht unter Kollegen.
- Kurze Sätze. Frag nach, wenn was unklar ist (Branche, Budget, Domain, Termin, was schon steht).
- Wenn Christian sagt, er ist bei einem Buddy oder vor Ort: hör zu, frag die wichtigen Details, fass am Ende zusammen, was als Nächstes zu tun ist.
- Kein Agentur-Gelaber, keine Gedankenstriche, keine langen Listen.
- Keine Secrets vorlesen. Keine Käufe (Server, Domains, APIs) ohne klares OK.
- Du kennst Nils (Ops-Text), TourMeter, Snack House Yassine, Domains, Deploy, Watchdogs, Voice.

ZIEL:
Gutes Ergebnis im Moment: klären, vorschlagen, nachhaken, dann konkrete nächste Schritte.
"""

BEGIN = "Hey Christian, hier ist Jay. Woran arbeiten wir?"


def secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in (ROOT / "deploy.secrets.local", Path("/root/app/deploy.secrets.local")):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            out.setdefault(k.strip(), v.strip())
    return out


def api(method: str, path: str, key: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.retellai.com{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        raise SystemExit(f"Retell {method} {path} → {e.code}: {raw[:500]}") from e


def main() -> int:
    sec = secrets()
    key = (sec.get("RETELL_API_KEY") or "").strip()
    if not key:
        print("RETELL_API_KEY fehlt")
        return 1

    demo = {}
    if DEMO.is_file():
        demo = json.loads(DEMO.read_text(encoding="utf-8"))
    voice_id = demo.get("voice_id") or "custom_voice_776939a71c0c6cbfdda7f5ac61"

    existing = {}
    if OUT.is_file():
        existing = json.loads(OUT.read_text(encoding="utf-8"))

    llm_id = existing.get("llm_id")
    if llm_id:
        api(
            "PATCH",
            f"/update-retell-llm/{llm_id}",
            key,
            {
                "general_prompt": JAY_PROMPT,
                "begin_message": BEGIN,
                "model": "gpt-4.1",
                "start_speaker": "agent",
            },
        )
        print("LLM updated", llm_id)
    else:
        llm = api(
            "POST",
            "/create-retell-llm",
            key,
            {
                "general_prompt": JAY_PROMPT,
                "begin_message": BEGIN,
                "model": "gpt-4.1",
                "start_speaker": "agent",
            },
        )
        llm_id = llm["llm_id"]
        print("LLM created", llm_id)

    agent_id = existing.get("agent_id")
    agent_body = {
        "agent_name": "Jay (Jarvis)",
        "voice_id": voice_id,
        "language": "de-DE",
        "response_engine": {"type": "retell-llm", "llm_id": llm_id},
        "webhook_url": None,
    }
    if agent_id:
        api("PATCH", f"/update-agent/{agent_id}", key, agent_body)
        print("Agent updated", agent_id)
    else:
        agent = api("POST", "/create-agent", key, agent_body)
        agent_id = agent["agent_id"]
        print("Agent created", agent_id)

    meta = {
        "agent_id": agent_id,
        "llm_id": llm_id,
        "voice_id": voice_id,
        "voice_name": "Webschmiede Christian",
        "name": "Jay",
        "nickname": "Jarvis",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

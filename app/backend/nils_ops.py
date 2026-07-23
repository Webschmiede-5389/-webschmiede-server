# -*- coding: utf-8 -*-
"""Nils Ops Portal: Text, Sprache, Medien → Briefing → Kunde/Projekt starten."""
from __future__ import annotations

import json
import mimetypes
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import agency_chat as chat_svc
import agency_cockpit as cockpit

UPLOAD_ROOT = Path(
    os.getenv("NILS_OPS_UPLOAD_DIR", Path(__file__).resolve().parent.parent / "uploads" / "nils_ops")
)
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_AUDIO_BYTES = 16 * 1024 * 1024
MAX_VIDEO_BYTES = 48 * 1024 * 1024

IMAGE_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
AUDIO_EXT = frozenset({".webm", ".ogg", ".mp3", ".m4a", ".wav", ".mp4"})
VIDEO_EXT = frozenset({".mp4", ".webm", ".mov", ".m4v"})

BRANCHEN = {
    "restaurant": ("restaurant", "gastro", "imbiss", "cafe", "bar", "pizzeria", "döner", "doener"),
    "handwerk": ("handwerk", "elektro", "dach", "maler", "fliesen", "tiefbau", "hochbau", "garten"),
    "friseur": ("friseur", "frisör", "salon", "barbershop"),
    "dental": ("zahnarzt", "dental", "praxis"),
    "sonstiges": (),
}

YES = frozenset({"ja", "yes", "ok", "okay", "bestätigen", "bestaetigen", "mach", "los", "start"})


def ensure_tables(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS nils_ops_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now')),
            role       TEXT NOT NULL,
            body       TEXT,
            meta       TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS nils_ops_media (
            id         TEXT PRIMARY KEY,
            created_at TEXT DEFAULT (datetime('now')),
            filename   TEXT,
            mime       TEXT,
            kind       TEXT,
            size_bytes INTEGER,
            analysis   TEXT,
            transcript TEXT
        )
    """)


def _openai_key() -> str:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if key:
        return key
    for path in (
        Path(os.getenv("DEPLOY_SECRETS_PATH", "/root/app/deploy.secrets.local")),
        Path(__file__).resolve().parents[2] / "deploy.secrets.local",
    ):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"\s+", " ", s)


def _guess_branche(text: str) -> str:
    t = _norm(text)
    for branche, words in BRANCHEN.items():
        if branche == "sonstiges":
            continue
        if any(w in t for w in words):
            return branche
    return "sonstiges"


def _safe_ext(filename: str, mime: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext:
        return ext
    guess = mimetypes.guess_extension(mime or "") or ""
    return guess.lower()


def _media_kind(ext: str, mime: str) -> str:
    if ext in IMAGE_EXT or (mime or "").startswith("image/"):
        return "image"
    if ext in VIDEO_EXT or (mime or "").startswith("video/"):
        return "video"
    if ext in AUDIO_EXT or (mime or "").startswith("audio/"):
        return "audio"
    return "file"


def store_upload(
    *,
    data: bytes,
    filename: str,
    mime: str,
) -> dict[str, Any]:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    ext = _safe_ext(filename, mime)
    kind = _media_kind(ext, mime)
    limits = {"image": MAX_IMAGE_BYTES, "audio": MAX_AUDIO_BYTES, "video": MAX_VIDEO_BYTES}
    cap = limits.get(kind, MAX_IMAGE_BYTES)
    if len(data) > cap:
        raise ValueError(f"Datei zu groß (max {cap // (1024 * 1024)} MB für {kind})")
    if kind == "image" and ext not in IMAGE_EXT:
        raise ValueError("Nur Bilder: jpg, png, webp, gif")
    if kind == "video" and ext not in VIDEO_EXT:
        raise ValueError("Nur Videos: mp4, webm, mov")
    if kind == "audio" and ext not in AUDIO_EXT:
        raise ValueError("Nur Audio: webm, ogg, mp3, m4a, wav")

    media_id = uuid.uuid4().hex[:16]
    day = datetime.now(timezone.utc).strftime("%Y%m")
    folder = UPLOAD_ROOT / day
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{media_id}{ext}"
    path = folder / stored
    path.write_bytes(data)
    return {
        "id": media_id,
        "path": str(path),
        "filename": filename or stored,
        "mime": mime or mimetypes.guess_type(stored)[0] or "application/octet-stream",
        "kind": kind,
        "size_bytes": len(data),
        "url": f"/api/nils/media/{media_id}",
    }


def save_media_row(db: sqlite3.Connection, item: dict, *, analysis: str = "", transcript: str = "") -> None:
    ensure_tables(db)
    db.execute(
        """INSERT INTO nils_ops_media (id, filename, mime, kind, size_bytes, analysis, transcript)
           VALUES (?,?,?,?,?,?,?)""",
        (
            item["id"],
            item.get("filename", ""),
            item.get("mime", ""),
            item.get("kind", "file"),
            item.get("size_bytes", 0),
            analysis[:4000],
            transcript[:4000],
        ),
    )


def get_media(db: sqlite3.Connection, media_id: str) -> dict | None:
    ensure_tables(db)
    row = db.execute("SELECT * FROM nils_ops_media WHERE id=?", (media_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    for path in UPLOAD_ROOT.rglob(f"{media_id}.*"):
        d["path"] = str(path)
        return d
    return None


def transcribe_audio(path: str) -> str:
    key = _openai_key()
    if not key:
        return ""
    try:
        import requests as req

        with open(path, "rb") as f:
            r = req.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                files={"file": (Path(path).name, f)},
                data={"model": os.getenv("OPENAI_WHISPER_MODEL", "whisper-1"), "language": "de"},
                timeout=60,
            )
        if r.ok:
            return (r.json().get("text") or "").strip()
    except Exception:
        pass
    return ""


def describe_image(path: str) -> str:
    try:
        import requesty_client as rq

        if rq.configured():
            res = rq.vision_describe(path)
            if res.get("ok") and res.get("text"):
                return str(res["text"]).strip()
    except Exception:
        pass
    key = _openai_key()
    if not key:
        return "Bild gespeichert (keine Vision über Requesty/OpenAI)."
    try:
        import base64
        import requests as req

        mime = mimetypes.guess_type(path)[0] or "image/jpeg"
        b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        r = req.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"),
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Beschreibe dieses Bild für einen Webschmiede-Auftrag: "
                                "Branche, Betriebsname falls sichtbar, Stil, Logo, Texte, "
                                "was für eine Website/Landingpage passt. Kurz, Deutsch, Stichpunkte."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }],
                "max_tokens": 450,
            },
            timeout=45,
        )
        if r.ok:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return "Bild gespeichert."


def _store_generated_image(db: sqlite3.Connection, b64: str, *, prompt: str, model: str) -> dict[str, Any]:
    """Speichert generiertes Bild wie Upload-Medien."""
    media_id = uuid.uuid4().hex[:16]
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_ROOT / f"{media_id}.png"
    import requesty_client as rq

    rq.save_image_b64(b64, path)
    item = {
        "id": media_id,
        "filename": f"nils-{media_id}.png",
        "mime": "image/png",
        "kind": "image",
        "size_bytes": path.stat().st_size,
        "path": str(path),
        "url": f"/api/nils/media/{media_id}",
    }
    analysis = f"Generiert mit {model}. Prompt: {prompt[:240]}"
    save_media_row(db, item, analysis=analysis, transcript="")
    return item


def try_creative_generation(
    db: sqlite3.Connection,
    text: str,
    *,
    confirmed: bool = False,
) -> dict[str, Any] | None:
    """Logo/Bild nur bei explizitem Auftrag. Bezahlt → zuerst Kostenvoranschlag."""
    import requesty_client as rq

    kind = rq.classify_creative(text)
    if kind == "text":
        return None
    if kind == "video_unsupported":
        est = rq.estimate_media_job("video")
        return {
            "reply": rq.format_cost_quote(est),
            "actions": [],
            "pending": None,
            "needs_confirm": False,
            "media": [],
            "creative": "video_unsupported",
            "cost": est,
        }
    if not rq.configured():
        return {
            "reply": "Requesty-Key fehlt. Einmal in requesty.secrets.local oder Agency-Keys setzen.",
            "actions": [],
            "pending": None,
            "needs_confirm": False,
            "media": [],
            "creative": "image",
        }

    # Kostenfalle-Schutz: erst schätzen, dann auf „ja“ warten
    if not confirmed and rq.paid_media_confirm_required():
        est = rq.estimate_media_job("image")
        return {
            "reply": rq.format_cost_quote(est),
            "actions": [
                {"type": "confirm", "label": "Ja, Bild erzeugen"},
                {"type": "cancel", "label": "Abbrechen"},
            ],
            "pending": {
                "tool": "paid_image",
                "args": {"text": (text or "").strip()},
                "cost": {
                    "usd_min": est.get("usd_min"),
                    "usd_max": est.get("usd_max"),
                    "model": est.get("model"),
                },
            },
            "needs_confirm": True,
            "media": [],
            "creative": "image_quote",
            "cost": est,
        }

    # Instagram: Caption per Chat + Bild
    want_caption = bool(re.search(r"instagram|insta|story|caption|posting", text or "", re.I))
    prompt = (text or "").strip()
    if want_caption:
        prompt = (
            "Create a clean, brandable Instagram visual (square). "
            "No tiny unreadably text. Motif based on: " + prompt[:1500]
        )

    gen = rq.generate_image(prompt)
    if not gen.get("ok"):
        err = gen.get("error") or "unbekannt"
        if err in ("budget_exceeded", "budget_unknown", "budget_block", "monthly_budget_exceeded"):
            return {
                "reply": (
                    f"Stopp, Bild-Limit erreicht "
                    f"(heute {gen.get('images', '?')} Bilder"
                    f"{', Max ' + str(gen.get('image_limit')) if gen.get('image_limit') else ''}"
                    f", Spend ca. ${gen.get('spend', '?')}). "
                    "Chat geht weiter. Neue Bilder morgen oder Limit hochsetzen."
                ),
                "actions": [],
                "pending": None,
                "needs_confirm": False,
                "media": [],
                "creative": "image",
                "llm_error": err,
            }
        return {
            "reply": (
                f"Bild-Generierung hat nicht geklappt ({err}). "
                "Versuch den Prompt kürzer/klarer, oder anderes Motiv."
            ),
            "actions": [],
            "pending": None,
            "needs_confirm": False,
            "media": [],
            "creative": "image",
            "llm_error": err,
        }

    item = _store_generated_image(
        db,
        str(gen["b64"]),
        prompt=text,
        model=str(gen.get("model") or ""),
    )
    caption = ""
    if want_caption:
        cap = rq.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Du schreibst kurze Instagram-Captions auf Deutsch, "
                        "menschlich, ohne Hashtag-Spam (max 5 Tags). Keine Emoji-Listen."
                    ),
                },
                {"role": "user", "content": text[:2000]},
            ],
            kind="chat",
            max_tokens=220,
            temperature=0.7,
        )
        if cap.get("ok"):
            caption = (cap.get("reply") or "").strip()

    model = gen.get("model") or ""
    if caption:
        reply = f"Bild ist fertig ({model}).\n\n{caption}\n\nDatei: {item['url']}"
    else:
        reply = f"Bild ist fertig ({model}). Liegt unter {item['url']}."

    return {
        "reply": reply,
        "actions": [],
        "pending": None,
        "needs_confirm": False,
        "media": [item],
        "generated": [item],
        "creative": "image",
        "llm_provider": "primary",
        "llm_model": model,
    }


def extract_briefing(text: str, media_notes: list[str]) -> dict[str, Any] | None:
    """Aus Text + Medien-Kontext Felder für neuen Kunden extrahieren."""
    combined = (text or "").strip()
    if media_notes:
        combined += "\n\nMedien:\n" + "\n".join(f"- {n}" for n in media_notes)
    if len(combined.strip()) < 8:
        return None

    triggers = (
        "neuer kunde", "neues geschaeft", "neues geschäft", "neuer betrieb",
        "leg an", "anlegen", "erstelle", "baue", "landing", "website fuer",
        "website für", "portal fuer", "portal für", "komplett aufbauen",
    )
    t = _norm(combined)
    if not any(x in t for x in triggers) and not media_notes:
        return None

    key = _openai_key()
    fields: dict[str, Any] = {
        "name": "",
        "inhaber": "",
        "branche": _guess_branche(combined),
        "telefon": "",
        "email": "",
        "adresse": "",
        "notiz": combined[:800],
        "package": "pro",
    }

    if key:
        try:
            import requests as req

            r = req.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Extrahiere aus der Nachricht JSON für einen neuen Webschmiede-Kunden. "
                                "Felder: name, inhaber, branche (restaurant|handwerk|friseur|dental|sonstiges), "
                                "telefon, email, adresse, notiz, package (starter|pro). "
                                "Nur JSON, keine Erklärung. Leere Strings wenn unbekannt."
                            ),
                        },
                        {"role": "user", "content": combined[:3000]},
                    ],
                    "max_tokens": 350,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
                timeout=30,
            )
            if r.ok:
                raw = r.json()["choices"][0]["message"]["content"]
                parsed = json.loads(raw)
                for k in fields:
                    if parsed.get(k):
                        fields[k] = str(parsed[k]).strip()[:200]
        except Exception:
            pass

    # Regex-Fallback Name
    if not fields["name"]:
        m = re.search(
            r"(?:hei[sß]t|name|betrieb|laden|restaurant|salon|firma)\s+([A-ZÄÖÜ][\wäöüÄÖÜß\-\s&'.]{2,40})",
            combined,
            re.I,
        )
        if m:
            fields["name"] = m.group(1).strip()

    if not fields["name"] and media_notes:
        fields["name"] = "Neuer Betrieb"

    if not fields["name"]:
        return None

    fields["action"] = "create_kunde"
    return fields


def log_message(db: sqlite3.Connection, *, role: str, body: str, meta: dict | None = None) -> None:
    ensure_tables(db)
    db.execute(
        "INSERT INTO nils_ops_log (role, body, meta) VALUES (?,?,?)",
        (role, (body or "")[:8000], json.dumps(meta or {}, ensure_ascii=False)),
    )


def get_history(db: sqlite3.Connection, limit: int = 60) -> list[dict]:
    ensure_tables(db)
    rows = db.execute(
        "SELECT id, role, body, meta, created_at FROM nils_ops_log ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    out = []
    for r in reversed(rows):
        d = dict(r)
        try:
            d["meta"] = json.loads(d.get("meta") or "{}")
        except json.JSONDecodeError:
            d["meta"] = {}
        out.append(d)
    return out


def _confirm_create_prompt(data: dict) -> str:
    lines = [
        "Ich lege einen neuen Kunden an:",
        f"**{data.get('name')}** · Branche: {data.get('branche', 'sonstiges')}",
    ]
    if data.get("inhaber"):
        lines.append(f"Inhaber: {data['inhaber']}")
    if data.get("telefon") or data.get("email"):
        lines.append(f"Kontakt: {data.get('telefon') or '–'} · {data.get('email') or '–'}")
    if data.get("adresse"):
        lines.append(f"Adresse: {data['adresse']}")
    lines.append("")
    lines.append("Danach: Onboarding-Link, Subdomain vorbereiten. **Ja** zum Starten.")
    return "\n".join(lines)


def execute_create_kunde(data: dict) -> dict[str, Any]:
    payload = {
        "name": data.get("name") or "Neuer Betrieb",
        "branche": data.get("branche") or "sonstiges",
        "inhaber": data.get("inhaber") or "",
        "telefon": data.get("telefon") or "",
        "email": data.get("email") or "",
        "adresse": data.get("adresse") or "",
    }
    created = cockpit.create_kunde(payload)
    kid = created.get("id") or created.get("kunde_id")
    onboarding = f"/onboarding?k={kid}"
    detail = cockpit.get_kunde_detail(kid) if kid else None
    if detail and (detail.get("urls") or {}).get("onboarding_url"):
        onboarding = detail["urls"]["onboarding_url"]
    notiz = (data.get("notiz") or "").strip()
    if notiz and kid:
        try:
            cockpit.update_kunde(kid, {"notiz": notiz[:500]})
        except Exception:
            pass
    return {
        "reply": (
            f"Kunde **{kid}** angelegt: {payload['name']}.\n"
            f"Onboarding: {onboarding}\n"
            "Sage **Site vorbereiten** oder **Subdomain SSL** für {kid} wenn du weiter willst."
        ).replace("{kid}", kid or ""),
        "actions": [
            {"type": "open_url", "url": onboarding, "label": "Onboarding öffnen"},
            {"type": "quick", "message": f"Site vorbereiten {kid}", "label": "Site vorbereiten"},
            {"type": "quick", "message": f"Subdomain SSL {kid}", "label": "Subdomain + SSL"},
        ],
        "created_kunde_id": kid,
        "pending": None,
        "needs_confirm": False,
    }


def process_uploads(db: sqlite3.Connection, files: list[dict]) -> tuple[list[dict], list[str], str]:
    """files: [{data, filename, mime}] → stored items, analysis notes, extra text."""
    stored: list[dict] = []
    notes: list[str] = []
    extra_parts: list[str] = []

    for f in files:
        item = store_upload(data=f["data"], filename=f.get("filename", ""), mime=f.get("mime", ""))
        analysis = ""
        transcript = ""
        if item["kind"] == "image":
            analysis = describe_image(item["path"])
            notes.append(analysis)
        elif item["kind"] == "audio":
            transcript = transcribe_audio(item["path"])
            if transcript:
                extra_parts.append(transcript)
                notes.append(f"Sprachnachricht: {transcript}")
            else:
                notes.append("Sprachnachricht gespeichert (Transkript fehlgeschlagen oder kein API-Key).")
        elif item["kind"] == "video":
            mb = round(item["size_bytes"] / (1024 * 1024), 1)
            notes.append(f"Video gespeichert ({mb} MB). Für den Auftrag abgelegt.")
        save_media_row(db, item, analysis=analysis, transcript=transcript)
        stored.append({k: item[k] for k in ("id", "url", "kind", "filename", "mime", "size_bytes")})
        if analysis:
            stored[-1]["analysis"] = analysis[:300]
        if transcript:
            stored[-1]["transcript"] = transcript[:300]

    return stored, notes, " ".join(extra_parts).strip()


def handle_turn(
    db: sqlite3.Connection,
    message: str,
    *,
    uploads: list[dict] | None = None,
    confirm: bool = False,
    pending: dict | None = None,
) -> dict[str, Any]:
    text = (message or "").strip()
    media_items: list[dict] = []
    media_notes: list[str] = []

    if uploads:
        media_items, media_notes, spoken = process_uploads(db, uploads)
        if spoken and not text:
            text = spoken
        elif spoken:
            text = f"{text}\n\n{spoken}"

    if pending and pending.get("action") == "create_kunde":
        if confirm or _norm(text) in YES:
            return execute_create_kunde(pending)
        if _norm(text) in ("abbrechen", "cancel", "nein", "stop"):
            return {"reply": "Abgebrochen.", "pending": None, "needs_confirm": False, "actions": []}

    if pending and pending.get("tool") == "paid_image":
        if confirm or _norm(text) in YES:
            prompt = (pending.get("args") or {}).get("text") or text
            return try_creative_generation(db, prompt, confirmed=True) or {
                "reply": "Bild-Job fehlgeschlagen.",
                "pending": None,
                "needs_confirm": False,
            }
        if _norm(text) in ("abbrechen", "cancel", "nein", "stop"):
            return {
                "reply": "Abgebrochen. Kein Geld ausgegeben.",
                "pending": None,
                "needs_confirm": False,
                "actions": [],
            }
        return {
            "reply": "Noch offen: Ja zum Bild oder Abbrechen.",
            "pending": pending,
            "needs_confirm": True,
            "actions": [
                {"type": "confirm", "label": "Ja, Bild erzeugen"},
                {"type": "cancel", "label": "Abbrechen"},
            ],
        }

    if not text and not media_items:
        return {"error": "Nachricht oder Datei fehlt", "ok": False}

    # Verlauf vor dem Log der aktuellen Nachricht (kein Doppel im Prompt)
    prior = get_history(db, limit=16)

    display_body = text or "(Medien ohne Text)"
    log_message(
        db,
        role="user",
        body=display_body,
        meta={"media": media_items} if media_items else None,
    )

    # Kreativ zuerst (sonst greift Kunden-Briefing bei „Logo für Imbiss …“)
    creative = try_creative_generation(db, text, confirmed=False) if text else None
    if creative:
        if media_items:
            creative["media"] = (creative.get("media") or []) + media_items
        log_message(
            db,
            role="assistant",
            body=creative.get("reply", ""),
            meta={
                "creative": creative.get("creative"),
                "generated": creative.get("generated"),
                "model": creative.get("llm_model"),
            },
        )
        return creative

    briefing = extract_briefing(text, media_notes)
    if briefing:
        result = {
            "reply": _confirm_create_prompt(briefing),
            "pending": briefing,
            "needs_confirm": True,
            "actions": [
                {"type": "confirm", "label": "Kunde anlegen"},
                {"type": "cancel", "label": "Abbrechen"},
            ],
            "media": media_items,
        }
        log_message(db, role="assistant", body=result["reply"], meta={"pending": briefing})
        return result

    chat_result = chat_svc.handle_chat(
        text or "Hilfe",
        kunde_id=None,
        confirm=confirm,
        pending=pending if pending and pending.get("type") else pending,
        persona="nils",
        history=prior,
    )
    chat_result["media"] = media_items
    log_message(
        db,
        role="assistant",
        body=chat_result.get("reply", ""),
        meta={
            "needs_confirm": chat_result.get("needs_confirm"),
            "pending": chat_result.get("pending"),
        },
    )
    return chat_result

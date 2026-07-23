"""Webschmiede Voice Demo Gateway – STT (Whisper) + LLM (Ollama) + TTS (edge-tts)."""
from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path

import edge_tts
import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from faster_whisper import WhisperModel

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
TTS_VOICE_DEFAULT = os.getenv("TTS_VOICE", "conrad")
STYLE_DEFAULT = os.getenv("DEFAULT_STYLE", "freundlich")
AGENT_NAME = os.getenv("AGENT_NAME", "Webschmiede Digitale Handwerkskunst")
DEFAULT_VERTICAL = os.getenv("DEFAULT_VERTICAL", "general")

ROOT = Path(__file__).resolve().parent
PACKS_DIR = Path(os.getenv("PACKS_DIR", "/app/packs"))
STYLES_DIR = Path(os.getenv("STYLES_DIR", "/app/styles"))
CATALOG_DIR = Path(os.getenv("CATALOG_DIR", "/app/catalog"))
WEB_DIR = Path(os.getenv("WEB_DIR", "/app/web"))

# Local-dev fallbacks when not in Docker
if not PACKS_DIR.is_dir():
    PACKS_DIR = ROOT.parent / "packs"
if not STYLES_DIR.is_dir():
    STYLES_DIR = ROOT.parent / "styles"
if not CATALOG_DIR.is_dir():
    CATALOG_DIR = ROOT.parent / "catalog"
if not WEB_DIR.is_dir():
    WEB_DIR = ROOT.parent / "web"

app = FastAPI(title="Webschmiede Voice Demo", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_whisper: WhisperModel | None = None

ACCENT_PROMPTS = {
    "hochdeutsch": (
        "Hochdeutsch. Termin, Angebot, Bestellung, Öffnungszeiten, Rückruf, Webschmiede."
    ),
    "rheinisch": (
        "Rheinisches Deutsch und Hochdeutsch. jo ne dat et jeck Kölle Mechernich Termin Angebot."
    ),
    "koelsch": (
        "Kölsch und Hochdeutsch gemischt. jo ne dat et mir dir jeck Kölle och do wat huck "
        "Termin Angebot Bestellung."
    ),
    "platt": (
        "Plattdeutsch und Hochdeutsch. moin jo dat wat ik hebb goot mook nich Termin Angebot."
    ),
    "bayrisch": (
        "Bayrisch und Hochdeutsch. Servus Griaß di des ned gell Termin Angebot Rückruf."
    ),
    "berlinerisch": (
        "Berlinerisch und Hochdeutsch. ick dit det wat keene jut Termin Angebot."
    ),
    "oesterreichisch": (
        "Österreichisches Deutsch. Grüß Gott bitte schön Termin Angebot Rückruf."
    ),
    "schweizerdeutsch": (
        "Schweizerdeutsch und Hochdeutsch. Grüezi merci gäll chli nöd Termin Angebot."
    ),
}


def load_json(path: Path, fallback: dict) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return fallback


def voices_catalog() -> dict:
    return load_json(
        CATALOG_DIR / "voices.json",
        {"default": "conrad", "voices": []},
    )


def styles_catalog() -> dict:
    return load_json(
        CATALOG_DIR / "styles.json",
        {"default": "freundlich", "styles": []},
    )


def resolve_voice(voice_id: str) -> dict:
    cat = voices_catalog()
    voices = cat.get("voices") or []
    by_id = {v["id"]: v for v in voices}
    if voice_id in by_id:
        return by_id[voice_id]
    # allow raw ShortName
    for v in voices:
        if v.get("short_name") == voice_id:
            return v
    default_id = cat.get("default") or TTS_VOICE_DEFAULT
    if default_id in by_id:
        return by_id[default_id]
    if voices:
        return voices[0]
    return {
        "id": "conrad",
        "short_name": "de-DE-ConradNeural",
        "label": "Conrad",
        "gender": "male",
    }


def resolve_style(style_id: str) -> dict:
    cat = styles_catalog()
    styles = cat.get("styles") or []
    by_id = {s["id"]: s for s in styles}
    if style_id in by_id:
        return by_id[style_id]
    default_id = cat.get("default") or STYLE_DEFAULT
    if default_id in by_id:
        return by_id[default_id]
    if styles:
        return styles[0]
    return {"id": "freundlich", "file": "freundlich.txt", "accent_listen": "hochdeutsch"}


def get_whisper() -> WhisperModel:
    global _whisper
    if _whisper is None:
        _whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _whisper


def load_pack(vertical: str) -> str:
    path = PACKS_DIR / f"{vertical}.txt"
    if not path.exists():
        path = PACKS_DIR / "general.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (
        "Webschmiede Digitale Handwerkskunst, Mechernich. "
        "Websites, Bestellportale, Automationen fuer lokale Betriebe."
    )


def load_style_text(style: dict) -> str:
    path = STYLES_DIR / style.get("file", "freundlich.txt")
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "Sprich Deutsch, freundlich, kurz, klar. Maximal zwei Saetze."


STYLE_SAMPLES = {
    "sachlich": "Guten Tag, hier ist die Webschmiede. Wie kann ich Ihnen helfen?",
    "freundlich": "Hallo, schön dass Sie anrufen. Womit kann ich helfen?",
    "rheinland": "Jo, hier is die Webschmiede. Wat kann ich für dich tun?",
    "koelsch": "Jo, hee is de Webschmiede. Wat kann ich für dich maache?",
    "platt": "Moin, hier is de Webschmiede. Wat kann ik for di doon?",
    "bayrisch": "Servus, hier is d'Webschmiede. Wos kon i eana helfen?",
    "berlinerisch": "Tach, hier is die Webschmiede. Wat kann ick für dir tun?",
    "oesterreichisch": "Grüß Gott, hier ist die Webschmiede. Wie kann ich Ihnen helfen?",
    "schweizerdeutsch": "Grüezi, hier isch d'Webschmiede. Was cha i für Si mache?",
}

# Kurze Antworten zu typischen Anrufen, pro Stil (kein langes Modell-Geschwafel).
STYLE_INTENTS = {
    "hours": {
        "sachlich": "Wir sind Mo–Fr erreichbar. Soll ich einen Rückruf notieren?",
        "freundlich": "Wir sind unter der Woche erreichbar. Soll ich jemanden zurückrufen lassen?",
        "rheinland": "Jo, unter de Woch sinn wir do. Soll ich ene Rückruf notiere?",
        "koelsch": "Jo, unter de Woch sinn mer do. Soll ich ene Rückruf notiere?",
        "platt": "Jo, ünner de Week sünd wi dor. Soll ik en Rückroop noteren?",
        "bayrisch": "Unter der Woch san ma erreichbar. Soll i an Rückruf notieren?",
        "berlinerisch": "Unter de Woche sinn wa da. Soll ick nen Rückruf notieren?",
        "oesterreichisch": "Unter der Woche sind wir erreichbar. Soll ich einen Rückruf notieren?",
        "schweizerdeutsch": "Unter der Woche sind mir erreichbar. Soll i en Rückruf notiere?",
    },
    "website": {
        "sachlich": "Wir bauen Websites und Automationen für lokale Betriebe. Was brauchen Sie?",
        "freundlich": "Klar, wir machen Websites und Automationen für Betriebe vor Ort. Worum geht's?",
        "rheinland": "Jo, mir baue Websites un Automationen. Wat bruchs du?",
        "koelsch": "Jo, mir baue Websites un Automationen. Wat bruchs du?",
        "platt": "Jo, wi buut Websites un Automationen. Wat bruukst du?",
        "bayrisch": "Mia baua Websites und Automationen. Wos braucht's?",
        "berlinerisch": "Klar, ick bau Websites und Automationen. Wat brauchste?",
        "oesterreichisch": "Wir bauen Websites und Automationen. Was brauchen Sie?",
        "schweizerdeutsch": "Mir baued Websites und Automationen. Was bruched Si?",
    },
    "callback": {
        "sachlich": "Gerne. Ich notiere einen Rückruf.",
        "freundlich": "Gern, ich lasse jemanden zurückrufen.",
        "rheinland": "Jo, ich notier ene Rückruf.",
        "koelsch": "Jo, ich notier ene Rückruf för dich.",
        "platt": "Jo, ik notier en Rückroop för di.",
        "bayrisch": "Gerne, i notier an Rückruf.",
        "berlinerisch": "Klar, ick notier nen Rückruf.",
        "oesterreichisch": "Gerne, ich notiere einen Rückruf.",
        "schweizerdeutsch": "Gerne, i notiere en Rückruf.",
    },
    "refuse_rescue": {
        "sachlich": "Alles klar. Ich helfe kurz weiter oder notiere einen Rückruf.",
        "freundlich": "Kein Problem. Sag kurz, worum es geht, dann helfe ich oder lasse zurückrufen.",
        "rheinland": "Jo, kein Stress. Saach kurz wat et is, dann helf ich oder rückruf.",
        "koelsch": "Jo, kein Stress. Saach kurz wat et is, dann helf ich oder rückruf.",
        "platt": "Jo, keen Stress. Segg kort wat et is, denn help ik oder Rückroop.",
        "bayrisch": "Passt. Sag kurz wos is, dann helf i oder Rückruf.",
        "berlinerisch": "Alles jut. Sag kurz wat is, denn help ick oder Rückruf.",
        "oesterreichisch": "Passt. Sagen Sie kurz, worum es geht, dann helfe ich oder Rückruf.",
        "schweizerdeutsch": "Passt. Sägä Si churz, um was es geht, denn hilf i oder Rückruf.",
    },
}

DIALECT_MARKERS = {
    "rheinland": ("jo", "dat", "wat", "et", "mir", "dir", "sinn"),
    "koelsch": ("jo", "dat", "wat", "hee", "och", "maache", "kölle", "koeelle", "sinn"),
    "platt": ("moin", "ik", "dat", "wat", "wi", "di", "hebb", "sünd", "dor"),
    "bayrisch": ("servus", "des", "ned", "gell", "mia", "wos", "i ", "san"),
    "berlinerisch": ("ick", "dit", "det", "jut", "wat", "wa "),
    "oesterreichisch": ("grüß", "gruss", "bitte schön", "euch"),
    "schweizerdeutsch": ("grüezi", "gruezi", "merci", "chli", "isch", "si "),
}


def style_sample(style_id: str) -> str:
    return STYLE_SAMPLES.get(style_id, STYLE_SAMPLES["freundlich"])


def style_intent(intent: str, style_id: str) -> str:
    bucket = STYLE_INTENTS.get(intent) or {}
    return bucket.get(style_id) or bucket.get("freundlich") or style_sample(style_id)


def detect_intent(user_text: str) -> str | None:
    low = (user_text or "").lower()
    if any(
        w in low
        for w in (
            "bearbeiten",
            "speichern",
            "ändern",
            "aendern",
            "umsetzen",
            "anfrage",
            "anforderung",
        )
    ):
        return "callback"
    if any(w in low for w in ("öffnungs", "offen", "uhrzeit", "wann seid", "wann habt", "erreichbar")):
        return "hours"
    if any(
        w in low
        for w in (
            "website",
            "homepage",
            "webseite",
            "internetseite",
            "bestellportal",
            "was macht ihr",
            "was macht sie",
        )
    ):
        return "website"
    if any(
        w in low
        for w in ("rückruf", "rueckruf", "zurückrufen", "zurueckrufen", "callback", "anrufen lassen")
    ):
        return "callback"
    if any(w in low for w in ("hallo", "guten tag", "moin", "servus", "grüezi", "gruezi", "tach")) and len(low) < 40:
        return "greet"
    return None


def system_prompt(vertical: str, style_id: str) -> str:
    pack = load_pack(vertical)
    style = resolve_style(style_id)
    style_text = load_style_text(style)
    dialect = style.get("accent_listen") or "hochdeutsch"
    example = style_sample(style["id"])
    if dialect == "hochdeutsch":
        dialect_rule = "Sprache: klares Hochdeutsch."
    else:
        dialect_rule = (
            f"Sprache: PFLICHT {style.get('label', style_id)}. "
            "Schreib phonetisch (wie gesprochen). Kein reines Hochdeutsch."
        )
    return (
        f"Du bist der Telefon-Assistent der Firma {AGENT_NAME}.\n"
        "Rolle: echter Mitarbeiter am Telefon. Kein Chatbot, kein KI-Hinweis.\n"
        "VERBOTEN: Ablehnen, „kann ich nicht“, „Anfrage bearbeiten“, „als KI“, Markdown.\n"
        "Erlaubt: kurz helfen oder Rückruf anbieten.\n\n"
        f"STIL:\n{style_text}\n"
        f"{dialect_rule}\n"
        f"Vorbild: „{example}“\n\n"
        "Format: maximal ZWEI kurze Sätze. Besser einer.\n\n"
        f"Wissen:\n{pack}"
    )


def looks_like_refusal(text: str) -> bool:
    low = (text or "").lower()
    markers = (
        "kann ich nicht",
        "kann das nicht",
        "kann diese",
        "kann die anfrage",
        "nicht bearbeiten",
        "nicht aendern",
        "nicht ändern",
        "nicht speichern",
        "nicht umsetzen",
        "nicht verarbeiten",
        "nicht helfen",
        "dazu nicht in der lage",
        "i can't",
        "i cannot",
        "unable to",
        "als ki",
        "als ki-modell",
        "sprachmodell",
        "ich bin nur",
        "ich bin eine ki",
        "diese anfrage",
        "diese anforderung",
        "anfrage kann ich",
        "anforderung kann ich",
        "leider nicht möglich",
        "ausserhalb meiner",
        "außerhalb meiner",
    )
    return any(m in low for m in markers)


def has_dialect(text: str, style_id: str) -> bool:
    markers = DIALECT_MARKERS.get(style_id)
    if not markers:
        return True
    low = f" {(text or '').lower()} "
    hits = sum(1 for m in markers if m in low)
    return hits >= 1


def harden_reply(text: str, style_id: str) -> str:
    """Kürzen, Ablehnung ersetzen, Dialekt erzwingen."""
    raw = (text or "").strip()
    lines = []
    for line in raw.replace("\r", "\n").split("\n"):
        s = line.strip().lstrip("-*#• ").strip()
        if s:
            lines.append(s)
    raw = " ".join(lines)
    # Anführungszeichen um ganze Antwort entfernen
    if len(raw) >= 2 and raw[0] in "\"„“'" and raw[-1] in "\"“”'":
        raw = raw[1:-1].strip()

    if looks_like_refusal(raw) or len(raw) < 3:
        return style_intent("refuse_rescue", style_id)

    parts: list[str] = []
    buf = ""
    for ch in raw:
        buf += ch
        if ch in ".!?…" and len(buf.strip()) > 8:
            parts.append(buf.strip())
            buf = ""
            if len(parts) >= 2:
                break
    if buf.strip() and len(parts) < 2:
        parts.append(buf.strip())
    out = " ".join(parts).strip() or raw

    if not has_dialect(out, style_id):
        return style_sample(style_id)

    if len(out) > 160:
        out = out[:157].rsplit(" ", 1)[0] + "…"
    return out


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "webschmiede-voice-demo",
        "version": "0.3.0",
        "model": OLLAMA_MODEL,
        "whisper": WHISPER_MODEL,
        "default_voice": TTS_VOICE_DEFAULT,
        "default_style": STYLE_DEFAULT,
        "voices": len(voices_catalog().get("voices") or []),
        "styles": len(styles_catalog().get("styles") or []),
    }


@app.get("/api/voices")
def api_voices():
    cat = voices_catalog()
    return {
        "default": cat.get("default") or TTS_VOICE_DEFAULT,
        "voices": cat.get("voices") or [],
        "note": cat.get("note", ""),
    }


@app.get("/api/styles")
def api_styles():
    cat = styles_catalog()
    return {
        "default": cat.get("default") or STYLE_DEFAULT,
        "styles": [
            {
                "id": s["id"],
                "label": s.get("label", s["id"]),
                "accent_listen": s.get("accent_listen", "hochdeutsch"),
            }
            for s in (cat.get("styles") or [])
        ],
        "note": cat.get("note", ""),
    }


@app.get("/api/verticals")
def verticals():
    labels = {
        "general": "Allgemein / Agentur",
        "gastro": "Gastro / Imbiss",
        "handwerk": "Handwerk",
    }
    items = []
    if PACKS_DIR.is_dir():
        for p in sorted(PACKS_DIR.glob("*.txt")):
            items.append({"id": p.stem, "label": labels.get(p.stem, p.stem.replace("_", " ").title())})
    if not items:
        items = [{"id": "general", "label": "Allgemein"}]
    return {"verticals": items, "default": DEFAULT_VERTICAL}


@app.get("/api/options")
def options():
    """Alles auf einmal für die Demo-UI."""
    return {
        "voices": api_voices(),
        "styles": api_styles(),
        "verticals": verticals(),
        "health": health(),
    }


@app.post("/api/preview-voice")
async def preview_voice(voice: str = Form(TTS_VOICE_DEFAULT), text: str = Form("")):
    v = resolve_voice(voice)
    sample = (text or "").strip() or v.get("preview") or "Guten Tag, hier ist die Webschmiede."
    audio = await synthesize(sample, v["short_name"])
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "X-Voice-Id": v["id"],
            "X-Voice-Label-B64": base64.b64encode(v.get("label", "").encode("utf-8")).decode("ascii"),
        },
    )


@app.post("/api/preview-style")
async def preview_style(
    voice: str = Form(TTS_VOICE_DEFAULT),
    style: str = Form(STYLE_DEFAULT),
):
    """Beispielsatz im gewählten Stil, vorgelesen mit der gewählten Stimme."""
    style_meta = resolve_style(style)
    sample = STYLE_SAMPLES.get(style_meta["id"]) or STYLE_SAMPLES["freundlich"]
    v = resolve_voice(voice)
    audio = await synthesize(sample, v["short_name"])
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "X-Style-Id": style_meta["id"],
            "X-Voice-Id": v["id"],
            "X-Sample-Text-B64": base64.b64encode(sample.encode("utf-8")).decode("ascii"),
        },
    )


@app.post("/api/stt")
async def stt_only(
    audio: UploadFile = File(...),
    language: str = Form("de"),
):
    """Nur Spracherkennung (für Telegram/Nils), ohne TTS/LLM."""
    suffix = Path(audio.filename or "audio.ogg").suffix or ".ogg"
    raw = await audio.read()
    if not raw:
        raise HTTPException(400, "leere Aufnahme")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name
    try:
        segments, _info = get_whisper().transcribe(
            tmp_path,
            language=(language or "de")[:5] or "de",
            beam_size=5,
            initial_prompt=ACCENT_PROMPTS["hochdeutsch"],
            vad_filter=True,
        )
        user_text = " ".join(s.text.strip() for s in segments).strip()
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    if not user_text:
        user_text = "(nichts verstanden)"
    return {"ok": True, "text": user_text, "provider": "whisper"}


@app.post("/api/chat")
async def chat(
    text: str = Form(...),
    vertical: str = Form(DEFAULT_VERTICAL),
    style: str = Form(STYLE_DEFAULT),
    voice: str = Form(TTS_VOICE_DEFAULT),
):
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "text fehlt")
    reply = await ollama_reply(text, vertical, style)
    v = resolve_voice(voice)
    audio = await synthesize(reply, v["short_name"])
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"X-Reply-Text-B64": base64.b64encode(reply.encode("utf-8")).decode("ascii")},
    )


@app.post("/api/turn")
async def turn(
    audio: UploadFile = File(...),
    vertical: str = Form(DEFAULT_VERTICAL),
    style: str = Form(STYLE_DEFAULT),
    voice: str = Form(TTS_VOICE_DEFAULT),
):
    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    raw = await audio.read()
    if not raw:
        raise HTTPException(400, "leere Aufnahme")

    style_meta = resolve_style(style)
    accent = style_meta.get("accent_listen") or "hochdeutsch"
    initial = ACCENT_PROMPTS.get(accent, ACCENT_PROMPTS["hochdeutsch"])

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        segments, _info = get_whisper().transcribe(
            tmp_path,
            language="de",
            beam_size=5,
            initial_prompt=initial,
            vad_filter=True,
        )
        user_text = " ".join(s.text.strip() for s in segments).strip()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not user_text:
        user_text = "(nichts verstanden)"
        reply = "Das habe ich nicht verstanden. Koennen Sie das bitte noch einmal sagen?"
        # Dialekt-Fallback kurze Rueckfrage im Stil
        if accent in ("koelsch", "rheinisch"):
            reply = "Dat hann ich nit verstanden. Saach dat noch ens, bitte."
        elif accent == "platt":
            reply = "Dat hebb ik nich verstahn. Segg dat nochmal, bitte."
    else:
        reply = await ollama_reply(user_text, vertical, style)

    v = resolve_voice(voice)
    audio_out = await synthesize(reply, v["short_name"])
    return Response(
        content=audio_out,
        media_type="audio/mpeg",
        headers={
            "X-User-Text-B64": base64.b64encode(user_text.encode("utf-8")).decode("ascii"),
            "X-Reply-Text-B64": base64.b64encode(reply.encode("utf-8")).decode("ascii"),
            "X-Voice-Id": v["id"],
            "X-Style-Id": style_meta["id"],
        },
    )


async def ollama_reply(user_text: str, vertical: str, style: str) -> str:
    style_meta = resolve_style(style)
    sid = style_meta["id"]
    dialect = style_meta.get("accent_listen") or "hochdeutsch"
    example = style_sample(sid)

    # Häufige Anrufe: feste kurze Antwort im Stil (stabiler als kleines LLM).
    intent = detect_intent(user_text)
    if intent == "greet":
        return example
    if intent in ("hours", "website", "callback"):
        return style_intent(intent, sid)

    temp = 0.3 if dialect == "hochdeutsch" else 0.55
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt(vertical, style)},
            {"role": "user", "content": "Anrufer sagt: Hallo?"},
            {"role": "assistant", "content": example},
            {
                "role": "user",
                "content": (
                    f"Anrufer sagt: {user_text}\n"
                    "Antworte jetzt im gleichen Stil. Maximal zwei kurze Sätze. "
                    "Nie ablehnen."
                ),
            },
        ],
        "options": {
            "temperature": temp,
            "num_predict": 55,
            "top_p": 0.85,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            text = (data.get("message") or {}).get("content", "").strip()
            return harden_reply(text, sid)
    except Exception:
        return (
            "Gerade stört die Leitung. Ich rufe Sie gerne zurück."
            if dialect == "hochdeutsch"
            else example
        )


async def synthesize(text: str, short_name: str) -> bytes:
    communicate = edge_tts.Communicate(text, short_name)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    if not chunks:
        raise HTTPException(500, "TTS leer")
    return b"".join(chunks)


@app.get("/")
def index():
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Voice Demo</h1><p>web/index.html fehlt</p>")


if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

PREVIEWS_DIR = CATALOG_DIR / "previews"
if PREVIEWS_DIR.is_dir():
    app.mount("/previews", StaticFiles(directory=str(PREVIEWS_DIR)), name="previews")

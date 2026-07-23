# -*- coding: utf-8 -*-
"""Jay (Jarvis): Retell Web-Call Session + Stimmen/Persönlichkeit-Katalog."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
META_PATHS = (
    Path("/root/app/agency/jay_retell.json"),
    ROOT / "agency" / "jay_retell.json",
)
USAGE_PATHS = (
    Path("/root/app/agency/jay_usage.json"),
    ROOT / "agency" / "jay_usage.json",
)

# Kosten-Barrieren (typisches Gespräch 2–3 Min.)
DEFAULT_MAX_CALL_SECONDS = 180  # 3 Min. hartes Retell-Limit
DEFAULT_DAILY_MAX_SECONDS = 1800  # 30 Min./Tag Budget
DEFAULT_SILENCE_END_MS = 45_000  # 45 Sek. Stille → Ende
DEFAULT_SESSIONS_PER_HOUR = 6

_usage_lock = threading.Lock()

# Christian = Default. Weitere Retell-Stimmen (DE wo möglich).
VOICES = [
    {
        "id": "christian",
        "label": "Christian (klar, authentisch)",
        "voice_id": "custom_voice_776939a71c0c6cbfdda7f5ac61",
        "tag": "Standard",
        "premium": True,
    },
    {
        "id": "max",
        "label": "Max (männlich, DE)",
        "voice_id": "minimax-Max",
        "tag": "Deutsch",
    },
    {
        "id": "carola",
        "label": "Carola (weiblich, DE)",
        "voice_id": "11labs-Carola",
        "tag": "Deutsch",
    },
    {
        "id": "eva",
        "label": "Eva (weiblich, DE)",
        "voice_id": "cartesia-Eva",
        "tag": "Deutsch",
    },
    {
        "id": "lina",
        "label": "Lina (weiblich, DE)",
        "voice_id": "cartesia-Lina",
        "tag": "Deutsch",
    },
    {
        "id": "nico",
        "label": "Nico (international)",
        "voice_id": "retell-Nico",
        "tag": "Intl",
    },
]

PERSONALITIES = [
    {
        "id": "kollege",
        "label": "Kollege Jay",
        "prompt": (
            "Du bist Jay, Christians direkter Kollege. Duzen. Sparring-Partner: "
            "hörst zu, fragst nach, denkst mit, fass am Ende zusammen."
        ),
    },
    {
        "id": "sparring",
        "label": "Sparring (kritisch)",
        "prompt": (
            "Du bist Jay im Sparring-Modus: freundlich, aber du hinterfragst Annahmen, "
            "zeigst Risiken und fragst nach Zahlen und Priorität."
        ),
    },
    {
        "id": "verkauf",
        "label": "Verkauf / Angebot",
        "prompt": (
            "Du hilfst Christian beim Verkauf: Branche, Schmerz, Paket, Preisrahmen, "
            "nächster Schritt. Frag gezielt, was für ein Angebot fehlt."
        ),
    },
    {
        "id": "technik",
        "label": "Technik / Ops",
        "prompt": (
            "Du bist Jay als Ops: Deploy, Server, Domains, Nils, Watchdogs, Portale. "
            "Konkret, kurz, nächster Check."
        ),
    },
    {
        "id": "ruhig",
        "label": "Ruhig / zuhören",
        "prompt": (
            "Du bist Jay, sehr ruhig. Mehr zuhören, wenig reden, nur gezielte Rückfragen, "
            "dann eine klare Zusammenfassung."
        ),
    },
]

STYLES = [
    {"id": "freundlich", "label": "Freundlich (Hochdeutsch)", "prompt": "Hochdeutsch, warm, klar."},
    {"id": "sachlich", "label": "Sachlich (Hochdeutsch)", "prompt": "Hochdeutsch, knapp, nüchtern."},
    {"id": "rheinland", "label": "Rheinland (leicht)", "prompt": "Leichter rheinischer Touch im Wortlaut, trotzdem verständlich."},
    {"id": "koelsch", "label": "Kölsch", "prompt": "Kölscher Wortlaut, lockerer Ton, nicht übertreiben."},
    {"id": "bayrisch", "label": "Bayrisch", "prompt": "Leicht bayrischer Wortlaut."},
    {"id": "berlinerisch", "label": "Berlinerisch", "prompt": "Leicht berlinerischer Wortlaut."},
    {"id": "oesterreichisch", "label": "Österreichisch", "prompt": "Österreichischer Wortlaut (Grüß Gott etc.)."},
    {"id": "schweizerdeutsch", "label": "Schweizerdeutsch (leicht)", "prompt": "Leichter Schweizer Touch im Wortlaut."},
]


def _secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in (
        Path(os.getenv("DEPLOY_SECRETS_PATH", "/root/app/deploy.secrets.local")),
        ROOT / "deploy.secrets.local",
    ):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            out.setdefault(k.strip(), v.strip())
    if os.getenv("RETELL_API_KEY"):
        out["RETELL_API_KEY"] = os.getenv("RETELL_API_KEY", "")
    return out


def retell_key() -> str:
    return (_secrets().get("RETELL_API_KEY") or "").strip()


def _int_secret(name: str, default: int, *, minimum: int = 1) -> int:
    raw = (_secrets().get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def limits() -> dict[str, int]:
    return {
        "max_call_seconds": _int_secret(
            "JAY_MAX_CALL_SECONDS", DEFAULT_MAX_CALL_SECONDS, minimum=60
        ),
        "daily_max_seconds": _int_secret(
            "JAY_DAILY_MAX_SECONDS", DEFAULT_DAILY_MAX_SECONDS, minimum=60
        ),
        "silence_end_ms": min(
            600_000,
            max(
                10_000,
                _int_secret("JAY_SILENCE_END_MS", DEFAULT_SILENCE_END_MS, minimum=10_000),
            ),
        ),
        "sessions_per_hour": min(
            30,
            max(1, _int_secret("JAY_SESSIONS_PER_HOUR", DEFAULT_SESSIONS_PER_HOUR, minimum=1)),
        ),
    }


def _usage_path() -> Path:
    for p in USAGE_PATHS:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            continue
    return USAGE_PATHS[-1]


def _load_usage() -> dict[str, Any]:
    path = _usage_path()
    today = date.today().isoformat()
    empty = {"date": today, "seconds_reserved": 0, "sessions": 0, "hour_buckets": {}}
    if not path.is_file():
        return empty
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return empty
    if data.get("date") != today:
        return empty
    data.setdefault("seconds_reserved", 0)
    data.setdefault("sessions", 0)
    data.setdefault("hour_buckets", {})
    return data


def _save_usage(data: dict[str, Any]) -> None:
    path = _usage_path()
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def usage_snapshot() -> dict[str, Any]:
    lim = limits()
    with _usage_lock:
        u = _load_usage()
        used = int(u.get("seconds_reserved") or 0)
        remaining = max(0, lim["daily_max_seconds"] - used)
        return {
            "date": u.get("date"),
            "seconds_used_or_reserved": used,
            "seconds_remaining_today": remaining,
            "sessions_today": int(u.get("sessions") or 0),
            "max_call_seconds": lim["max_call_seconds"],
            "daily_max_seconds": lim["daily_max_seconds"],
            "approx_cost_hint": "ca. 0,15–0,20 $/Min. (Retell)",
        }


def _can_start(call_seconds: int) -> dict[str, Any] | None:
    """Prüft Budget ohne zu buchen. None = ok, sonst Fehler-dict."""
    lim = limits()
    hour_key = str(int(time.time() // 3600))
    with _usage_lock:
        u = _load_usage()
        buckets = u.get("hour_buckets") or {}
        hour_count = int(buckets.get(hour_key) or 0)
        if hour_count >= lim["sessions_per_hour"]:
            return {
                "ok": False,
                "error": (
                    f"Stunden-Limit: max. {lim['sessions_per_hour']} Jay-Gespräche "
                    "pro Stunde. Kurz warten."
                ),
            }
        used = int(u.get("seconds_reserved") or 0)
        if used + call_seconds > lim["daily_max_seconds"]:
            left = max(0, lim["daily_max_seconds"] - used)
            return {
                "ok": False,
                "error": (
                    f"Tages-Budget aufgebraucht ({lim['daily_max_seconds'] // 60} Min./Tag). "
                    f"Noch ca. {left // 60} Min. frei. Morgen weiter oder Limit in Secrets erhöhen "
                    "(JAY_DAILY_MAX_SECONDS)."
                ),
            }
    return None


def _reserve_budget(call_seconds: int) -> None:
    """Reserviert Tagesbudget nach erfolgreichem Retell-Create."""
    hour_key = str(int(time.time() // 3600))
    with _usage_lock:
        u = _load_usage()
        buckets = u.get("hour_buckets") or {}
        hour_count = int(buckets.get(hour_key) or 0)
        u["seconds_reserved"] = int(u.get("seconds_reserved") or 0) + call_seconds
        u["sessions"] = int(u.get("sessions") or 0) + 1
        u["hour_buckets"] = {hour_key: hour_count + 1}
        _save_usage(u)

def load_meta() -> dict[str, Any]:
    for p in META_PATHS:
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    # Fallback Demo-Agent (nicht ideal, aber startfähig)
    for p in (Path("/root/app/agency/retell_demo.json"), ROOT / "agency" / "retell_demo.json"):
        if p.is_file():
            d = json.loads(p.read_text(encoding="utf-8"))
            return {
                "agent_id": d.get("agent_id"),
                "voice_id": d.get("voice_id"),
                "voice_name": d.get("voice_name"),
                "name": "Jay",
            }
    return {}


def catalog() -> dict[str, Any]:
    meta = load_meta()
    voices = list(VOICES)
    # sync christian voice id from meta if present
    for v in voices:
        if v["id"] == "christian" and meta.get("voice_id"):
            v["voice_id"] = meta["voice_id"]
            v["label"] = f"{meta.get('voice_name') or 'Christian'} (klar, authentisch)"
    snap = usage_snapshot()
    lim = limits()
    return {
        "default_voice": "christian",
        "default_personality": "kollege",
        "default_style": "freundlich",
        "voices": voices,
        "personalities": [{"id": p["id"], "label": p["label"]} for p in PERSONALITIES],
        "styles": [{"id": s["id"], "label": s["label"]} for s in STYLES],
        "agent_ready": bool(meta.get("agent_id")),
        "limits": {
            "max_call_seconds": lim["max_call_seconds"],
            "daily_max_seconds": lim["daily_max_seconds"],
            "silence_end_ms": lim["silence_end_ms"],
            "sessions_per_hour": lim["sessions_per_hour"],
            "require_cost_confirm": True,
        },
        "usage": snap,
        "cost_warning": (
            f"Retell kostet Minuten (ca. 0,15–0,20 $/Min.). "
            f"Max. {lim['max_call_seconds'] // 60} Min. pro Gespräch, "
            f"{lim['daily_max_seconds'] // 60} Min. pro Tag."
        ),
    }


def _pick(items: list[dict], id_: str, default_id: str) -> dict:
    for it in items:
        if it["id"] == id_:
            return it
    for it in items:
        if it["id"] == default_id:
            return it
    return items[0]


def _retell(method: str, path: str, key: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.retellai.com{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw[:400]}
        raise RuntimeError(parsed.get("message") or parsed.get("error") or raw[:300] or str(e)) from e


def create_session(
    *,
    voice: str = "christian",
    personality: str = "kollege",
    style: str = "freundlich",
    confirm_cost: bool = False,
) -> dict[str, Any]:
    if not confirm_cost:
        return {
            "ok": False,
            "error": "Kosten-Hinweis bestätigen (Haken setzen), sonst startet kein Gespräch.",
        }

    key = retell_key()
    if not key:
        return {"ok": False, "error": "RETELL_API_KEY fehlt in den Secrets."}

    lim = limits()
    blocked = _can_start(lim["max_call_seconds"])
    if blocked:
        return blocked

    meta = load_meta()
    agent_id = meta.get("agent_id")
    if not agent_id:
        return {
            "ok": False,
            "error": "Jay-Agent fehlt. Einmal: python scripts/setup_jay_retell.py",
        }

    v = _pick(VOICES, voice, "christian")
    p = _pick(PERSONALITIES, personality, "kollege")
    s = _pick(STYLES, style, "freundlich")
    if v["id"] == "christian" and meta.get("voice_id"):
        v = {**v, "voice_id": meta["voice_id"]}

    max_ms = lim["max_call_seconds"] * 1000
    # Retell: min 60s, max 2h
    max_ms = max(60_000, min(7_200_000, max_ms))

    body = {
        "agent_id": agent_id,
        "metadata": {
            "product": "jay",
            "voice": v["id"],
            "personality": p["id"],
            "style": s["id"],
            "max_call_seconds": lim["max_call_seconds"],
        },
        "retell_llm_dynamic_variables": {
            "jay_personality": p["prompt"],
            "jay_style": s["prompt"],
        },
        "agent_override": {
            "agent": {
                "voice_id": v["voice_id"],
                "language": "de-DE",
                "max_call_duration_ms": max_ms,
                "end_call_after_silence_ms": lim["silence_end_ms"],
            },
            "retell_llm": {
                "begin_message": (
                    "Hey Christian, hier ist Jay. Kurz und klar, "
                    f"wir haben etwa {lim['max_call_seconds'] // 60} Minuten. Woran arbeiten wir?"
                ),
                "model_temperature": 0.55,
            },
        },
    }

    try:
        created = _retell("POST", "/v2/create-web-call", key, body)
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    _reserve_budget(lim["max_call_seconds"])
    snap = usage_snapshot()
    return {
        "ok": True,
        "access_token": created.get("access_token"),
        "call_id": created.get("call_id"),
        "voice": v["id"],
        "personality": p["id"],
        "style": s["id"],
        "voice_label": v["label"],
        "max_call_seconds": lim["max_call_seconds"],
        "usage": snap,
    }

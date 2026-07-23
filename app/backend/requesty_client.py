# -*- coding: utf-8 -*-
"""Requesty Gateway: Modellkatalog + Chat/Bild über PRIMARY_* Keys."""
from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path
from typing import Any

import llm_client as llm

_CACHE: dict[str, Any] = {"ts": 0.0, "models": []}
_CACHE_TTL = 3600.0
_USAGE_CACHE: dict[str, Any] = {"usage_ts": 0.0, "key_ts": 0.0, "usage": None, "key": None}
_USAGE_TTL = 90.0  # Budget-Checks nicht vor jedem Chat neu abfragen (Latenz!)

# Bevorzugte Defaults (Requesty EU: provider/model)
DEFAULT_CHAT = "nebius/meta-llama/Llama-3.3-70B-Instruct"
DEFAULT_SMART = "bedrock/claude-sonnet-4@eu-central-1"
DEFAULT_VISION = "azure/gpt-4o-mini@swedencentral"
DEFAULT_IMAGE = "azure/openai/gpt-image-1"
DEFAULT_IMAGE_FALLBACKS = (
    "azure/openai/gpt-image-1",
    "azure/openai/gpt-image-1.5",
)

IMAGE_INTENT_RE = re.compile(
    r"\b("
    r"logo|bild|bilder|flyer|poster|banner|mockup|cover|thumbnail|"
    r"instagram|insta[\s-]?post|story|stories|carousel|"
    r"generier|erstell|zeichn|design|visual|grafik|"
    r"image|picture|generate\s+image"
    r")\b",
    re.I,
)
# Nur bei klarem Absicht erzeugen (sonst kostet jedes „Logo-Thema“ Geld)
# Default: Auto-Bilder AUS. Explizit: „generiere jetzt bild/logo…“ oder NILS_IMAGE_AUTO=1
EXPLICIT_IMAGE_RE = re.compile(
    r"(?:"
    r"generier\w*\s+jetzt\b.{0,40}\b(bild|logo|flyer|banner|mockup|instagram|posting)\b|"
    r"\b(mach|erstell|zeichn)\w*\s+jetzt\b.{0,30}\b(ein|eine|mir|das|den)?\s*(bild|logo|flyer|banner|mockup)\b|"
    r"\bbild\s*:\s*.{3,}|"
    r"\blogo\s*:\s*.{3,}|"
    r"generate\s+now\s+(an?\s+)?(image|logo|flyer)"
    r")",
    re.I,
)
IDEA_ONLY_RE = re.compile(
    r"\b("
    r"idee|ideen|sammeln|brain.?storm|konzept|erstmal|zuerst|"
    r"nur\s+text|kein\s+bild|noch\s+nicht\s+(zeichnen|generier|erzeug)|"
    r"vorschl[aä]ge|skizzier"
    r")\b",
    re.I,
)
VIDEO_INTENT_RE = re.compile(
    r"\b(video|reel|reels|tiktok|short[\s-]?film|runway|sora|kling)\b",
    re.I,
)


def configured() -> bool:
    return bool(llm.primary_api_key() and llm.primary_gateway_url())


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {llm.primary_api_key()}",
        "Content-Type": "application/json",
    }


def base_url() -> str:
    return llm.primary_gateway_url().rstrip("/")


def list_models(*, force: bool = False) -> list[dict[str, Any]]:
    """GET /v1/models, gecacht. Keine Secrets."""
    now = time.time()
    if not force and _CACHE["models"] and (now - float(_CACHE["ts"])) < _CACHE_TTL:
        return list(_CACHE["models"])
    if not configured():
        return []
    import requests

    try:
        r = requests.get(f"{base_url()}/models", headers=_headers(), timeout=45)
        if not r.ok:
            return list(_CACHE["models"] or [])
        data = r.json() if r.content else {}
        models = data.get("data") or data.get("models") or []
        if isinstance(models, list):
            _CACHE["models"] = models
            _CACHE["ts"] = now
            return list(models)
    except Exception:
        pass
    return list(_CACHE["models"] or [])


def catalog_summary() -> dict[str, Any]:
    models = list_models()
    providers: dict[str, int] = {}
    vision = image_gen = reasoning = tools = 0
    for m in models:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id") or "")
        if "/" in mid:
            providers[mid.split("/", 1)[0]] = providers.get(mid.split("/", 1)[0], 0) + 1
        if m.get("supports_vision"):
            vision += 1
        if m.get("supports_image_generation"):
            image_gen += 1
        if m.get("supports_reasoning"):
            reasoning += 1
        if m.get("supports_tool_calling"):
            tools += 1
    return {
        "ok": configured(),
        "count": len(models),
        "providers": dict(sorted(providers.items(), key=lambda x: -x[1])[:25]),
        "supports_vision": vision,
        "supports_image_generation": image_gen,
        "supports_reasoning": reasoning,
        "supports_tool_calling": tools,
        "defaults": {
            "chat": pick_model("chat"),
            "smart": pick_model("smart"),
            "vision": pick_model("vision"),
            "image": pick_model("image"),
        },
        "limits": {
            "video_generation": False,
            "note": (
                "Requesty: Chat, Vision, Bild-Generierung, Embeddings, Audio. "
                "Keine Video-Produktion über diesen Gateway."
            ),
        },
    }


def pick_model(kind: str) -> str:
    """Wählt ein Modell für die Aufgabe. Env überschreibt."""
    kind = (kind or "chat").lower().strip()
    env_map = {
        "chat": "REQUESTY_CHAT_MODEL",
        "smart": "REQUESTY_SMART_MODEL",
        "vision": "REQUESTY_VISION_MODEL",
        "image": "REQUESTY_IMAGE_MODEL",
    }
    env_key = env_map.get(kind)
    if env_key:
        override = llm._env(env_key)
        if override:
            return override
    if kind == "chat":
        return llm.primary_default_model() or DEFAULT_CHAT
    if kind == "smart":
        return _first_available(
            [DEFAULT_SMART, "anthropic/claude-sonnet-4-20250514", "openai/gpt-4o", DEFAULT_CHAT]
        )
    if kind == "vision":
        return _first_available([DEFAULT_VISION, "openai/gpt-4o-mini", DEFAULT_CHAT])
    if kind == "image":
        return llm._env("REQUESTY_IMAGE_MODEL") or DEFAULT_IMAGE
    return DEFAULT_CHAT


def _first_available(candidates: list[str]) -> str:
    ids = {str(m.get("id") or "") for m in list_models() if isinstance(m, dict)}
    if not ids:
        return candidates[0]
    for c in candidates:
        if c in ids:
            return c
    # Prefix match (version suffixes)
    for c in candidates:
        for mid in ids:
            if mid.startswith(c) or c.startswith(mid.split("@")[0]):
                return mid
    return candidates[0]


def usage_today(*, force: bool = False) -> dict[str, Any]:
    """Tagesverbrauch vom Requesty Management-API (ohne Secrets). Gecacht."""
    import time

    now = time.time()
    if (
        not force
        and _USAGE_CACHE.get("usage")
        and (now - float(_USAGE_CACHE.get("usage_ts") or 0)) < _USAGE_TTL
    ):
        return dict(_USAGE_CACHE["usage"])

    if not configured():
        return {"ok": False, "error": "not_configured"}
    import requests
    from datetime import datetime, timezone

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            "https://api-v2.requesty.ai/v1/manage/apikey/self/usage",
            headers=_headers(),
            json={
                "start": f"{day}T00:00:00Z",
                "end": f"{day}T23:59:59Z",
            },
            timeout=8,
        )
        if not r.ok:
            return {"ok": False, "error": f"http_{r.status_code}"}
        usage = (r.json() or {}).get("usage") or {}
        bucket = usage.get(day) or next(iter(usage.values()), {}) if usage else {}
        spend = float(bucket.get("spend") or 0)
        out = {
            "ok": True,
            "day": day,
            "spend": spend,
            "completions": int(bucket.get("completions_requests") or 0),
            "images": int(bucket.get("image_requests") or 0),
            "transcriptions": int(bucket.get("transcription_requests") or 0),
            "total_requests": int(bucket.get("total_requests") or 0),
            "input_tokens": int(bucket.get("input_tokens") or 0),
            "output_tokens": int(bucket.get("output_tokens") or 0),
            "raw": bucket,
        }
        _USAGE_CACHE["usage"] = out
        _USAGE_CACHE["usage_ts"] = now
        return dict(out)
    except Exception as e:
        cached = _USAGE_CACHE.get("usage")
        if cached:
            return dict(cached)
        return {"ok": False, "error": f"{type(e).__name__}"}


def key_info(*, force: bool = False) -> dict[str, Any]:
    import time

    now = time.time()
    if (
        not force
        and _USAGE_CACHE.get("key")
        and (now - float(_USAGE_CACHE.get("key_ts") or 0)) < _USAGE_TTL
    ):
        return dict(_USAGE_CACHE["key"])

    if not configured():
        return {"ok": False}
    import requests

    try:
        r = requests.get(
            "https://api-v2.requesty.ai/v1/manage/apikey/self",
            headers=_headers(),
            timeout=8,
        )
        if not r.ok:
            return {"ok": False, "error": f"http_{r.status_code}"}
        data = r.json() or {}
        out = {
            "ok": True,
            "name": data.get("name"),
            "monthly_spend": float(data.get("monthly_spend") or 0),
            "monthly_limit": float(data.get("monthly_limit") or 0),
        }
        _USAGE_CACHE["key"] = out
        _USAGE_CACHE["key_ts"] = now
        return dict(out)
    except Exception as e:
        cached = _USAGE_CACHE.get("key")
        if cached:
            return dict(cached)
        return {"ok": False, "error": type(e).__name__}


def budget_guard(*, kind: str = "chat") -> dict[str, Any]:
    """Soft/Hard-Limit. Tages-Spend, Monats-Spend, Bilder/Tag.

    Chat: standardmäßig kein Netzwerk-Roundtrip (nur Cache). Bilder: immer prüfen.
    """
    try:
        daily = float(llm._env("NILS_REQUESTY_DAILY_BUDGET", "8") or 8)
    except Exception:
        daily = 8.0
    try:
        monthly = float(llm._env("NILS_REQUESTY_MONTHLY_BUDGET", "20") or 20)
    except Exception:
        monthly = 20.0
    try:
        max_images = int(float(llm._env("NILS_IMAGE_MAX_PER_DAY", "5") or 5))
    except Exception:
        max_images = 5

    # Chat-Hotpath: Budget-API nicht vor jedem Telegram-Call (macht ~600ms+)
    chat_guard = llm._env("NILS_BUDGET_GUARD_CHAT", "0") not in ("0", "false", "no")
    if kind == "chat" and not chat_guard:
        # Nur Cache lesen, nie frisch fetchen
        import time

        info = _USAGE_CACHE.get("key") or {}
        usage = _USAGE_CACHE.get("usage") or {}
        month_spend = float(info.get("monthly_spend") or 0) if info.get("ok") else None
        if monthly > 0 and month_spend is not None and month_spend >= monthly:
            return {
                "ok": False,
                "error": "monthly_budget_exceeded",
                "spend": month_spend,
                "limit": monthly,
                "period": "month",
            }
        spend = float(usage.get("spend") or 0) if usage.get("ok") else 0.0
        if daily > 0 and usage.get("ok") and spend >= daily:
            return {"ok": False, "error": "budget_exceeded", "spend": spend, "limit": daily, "period": "day"}
        return {"ok": True, "skipped_network": True, "spend": spend or None, "monthly_spend": month_spend}

    info = key_info()
    month_spend = float(info.get("monthly_spend") or 0) if info.get("ok") else None
    if monthly > 0 and month_spend is not None and month_spend >= monthly:
        return {
            "ok": False,
            "error": "monthly_budget_exceeded",
            "spend": month_spend,
            "limit": monthly,
            "period": "month",
            "hint": f"Monats-Limit ${monthly:.0f} erreicht (${month_spend:.2f}).",
        }

    u = usage_today()
    if not u.get("ok"):
        if kind == "image":
            return {"ok": False, "error": "budget_unknown", "detail": u.get("error")}
        return {"ok": True, "usage_unknown": True, "monthly_spend": month_spend, "monthly_limit": monthly}

    spend = float(u.get("spend") or 0)
    images = int(u.get("images") or 0)

    if daily > 0 and spend >= daily:
        return {
            "ok": False,
            "error": "budget_exceeded",
            "spend": spend,
            "limit": daily,
            "period": "day",
            "images": images,
            "completions": u.get("completions"),
            "monthly_spend": month_spend,
        }

    if kind == "image" and max_images > 0 and images >= max_images:
        return {
            "ok": False,
            "error": "budget_exceeded",
            "spend": spend,
            "limit": daily,
            "period": "day",
            "images": images,
            "image_limit": max_images,
            "completions": u.get("completions"),
            "hint": f"Heute schon {images} Bilder (Max {max_images}).",
            "monthly_spend": month_spend,
        }

    return {
        "ok": True,
        "spend": spend,
        "limit": daily,
        "period": "day",
        "images": images,
        "image_limit": max_images,
        "monthly_spend": month_spend,
        "monthly_limit": monthly,
        "remaining": round(max(0.0, daily - spend), 4) if daily > 0 else None,
        "remaining_month": round(max(0.0, monthly - (month_spend or 0)), 4) if monthly > 0 else None,
    }


# Grobe Requesty-/Provider-Schätzungen (USD), damit Christian vorher Ja sagen kann.
# Keine Garantie, nur Schutz vor Überraschung.
COST_CATALOG: dict[str, dict[str, Any]] = {
    "chat_fast": {
        "label": "Schneller Chat (Mistral / Llama / gpt-4o-mini)",
        "usd_min": 0.0001,
        "usd_max": 0.01,
        "paid": False,
        "note": "Standard. Billigste brauchbare Modelle zuerst.",
    },
    "chat_smart": {
        "label": "Schwerer Chat (Claude Sonnet o.ä.)",
        "usd_min": 0.01,
        "usd_max": 0.08,
        "paid": True,
        "note": "Nur Route B (komplexe Analyse).",
    },
    "image": {
        "label": "Bild / Logo (gpt-image)",
        "usd_min": 0.04,
        "usd_max": 0.15,
        "paid": True,
        "model": DEFAULT_IMAGE,
        "note": "Kostet echt Geld. Nur nach Freigabe.",
    },
    "vision": {
        "label": "Bild verstehen (Vision)",
        "usd_min": 0.005,
        "usd_max": 0.04,
        "paid": True,
        "note": "Wenn du ein Foto schickst und Analyse brauchst.",
    },
    "video": {
        "label": "Video erzeugen",
        "usd_min": None,
        "usd_max": None,
        "paid": True,
        "unsupported": True,
        "note": "Über Requesty bei uns nicht verfügbar. Kein Auto-Kauf.",
    },
}


def paid_media_confirm_required() -> bool:
    """Default AN: bezahlte Media-Jobs brauchen Christians OK."""
    return llm._env("NILS_PAID_MEDIA_CONFIRM", "1") not in ("0", "false", "no")


def estimate_media_job(kind: str = "image") -> dict[str, Any]:
    cat = COST_CATALOG.get(kind) or COST_CATALOG["image"]
    guard = budget_guard(kind="image" if kind == "image" else "chat")
    out = {
        "ok": True,
        "kind": kind,
        "label": cat.get("label"),
        "usd_min": cat.get("usd_min"),
        "usd_max": cat.get("usd_max"),
        "model": cat.get("model") or pick_model("image" if kind == "image" else "chat"),
        "paid": bool(cat.get("paid")),
        "unsupported": bool(cat.get("unsupported")),
        "note": cat.get("note") or "",
        "budget": {
            "ok": guard.get("ok"),
            "spend_today": guard.get("spend"),
            "daily_limit": guard.get("limit"),
            "remaining_today": guard.get("remaining"),
            "monthly_spend": guard.get("monthly_spend"),
            "monthly_limit": guard.get("monthly_limit"),
            "remaining_month": guard.get("remaining_month"),
            "images_today": guard.get("images"),
            "image_limit": guard.get("image_limit"),
            "error": guard.get("error"),
            "hint": guard.get("hint"),
        },
    }
    return out


def format_cost_quote(est: dict[str, Any]) -> str:
    """Menschlicher Kostenvoranschlag für Telegram/Portal."""
    if est.get("unsupported"):
        return (
            "Video erzeugen geht über Requesty bei uns noch nicht. "
            "Kein automatischer Kauf. Wenn du ein Standbild willst: "
            "„generiere jetzt ein Logo …“."
        )
    b = est.get("budget") or {}
    if not b.get("ok") and b.get("error"):
        hint = b.get("hint") or b.get("error")
        return (
            f"Stopp, Budget-Bremse: {hint}. "
            "Chat geht weiter, bezahlte Bilder erst wenn Limit frei ist."
        )
    lo, hi = est.get("usd_min"), est.get("usd_max")
    price = f"ca. ${lo:.2f}–${hi:.2f}" if lo is not None and hi is not None else "Kosten unbekannt"
    lines = [
        f"Bevor ich das starte: {est.get('label') or 'bezahlter Job'}.",
        f"Schätzung {price} (Modell {est.get('model') or '?'}).",
    ]
    if b.get("spend_today") is not None and b.get("daily_limit"):
        lines.append(
            f"Heute schon ca. ${float(b['spend_today']):.2f} von ${float(b['daily_limit']):.0f}."
        )
    if b.get("monthly_spend") is not None and b.get("monthly_limit"):
        lines.append(
            f"Monat ca. ${float(b['monthly_spend']):.2f} von ${float(b['monthly_limit']):.0f}."
        )
    if b.get("images_today") is not None and b.get("image_limit"):
        lines.append(f"Bilder heute: {b['images_today']} / {b['image_limit']}.")
    lines.append("Soll ich das machen? Antworte ja oder abbrechen.")
    return " ".join(lines)


def spend_status_text() -> str:
    """Kurzstatus für „budget“ / „kosten“."""
    guard = budget_guard(kind="image")
    if guard.get("error") == "budget_unknown" or (
        not guard.get("ok") and guard.get("error") not in ("budget_exceeded", "monthly_budget_exceeded")
        and guard.get("spend") is None and guard.get("monthly_spend") is None
    ):
        # Nochmal mit Chat-Pfad falls image blockt wegen unknown
        guard = budget_guard(kind="chat") if not guard.get("skipped_network") else guard
    spend = guard.get("spend")
    daily = guard.get("limit")
    month = guard.get("monthly_spend")
    mlim = guard.get("monthly_limit")
    imgs = guard.get("images")
    ilim = guard.get("image_limit")
    parts = ["Requesty-Budget:"]
    if spend is not None and daily:
        parts.append(f"heute ca. ${float(spend):.2f} / ${float(daily):.0f}.")
    elif spend is not None:
        parts.append(f"heute ca. ${float(spend):.2f}.")
    else:
        parts.append("Tages-Spend gerade nicht lesbar (Cache).")
    if month is not None and mlim:
        parts.append(f"Monat ca. ${float(month):.2f} / ${float(mlim):.0f}.")
    if imgs is not None and ilim:
        parts.append(f"Bilder {imgs}/{ilim}.")
    parts.append("Chat nutzt zuerst die günstigen Modelle. Bilder nur nach Freigabe.")
    return " ".join(parts)


def classify_creative(text: str) -> str:
    """text | image | video_unsupported

    Auto-Bilder sind standardmäßig aus. Ideen sammeln = immer Text.
    Bild nur mit „… jetzt … bild/logo“ oder Prefixe „bild:“ / „logo:“.
    """
    t = (text or "").strip()
    if not t:
        return "text"
    if IDEA_ONLY_RE.search(t) and not re.search(r"\bjetzt\b", t, re.I):
        return "text"
    if VIDEO_INTENT_RE.search(t):
        return "video_unsupported"
    auto = llm._env("NILS_IMAGE_AUTO", "0") not in ("0", "false", "no")
    if EXPLICIT_IMAGE_RE.search(t):
        return "image"
    if auto and IMAGE_INTENT_RE.search(t):
        # Alter lockerer Modus nur wenn bewusst angeschaltet
        low = t.lower()
        if any(w in low for w in ("mach", "erstell", "generier", "zeichn")):
            return "image"
    return "text"


def generate_image(
    prompt: str,
    *,
    model: str | None = None,
    size: str = "1024x1024",
    quality: str = "auto",
    timeout: float = 120,
) -> dict[str, Any]:
    """POST /v1/images/generations → {ok, path?, b64?, model, error?}"""
    if not configured():
        return {"ok": False, "error": "requesty_not_configured"}
    if llm._env("NILS_IMAGE_ENABLED", "1") in ("0", "false", "no"):
        return {"ok": False, "error": "image_disabled"}
    guard = budget_guard(kind="image")
    if not guard.get("ok"):
        return {
            "ok": False,
            "error": guard.get("error") or "budget_block",
            "spend": guard.get("spend"),
            "limit": guard.get("limit"),
        }
    prompt = (prompt or "").strip()
    if len(prompt) < 3:
        return {"ok": False, "error": "prompt_empty"}

    import requests

    chain = []
    preferred = (model or pick_model("image")).strip()
    if preferred:
        chain.append(preferred)
    for m in DEFAULT_IMAGE_FALLBACKS:
        if m not in chain:
            chain.append(m)

    last_err = "image_fail"
    for mid in chain:
        try:
            r = requests.post(
                f"{base_url()}/images/generations",
                headers=_headers(),
                json={
                    "model": mid,
                    "prompt": prompt[:4000],
                    "n": 1,
                    "size": size,
                    "quality": quality,
                    "response_format": "b64_json",
                },
                timeout=timeout,
            )
            if not r.ok:
                last_err = f"http_{r.status_code}:{(r.text or '')[:180]}"
                continue
            data = r.json() if r.content else {}
            item = (data.get("data") or [{}])[0]
            b64 = item.get("b64_json") or ""
            url = item.get("url") or ""
            if not b64 and url:
                ir = requests.get(url, timeout=60)
                if ir.ok:
                    b64 = base64.b64encode(ir.content).decode("ascii")
            if not b64:
                last_err = "empty_image"
                continue
            return {
                "ok": True,
                "b64": b64,
                "model": mid,
                "provider": "primary",
                "size": size,
                "revised_prompt": item.get("revised_prompt"),
                "budget": guard,
            }
        except Exception as e:
            last_err = f"exception:{type(e).__name__}"
            continue
    return {"ok": False, "error": last_err}


def save_image_b64(b64: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(b64)
    dest.write_bytes(raw)
    return dest


def vision_describe(
    image_path: str,
    *,
    prompt: str | None = None,
    timeout: float = 60,
) -> dict[str, Any]:
    """Bildanalyse über Requesty Vision-Modell."""
    if not configured():
        return {"ok": False, "error": "requesty_not_configured", "text": ""}
    p = Path(image_path)
    if not p.is_file():
        return {"ok": False, "error": "file_missing", "text": ""}
    import mimetypes
    import requests

    mime = mimetypes.guess_type(str(p))[0] or "image/jpeg"
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    text = prompt or (
        "Beschreibe dieses Bild für einen Webschmiede-Auftrag: "
        "Branche, Betriebsname falls sichtbar, Stil, Logo, Texte. Kurz, Deutsch."
    )
    model = pick_model("vision")
    try:
        r = requests.post(
            f"{base_url()}/chat/completions",
            headers=_headers(),
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": text},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{b64}"},
                            },
                        ],
                    }
                ],
                "max_tokens": 500,
            },
            timeout=timeout,
        )
        if not r.ok:
            return {"ok": False, "error": f"http_{r.status_code}", "text": "", "model": model}
        content = (
            ((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        ).strip()
        if not content:
            return {"ok": False, "error": "empty", "text": "", "model": model}
        return {"ok": True, "text": content, "model": model, "provider": "primary"}
    except Exception as e:
        return {"ok": False, "error": f"exception:{type(e).__name__}", "text": ""}


def chat(
    messages: list[dict[str, Any]],
    *,
    kind: str = "chat",
    max_tokens: int = 800,
    temperature: float = 0.55,
    timeout: float = 90,
) -> dict[str, Any]:
    """Direkt Requesty-Chat mit gewähltem Modell (ohne Ollama-Vorrang)."""
    if not configured():
        return {"ok": False, "error": "requesty_not_configured"}
    model = pick_model(kind)
    return llm._chat_openai_compatible(
        messages,
        base_url=base_url(),
        key=llm.primary_api_key(),
        model=model,
        provider="primary",
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )

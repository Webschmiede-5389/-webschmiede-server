"""LLM-Client für Nils: Ollama (gratis) + optional OpenAI / Grok / Gemini.

Grok = xAI (nicht „Gronkh“). Bezahlte Keys nur nach Christians OK eintragen.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    root = Path(__file__).resolve().parents[2]
    for path in (
        Path(os.getenv("DEPLOY_SECRETS_PATH", "/root/app/deploy.secrets.local")),
        Path("/root/app/backend/.env"),
        Path("/root/app/requesty.secrets.local"),
        root / "deploy.secrets.local",
        root / "requesty.secrets.local",
    ):
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                out.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except Exception:
            continue
    return out


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or "").strip() or _secrets().get(key, "").strip() or default


def ollama_url() -> str:
    env = _env("OLLAMA_URL").rstrip("/")
    if env:
        return env
    auto = _env("AUTO_HOST")
    if auto:
        return f"http://{auto}:11434"
    return "http://127.0.0.1:11434"


def ollama_model() -> str:
    return _env("OLLAMA_MODEL", "qwen2.5:14b")


def openai_key() -> str:
    return _env("OPENAI_API_KEY") or _env("FALLBACK_OPENAI_KEY")


def openai_base_url() -> str:
    return (
        _env("FALLBACK_OPENAI_GATEWAY")
        or _env("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")


def openai_model() -> str:
    return _env("OPENAI_MODEL", "gpt-4o-mini")


def primary_gateway_url() -> str:
    """EU-Gateway (Requesty Frankfurt), OpenAI-kompatibel."""
    return (
        _env("PRIMARY_LLM_GATEWAY")
        or _env("REQUESTY_BASE_URL")
        or "https://router.eu.requesty.ai/v1"
    ).rstrip("/")


def primary_api_key() -> str:
    return _env("PRIMARY_API_KEY") or _env("REQUESTY_API_KEY")


def primary_default_model() -> str:
    # EU-Inference bevorzugen (Azure Sweden / Requesty EU)
    return _env("PRIMARY_LLM_MODEL", "azure/gpt-4o-mini@swedencentral")


def xai_key() -> str:
    return _env("XAI_API_KEY") or _env("GROK_API_KEY")


def xai_model() -> str:
    return _env("XAI_MODEL") or _env("GROK_MODEL") or "grok-2-latest"


def gemini_key() -> str:
    return _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")


def gemini_model() -> str:
    return _env("GEMINI_MODEL", "gemini-2.0-flash")


def voice_gateway_url() -> str:
    env = _env("VOICE_GATEWAY_URL").rstrip("/")
    if env:
        return env
    auto = _env("AUTO_HOST")
    if auto:
        return f"http://{auto}:8090"
    return "http://127.0.0.1:8090"


def provider_preference() -> str:
    """auto | ollama | primary | openai | grok | gemini | cloud | openrouter"""
    return (_env("LLM_PROVIDER") or "auto").lower()


def _provider_order() -> list[str]:
    pref = provider_preference()
    cloud = ["primary", "openrouter", "openai", "grok", "gemini"]
    if pref in ("openai", "grok", "gemini", "ollama", "openrouter", "primary"):
        rest = [p for p in (["ollama"] + cloud) if p != pref]
        return [pref] + rest
    if pref == "cloud":
        # Qualität zuerst (bezahlte Keys), Ollama nur Fallback
        return cloud + ["ollama"]
    # auto = kostenlos zuerst, dann Primary-Gateway, dann Rest
    return ["ollama"] + cloud


def openrouter_key() -> str:
    return _env("OPENROUTER_API_KEY")


def readiness() -> dict[str, Any]:
    import requests

    url = ollama_url()
    ollama_ok = False
    models: list[str] = []
    err = ""
    try:
        r = requests.get(f"{url}/api/tags", timeout=5)
        if r.ok:
            ollama_ok = True
            models = [m.get("name") or "" for m in (r.json().get("models") or []) if m.get("name")]
    except Exception as e:
        err = str(e)[:120]
    gw = voice_gateway_url()
    gw_ok = False
    try:
        r = requests.get(f"{gw}/api/health", timeout=4)
        gw_ok = r.ok
    except Exception:
        pass
    primary_ok = bool(primary_api_key() and primary_gateway_url())
    return {
        "ok": ollama_ok
        or primary_ok
        or bool(openai_key() or xai_key() or gemini_key() or openrouter_key()),
        "provider_preference": provider_preference(),
        "provider_order": _provider_order(),
        "ollama_url": url,
        "ollama_ok": ollama_ok,
        "ollama_model": ollama_model(),
        "ollama_models": models[:12],
        "primary_gateway": primary_gateway_url() or None,
        "primary_key": primary_ok,
        "primary_model": primary_default_model(),
        "openai_key": bool(openai_key()),
        "openai_base": openai_base_url(),
        "openai_model": openai_model(),
        "openrouter_key": bool(openrouter_key()),
        "xai_key": bool(xai_key()),
        "xai_model": xai_model(),
        "gemini_key": bool(gemini_key()),
        "gemini_model": gemini_model(),
        "voice_gateway_url": gw,
        "voice_gateway_ok": gw_ok,
        "ollama_error": err,
        "note": (
            "Gratis: Ollama zuerst. Primary = Requesty/EU-Gateway. "
            "Fallback OpenAI direkt. Cloud-Keys nur nach OK."
        ),
    }


def chat(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 800,
    temperature: float = 0.55,
    timeout: float = 90,
    route: str | None = None,
    use_dispatcher: bool | None = None,
) -> dict[str, Any]:
    """Chat completion. Returns {ok, reply, provider, model?, error?, route?}."""
    # Standard: Nils Dispatcher (A/B/C + Strip + Fallback). Abschalten: NILS_DISPATCHER=0
    if use_dispatcher is None:
        use_dispatcher = _env("NILS_DISPATCHER", "1") not in ("0", "false", "no")
    if use_dispatcher:
        try:
            import nils_dispatcher as disp

            return disp.dispatch(
                messages,
                route=route,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
            )
        except Exception as e:
            # Dispatcher kaputt → klassischer Fallback
            last_err = f"dispatcher:{type(e).__name__}"
    else:
        last_err = "no_provider"

    for name in _provider_order():
        if name == "ollama":
            result = _chat_ollama(messages, max_tokens=max_tokens, temperature=temperature, timeout=timeout)
        elif name == "primary":
            if not (primary_api_key() and primary_gateway_url()):
                continue
            result = _chat_openai_compatible(
                messages,
                base_url=primary_gateway_url(),
                key=primary_api_key(),
                model=primary_default_model(),
                provider="primary",
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
            )
        elif name == "openai":
            result = _chat_openai_compatible(
                messages,
                base_url=openai_base_url(),
                key=openai_key(),
                model=openai_model(),
                provider="openai",
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
            )
        elif name == "openrouter":
            if not openrouter_key():
                continue
            result = _chat_openai_compatible(
                messages,
                base_url="https://openrouter.ai/api/v1",
                key=openrouter_key(),
                model=_env("OPENROUTER_MODEL", "deepseek/deepseek-chat"),
                provider="openrouter",
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
            )
        elif name == "grok":
            result = _chat_openai_compatible(
                messages,
                base_url="https://api.x.ai/v1",
                key=xai_key(),
                model=xai_model(),
                provider="grok",
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
            )
        elif name == "gemini":
            result = _chat_openai_compatible(
                messages,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                key=gemini_key(),
                model=gemini_model(),
                provider="gemini",
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
            )
        else:
            continue
        if result.get("ok") and result.get("reply"):
            return result
        last_err = result.get("error") or last_err
    return {"ok": False, "reply": None, "provider": None, "error": last_err}


def transcribe_audio_file(path: str, *, language: str = "de") -> dict[str, Any]:
    """Sprachnachricht → Text.

    Standard: lokales Voice-Gateway zuerst (schnell). Requesty-STT nur als Fallback.
    Kein Budget-Roundtrip vor STT (Latenz).
    """
    import requests

    p = Path(path)
    if not p.is_file():
        return {"ok": False, "text": "", "error": "file_missing"}

    gw_err = ""
    # Cloud-STT oft langsam/404 → lokal zuerst, außer bewusst umgestellt
    cloud_first = _env("NILS_STT_CLOUD_FIRST", "0") not in ("0", "false", "no")

    def _primary_stt() -> dict[str, Any] | None:
        url = primary_gateway_url()
        key = primary_api_key()
        if not (url and key):
            return None
        model = _env("REQUESTY_STT_MODEL", "openai/whisper-1")
        try:
            with p.open("rb") as f:
                r = requests.post(
                    f"{url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {key}"},
                    files={"file": (p.name, f)},
                    data={"model": model, "language": language},
                    timeout=25,
                )
            if r.ok:
                text = (r.json().get("text") or "").strip()
                if text:
                    return {"ok": True, "text": text, "provider": "requesty_whisper", "model": model}
            return {"ok": False, "error": f"http_{r.status_code}", "provider": "requesty_whisper"}
        except Exception as e:
            return {"ok": False, "error": f"exception:{type(e).__name__}", "provider": "requesty_whisper"}

    def _gateway_stt() -> dict[str, Any] | None:
        nonlocal gw_err
        gw = voice_gateway_url()
        try:
            with p.open("rb") as f:
                r = requests.post(
                    f"{gw}/api/stt",
                    files={"audio": (p.name, f, "application/octet-stream")},
                    data={"language": language},
                    timeout=25,
                )
            if r.ok:
                data = r.json() if r.content else {}
                text = (data.get("text") or "").strip()
                if text and text != "(nichts verstanden)":
                    return {"ok": True, "text": text, "provider": "voice_gateway"}
                if text:
                    return {"ok": False, "text": "", "error": "empty_stt", "provider": "voice_gateway"}
            gw_err = f"http_{r.status_code}"
        except Exception as e:
            gw_err = f"{type(e).__name__}"
        return None

    order = [_primary_stt, _gateway_stt] if cloud_first else [_gateway_stt, _primary_stt]
    for fn in order:
        res = fn()
        if res and res.get("ok") and res.get("text"):
            return res
        # Voice-Gateway hat geantwortet (auch leer) → nicht noch 1–2s Requesty-STT draufpacken
        if res and res.get("provider") == "voice_gateway" and res.get("error") == "empty_stt":
            return res

    # Direkt-OpenAI (optional Fallback)
    key = openai_key()
    if key:
        try:
            with p.open("rb") as f:
                r = requests.post(
                    f"{openai_base_url()}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {key}"},
                    files={"file": (p.name, f)},
                    data={"model": _env("OPENAI_WHISPER_MODEL", "whisper-1"), "language": language},
                    timeout=30,
                )
            if r.ok:
                text = (r.json().get("text") or "").strip()
                if text:
                    return {"ok": True, "text": text, "provider": "openai_whisper"}
        except Exception as e:
            return {"ok": False, "text": "", "error": f"whisper:{type(e).__name__}", "gateway_error": gw_err}

    return {
        "ok": False,
        "text": "",
        "error": "stt_unavailable",
        "gateway_error": gw_err,
        "hint": "Voice-Gateway auf auto-01 oder OPENAI_API_KEY für Whisper.",
    }


def _chat_ollama(
    messages: list[dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
    timeout: float,
) -> dict[str, Any]:
    import requests

    url = ollama_url()
    model = ollama_model()
    payload = {
        "model": model,
        "stream": False,
        "messages": messages,
        "keep_alive": _env("OLLAMA_KEEP_ALIVE", "30m"),
        "options": {
            "temperature": temperature,
            "num_predict": max(64, min(int(max_tokens), 2048)),
        },
    }
    try:
        r = requests.post(f"{url}/api/chat", json=payload, timeout=timeout)
        if not r.ok:
            return {"ok": False, "provider": "ollama", "error": f"http_{r.status_code}"}
        data = r.json() if r.content else {}
        text = ((data.get("message") or {}).get("content") or "").strip()
        if not text:
            return {"ok": False, "provider": "ollama", "error": "empty"}
        return {"ok": True, "reply": text, "provider": "ollama", "model": model}
    except Exception as e:
        return {"ok": False, "provider": "ollama", "error": f"exception:{type(e).__name__}"}


def _chat_openai_compatible(
    messages: list[dict[str, str]],
    *,
    base_url: str,
    key: str,
    model: str,
    provider: str,
    max_tokens: int,
    temperature: float,
    timeout: float,
) -> dict[str, Any]:
    import requests

    if not key:
        return {"ok": False, "provider": provider, "error": "missing_key"}
    # Realistisches Failover: Connect schnell failen, Gesamt-Timeout getrennt.
    # Kein Fake-„200ms Gateway-Bypass“ – LLM-TTFT liegt typisch bei 300–800ms+.
    connect_t = float(_env("LLM_CONNECT_TIMEOUT", "5") or 5)
    try:
        r = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=(connect_t, timeout),
        )
        if not r.ok:
            return {"ok": False, "provider": provider, "error": f"http_{r.status_code}", "model": model}
        text = (r.json()["choices"][0]["message"]["content"] or "").strip()
        if not text:
            return {"ok": False, "provider": provider, "error": "empty", "model": model}
        return {"ok": True, "reply": text, "provider": provider, "model": model}
    except Exception as e:
        return {"ok": False, "provider": provider, "error": f"exception:{type(e).__name__}", "model": model}


def stream_openai_compatible(
    messages: list[dict[str, Any]],
    *,
    base_url: str,
    key: str,
    model: str,
    provider: str,
    max_tokens: int = 800,
    temperature: float = 0.55,
    timeout: float = 90,
    on_delta=None,
) -> dict[str, Any]:
    """SSE-Streaming. on_delta(str) optional. Rückgabe wie chat()."""
    import json
    import requests

    if not key:
        return {"ok": False, "provider": provider, "error": "missing_key"}
    connect_t = float(_env("LLM_CONNECT_TIMEOUT", "5") or 5)
    buf: list[str] = []
    try:
        with requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            },
            stream=True,
            timeout=(connect_t, timeout),
        ) as r:
            if r.status_code >= 500 or r.status_code in (408, 429):
                return {"ok": False, "provider": provider, "error": f"http_{r.status_code}", "model": model}
            if not r.ok:
                return {"ok": False, "provider": provider, "error": f"http_{r.status_code}", "model": model}
            for raw in r.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                line = raw.strip() if isinstance(raw, str) else raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                except Exception:
                    continue
                delta = (((data.get("choices") or [{}])[0].get("delta") or {}).get("content")) or ""
                if not delta:
                    continue
                buf.append(delta)
                if on_delta:
                    try:
                        on_delta(delta)
                    except Exception:
                        pass
        text = "".join(buf).strip()
        if not text:
            return {"ok": False, "provider": provider, "error": "empty", "model": model}
        return {"ok": True, "reply": text, "provider": provider, "model": model, "streamed": True}
    except Exception as e:
        return {"ok": False, "provider": provider, "error": f"exception:{type(e).__name__}", "model": model}

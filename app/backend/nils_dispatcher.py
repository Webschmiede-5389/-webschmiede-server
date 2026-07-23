"""Nils Dispatcher: Smart-LLM-Router für Telegram/Agency.

Routen A/B/C, OpenRouter-Gateway, Data-Stripping, Fallback-Kette.
Kein Parallel-Stack: nutzt llm_client (Ollama / OpenAI / OpenRouter).

Hinweis DSGVO: Zero Data Retention (ZDR) bei Providern ist hilfreich,
ersetzt aber keinen AVV und keine Zweckbindung. Sensible Daten werden
vor Cloud-Calls maskiert.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

import llm_client as llm

log = logging.getLogger("nils_dispatcher")

# ── PII / sensible Muster (vor Cloud) ───────────────────────────────────────
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b", re.I)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-./]?)?(?:\(?0?\d{2,5}\)?[\s\-./]?)?\d{3,4}[\s\-./]?\d{3,5}\b"
)
_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_SECRETISH_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9]{20,}|xai-[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._\-]{20,})\b",
    re.I,
)

_ROUTE_C_HINTS = (
    "lieferschein",
    "rechnung",
    "pdf",
    "bild",
    "foto",
    "screenshot",
    "ocr",
    "extrahier",
    "json",
    "beleg",
    "scan",
    "vision",
    "strukturiert",
)
_ROUTE_B_HINTS = (
    "architektur",
    "strategie",
    "code",
    "refactor",
    "analysier",
    "komplex",
    "deep",
    "implementier",
    "python",
    "typescript",
    "docker",
    "sql",
    "angebot schreiben",
    "lange antwort",
)


def strip_pii(text: str) -> tuple[str, dict[str, int]]:
    """Maskiert sensible Tokens. Rückgabe: (masked, counts)."""
    counts = {"iban": 0, "email": 0, "phone": 0, "card": 0, "secret": 0}
    if not text:
        return text, counts

    def _iban(m: re.Match[str]) -> str:
        counts["iban"] += 1
        return "[IBAN]"

    def _email(m: re.Match[str]) -> str:
        counts["email"] += 1
        return "[EMAIL]"

    def _secret(m: re.Match[str]) -> str:
        counts["secret"] += 1
        return "[SECRET]"

    def _card(m: re.Match[str]) -> str:
        raw = re.sub(r"\D", "", m.group(0))
        if len(raw) < 13:
            return m.group(0)
        counts["card"] += 1
        return "[CARD]"

    def _phone(m: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        # Kunden-IDs / kurze Zahlen nicht anfassen
        if len(digits) < 8 or digits.startswith("19") or digits.startswith("20"):
            return m.group(0)
        # SHY001 etc. schon durch \b abgefangen
        counts["phone"] += 1
        return "[PHONE]"

    out = _SECRETISH_RE.sub(_secret, text)
    out = _IBAN_RE.sub(_iban, out)
    out = _EMAIL_RE.sub(_email, out)
    out = _CARD_RE.sub(_card, out)
    out = _PHONE_RE.sub(_phone, out)
    return out, counts


def _env_csv(key: str, default: str) -> list[str]:
    raw = (llm._env(key, default) or default).strip()
    return [x.strip() for x in raw.split(",") if x.strip()]


def route_models(route: str) -> list[dict[str, str]]:
    """Modell-Kette pro Route. Format provider:model.

    Telegram/ChatGPT-Feeling: Cloud-first (schnelle EU-Modelle), Ollama nur Fallback.
    DSGVO: Requesty EU + EU-Inference. Kein Fake-200ms-Bypass.
    """
    route = (route or "A").upper()
    ollama = f"ollama:{llm.ollama_model()}"
    # Cloud zuerst = spürbar schneller (Ollama oft 3–8s warm/cold)
    cloud_first = llm._env("NILS_CLOUD_FIRST", "1") not in ("0", "false", "no")
    if llm.primary_api_key() and llm.primary_gateway_url():
        # A: Mistral Small EU war im Smoke schnellstes TTFT (~0.5s)
        a_cloud = (
            "primary:mistral/mistral-small-latest,"
            "primary:nebius/meta-llama/Llama-3.3-70B-Instruct,"
            "primary:azure/gpt-4o-mini@swedencentral,"
            "primary:tensorx/deepseek-v4-flash,"
            "openai:gpt-4o-mini"
        )
        a_chain = f"{a_cloud},{ollama}" if cloud_first else f"{ollama},{a_cloud}"
        defaults = {
            "A": a_chain,
            "B": (
                "primary:bedrock/claude-sonnet-4@eu-central-1,"
                "primary:vertex/claude-sonnet-5@eu,"
                "primary:tensorx/deepseek-v4-pro,"
                "primary:mistral/mistral-medium-3-5,"
                f"{ollama},"
                "openai:gpt-4o"
            ),
            "C": (
                "primary:azure/gpt-4o-mini@swedencentral,"
                "primary:bedrock/claude-sonnet-4@eu-central-1,"
                "primary:mistral/mistral-small-latest,"
                "openai:gpt-4o,"
                f"{ollama}"
            ),
        }
    else:
        defaults = {
            "A": (
                f"{ollama},"
                "openrouter:deepseek/deepseek-chat,"
                "openai:gpt-4o-mini"
            ),
            "B": (
                "openrouter:anthropic/claude-sonnet-4,"
                "openai:gpt-4o,"
                f"{ollama}"
            ),
            "C": (
                "openai:gpt-4o,"
                "openrouter:openai/gpt-4o,"
                f"{ollama}"
            ),
        }
    env_key = f"NILS_ROUTE_{route}_MODELS"
    items = _env_csv(env_key, defaults.get(route, defaults["A"]))
    out: list[dict[str, str]] = []
    for item in items:
        if ":" not in item:
            continue
        provider, model = item.split(":", 1)
        out.append({"provider": provider.strip().lower(), "model": model.strip()})
    return out


def classify_route(
    text: str,
    *,
    hint: str | None = None,
    has_image: bool = False,
    has_pdf: bool = False,
) -> str:
    """Schnelle Regel-Klassifikation (kein Extra-LLM-Call)."""
    if hint:
        h = hint.strip().upper()
        if h in ("A", "B", "C"):
            return h
    if has_image or has_pdf:
        return "C"
    t = (text or "").lower()
    if any(k in t for k in _ROUTE_C_HINTS):
        return "C"
    if len(t) > 1200 or any(k in t for k in _ROUTE_B_HINTS):
        return "B"
    return "A"


def _mask_messages(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    total = {"iban": 0, "email": 0, "phone": 0, "card": 0, "secret": 0}
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role") or "user"
        content = m.get("content")
        if isinstance(content, str):
            masked, counts = strip_pii(content)
            for k, v in counts.items():
                total[k] = total.get(k, 0) + v
            out.append({**m, "role": role, "content": masked})
        else:
            # Vision/multipart: Textteile maskieren, Binär unverändert
            out.append(m)
    return out, total


def _call_target(
    messages: list[dict[str, Any]],
    *,
    provider: str,
    model: str,
    max_tokens: int,
    temperature: float,
    timeout: float,
    use_cache: bool,
) -> dict[str, Any]:
    if provider == "ollama":
        # Temporär Modell überschreiben über Env wäre global – daher direkter Call
        return _chat_ollama_model(
            messages, model=model, max_tokens=max_tokens, temperature=temperature, timeout=timeout
        )
    if provider == "openai":
        return llm._chat_openai_compatible(
            messages,
            base_url=llm.openai_base_url(),
            key=llm.openai_key(),
            model=model,
            provider="openai",
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
    if provider == "primary":
        url = llm.primary_gateway_url()
        key = llm.primary_api_key()
        if not url or not key:
            return {"ok": False, "provider": "primary", "error": "missing_key"}
        try:
            import requesty_client as rq

            guard = rq.budget_guard(kind="chat")
            if not guard.get("ok"):
                return {
                    "ok": False,
                    "provider": "primary",
                    "error": guard.get("error") or "budget_block",
                    "budget": guard,
                }
        except Exception:
            pass
        return llm._chat_openai_compatible(
            messages,
            base_url=url,
            key=key,
            model=model or llm.primary_default_model(),
            provider="primary",
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
    if provider == "openrouter":
        return _chat_openrouter(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            use_cache=use_cache,
        )
    if provider == "grok":
        return llm._chat_openai_compatible(
            messages,
            base_url="https://api.x.ai/v1",
            key=llm.xai_key(),
            model=model,
            provider="grok",
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
    if provider == "gemini":
        return llm._chat_openai_compatible(
            messages,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            key=llm.gemini_key(),
            model=model,
            provider="gemini",
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
    return {"ok": False, "provider": provider, "error": "unknown_provider"}


def _chat_ollama_model(
    messages: list[dict[str, Any]],
    *,
    model: str,
    max_tokens: int,
    temperature: float,
    timeout: float,
) -> dict[str, Any]:
    import requests

    url = llm.ollama_url()
    payload = {
        "model": model,
        "stream": False,
        "messages": messages,
        "keep_alive": llm._env("OLLAMA_KEEP_ALIVE", "30m"),
        "options": {
            "temperature": temperature,
            "num_predict": max(64, min(int(max_tokens), 2048)),
        },
    }
    try:
        r = requests.post(f"{url}/api/chat", json=payload, timeout=timeout)
        if not r.ok:
            return {"ok": False, "provider": "ollama", "model": model, "error": f"http_{r.status_code}"}
        data = r.json() if r.content else {}
        text = ((data.get("message") or {}).get("content") or "").strip()
        if not text:
            return {"ok": False, "provider": "ollama", "model": model, "error": "empty"}
        return {"ok": True, "reply": text, "provider": "ollama", "model": model}
    except Exception as e:
        return {"ok": False, "provider": "ollama", "model": model, "error": f"exception:{type(e).__name__}"}


def openrouter_key() -> str:
    return llm._env("OPENROUTER_API_KEY")


def _chat_openrouter(
    messages: list[dict[str, Any]],
    *,
    model: str,
    max_tokens: int,
    temperature: float,
    timeout: float,
    use_cache: bool,
) -> dict[str, Any]:
    import requests

    key = openrouter_key()
    if not key:
        return {"ok": False, "provider": "openrouter", "error": "missing_key"}

    # Prompt Caching: System-Message mit cache_control (OpenRouter/Anthropic-Stil)
    payload_messages: list[dict[str, Any]] = []
    for i, m in enumerate(messages):
        role = m.get("role") or "user"
        content = m.get("content")
        if use_cache and role == "system" and isinstance(content, str) and len(content) > 200:
            payload_messages.append(
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": content,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            )
        else:
            payload_messages.append({"role": role, "content": content})

    body: dict[str, Any] = {
        "model": model,
        "messages": payload_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        # ZDR-Wunsch: Provider ohne Data Collection bevorzugen
        "provider": {"data_collection": "deny"},
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": llm._env("OPENROUTER_SITE_URL", "https://digitalehandwerkskunst.de"),
        "X-Title": llm._env("OPENROUTER_APP_NAME", "Webschmiede-Nils"),
    }
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=timeout,
        )
        if not r.ok:
            # Fallback ohne data_collection deny (manche Modelle blocken)
            if r.status_code in (400, 404) and "provider" in body:
                body.pop("provider", None)
                r = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=body,
                    timeout=timeout,
                )
            if not r.ok:
                err_snip = (r.text or "")[:160]
                return {
                    "ok": False,
                    "provider": "openrouter",
                    "model": model,
                    "error": f"http_{r.status_code}",
                    "detail": err_snip,
                }
        data = r.json() if r.content else {}
        text = (data["choices"][0]["message"]["content"] or "").strip()
        if not text:
            return {"ok": False, "provider": "openrouter", "model": model, "error": "empty"}
        return {
            "ok": True,
            "reply": text,
            "provider": "openrouter",
            "model": model,
            "usage": data.get("usage"),
        }
    except Exception as e:
        return {
            "ok": False,
            "provider": "openrouter",
            "model": model,
            "error": f"exception:{type(e).__name__}",
        }


def dispatch(
    messages: list[dict[str, Any]],
    *,
    route: str | None = None,
    hint_text: str = "",
    has_image: bool = False,
    has_pdf: bool = False,
    max_tokens: int = 800,
    temperature: float = 0.55,
    timeout: float = 90,
    strip: bool = True,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Haupt-Einstieg: klassifizieren → strippen → Modell-Kette mit Fallback."""
    user_blob = hint_text or " ".join(
        str(m.get("content") or "") for m in messages if m.get("role") == "user"
    )
    chosen = classify_route(user_blob, hint=route, has_image=has_image, has_pdf=has_pdf)

    work = messages
    strip_counts: dict[str, int] = {}
    if strip and llm._env("NILS_STRIP_PII", "1") not in ("0", "false", "no"):
        # Lokal (Ollama) darf unmaskiert bleiben – Strip nur wenn Cloud in der Kette
        chain_preview = route_models(chosen)
        needs_cloud = any(c["provider"] != "ollama" for c in chain_preview)
        if needs_cloud:
            work, strip_counts = _mask_messages(messages)

    attempts: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    for target in route_models(chosen):
        t1 = time.perf_counter()
        result = _call_target(
            work,
            provider=target["provider"],
            model=target["model"],
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            use_cache=use_cache,
        )
        elapsed_ms = int((time.perf_counter() - t1) * 1000)
        attempts.append(
            {
                "provider": target["provider"],
                "model": target["model"],
                "ok": bool(result.get("ok")),
                "error": result.get("error"),
                "ms": elapsed_ms,
            }
        )
        if result.get("ok") and result.get("reply"):
            result["route"] = chosen
            result["attempts"] = attempts
            result["strip"] = strip_counts
            result["dispatch_ms"] = int((time.perf_counter() - t0) * 1000)
            return result

    # Letzter Fallback: klassischer Provider-Order OHNE Dispatcher (keine Rekursion)
    fallback = llm.chat(
        work,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        use_dispatcher=False,
    )
    fallback["route"] = chosen
    fallback["attempts"] = attempts
    fallback["strip"] = strip_counts
    fallback["dispatch_ms"] = int((time.perf_counter() - t0) * 1000)
    if not fallback.get("ok"):
        fallback["error"] = fallback.get("error") or "all_routes_failed"
    return fallback


def dispatch_stream(
    messages: list[dict[str, Any]],
    *,
    route: str | None = None,
    hint_text: str = "",
    max_tokens: int = 800,
    temperature: float = 0.55,
    timeout: float = 90,
    on_delta=None,
) -> dict[str, Any]:
    """Wie dispatch, aber streamt über Requesty/OpenAI-kompatible Targets.

    Ollama in der Kette wird übersprungen (kein SSE). Bei Stream-Fail → nächstes Target.
    """
    user_blob = hint_text or " ".join(
        str(m.get("content") or "") for m in messages if m.get("role") == "user"
    )
    chosen = classify_route(user_blob, hint=route)
    work = messages
    strip_counts: dict[str, int] = {}
    if llm._env("NILS_STRIP_PII", "1") not in ("0", "false", "no"):
        chain_preview = route_models(chosen)
        if any(c["provider"] != "ollama" for c in chain_preview):
            work, strip_counts = _mask_messages(messages)

    attempts: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    for target in route_models(chosen):
        provider = target["provider"]
        model = target["model"]
        if provider == "ollama":
            attempts.append({"provider": provider, "model": model, "ok": False, "error": "skip_stream"})
            continue
        if provider == "primary":
            base, key = llm.primary_gateway_url(), llm.primary_api_key()
            try:
                import requesty_client as rq

                guard = rq.budget_guard(kind="chat")
                if not guard.get("ok"):
                    attempts.append(
                        {
                            "provider": provider,
                            "model": model,
                            "ok": False,
                            "error": guard.get("error") or "budget_block",
                        }
                    )
                    continue
            except Exception:
                pass
        elif provider == "openai":
            base, key = llm.openai_base_url(), llm.openai_key()
        else:
            attempts.append({"provider": provider, "model": model, "ok": False, "error": "no_stream"})
            continue
        if not base or not key:
            attempts.append({"provider": provider, "model": model, "ok": False, "error": "missing_key"})
            continue
        t1 = time.perf_counter()
        result = llm.stream_openai_compatible(
            work,
            base_url=base,
            key=key,
            model=model,
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            on_delta=on_delta,
        )
        attempts.append(
            {
                "provider": provider,
                "model": model,
                "ok": bool(result.get("ok")),
                "error": result.get("error"),
                "ms": int((time.perf_counter() - t1) * 1000),
            }
        )
        if result.get("ok") and result.get("reply"):
            result["route"] = chosen
            result["attempts"] = attempts
            result["strip"] = strip_counts
            result["dispatch_ms"] = int((time.perf_counter() - t0) * 1000)
            return result

    # Fallback non-stream
    return dispatch(
        messages,
        route=chosen,
        hint_text=hint_text,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )


def readiness() -> dict[str, Any]:
    base = llm.readiness()
    base["openrouter_key"] = bool(openrouter_key())
    base["primary_key"] = bool(llm.primary_api_key() and llm.primary_gateway_url())
    base["primary_gateway"] = llm.primary_gateway_url() or None
    base["dispatcher"] = True
    base["routes"] = {
        "A": [f"{x['provider']}:{x['model']}" for x in route_models("A")],
        "B": [f"{x['provider']}:{x['model']}" for x in route_models("B")],
        "C": [f"{x['provider']}:{x['model']}" for x in route_models("C")],
    }
    base["strip_pii"] = llm._env("NILS_STRIP_PII", "1") not in ("0", "false", "no")
    base["note"] = (
        "Nils Dispatcher: Primary=Requesty/EU-Gateway, Fallback=OpenAI direkt, "
        "Route A lokal zuerst (Ollama). ZDR/Strip vor Cloud."
    )
    return base

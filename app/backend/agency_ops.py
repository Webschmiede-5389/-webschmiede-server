"""Agency Ops: Server-Health, Kunden-Health, Übersicht."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from agency_cockpit import list_kunden_summary
from agency_metrics import get_kpis, recent_events
from client_setup import global_automation_status


def _run(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (proc.stdout or proc.stderr or "").strip()[:200]
        return proc.returncode == 0, out
    except Exception as exc:
        return False, str(exc)[:200]


def _http_probe(url: str, timeout: int = 8) -> dict:
    if not url or not url.startswith("http"):
        return {"ok": False, "status": 0, "error": "keine URL"}
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Webschmiede-Ops/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"ok": 200 <= resp.status < 400, "status": resp.status, "url": url}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "url": url, "error": str(exc.reason)[:80]}
    except Exception as exc:
        return {"ok": False, "status": 0, "url": url, "error": str(exc)[:120]}


def _service_active(name: str) -> bool:
    ok, out = _run(["systemctl", "is-active", name], timeout=8)
    return ok and out.strip() == "active"


def _read_mem_percent() -> float | None:
    try:
        info: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                info[parts[0].rstrip(":")] = int(parts[1])
        total = info.get("MemTotal", 0)
        avail = info.get("MemAvailable", info.get("MemFree", 0))
        if total <= 0:
            return None
        return round(100.0 * (total - avail) / total, 1)
    except OSError:
        return None


def _last_backup_marker() -> dict:
    log = Path("/var/log/snack-backup.log")
    if not log.is_file():
        return {"ok": False, "detail": "kein Backup-Log", "offsite": {"ok": False, "detail": "kein Log"}}
    today = datetime.now().strftime("%Y-%m-%d")
    local_ok = False
    offsite_ok = False
    local_detail = "heute kein backup ok im Log"
    offsite_detail = "offsite nicht konfiguriert oder fehlgeschlagen"
    try:
        for line in reversed(log.read_text(encoding="utf-8", errors="replace").splitlines()[-120:]):
            if today in line and "backup ok" in line and not local_ok:
                local_ok = True
                local_detail = line.strip()[:120]
            if today in line and "offsite ok" in line and not offsite_ok:
                offsite_ok = True
                offsite_detail = line.strip()[:120]
            if today in line and "offsite skip" in line and not offsite_ok:
                offsite_detail = line.strip()[:120]
    except OSError:
        pass
    return {
        "ok": local_ok,
        "detail": local_detail,
        "offsite": {"ok": offsite_ok, "detail": offsite_detail},
    }


def get_server_health() -> dict:
    api_ok, _ = _run(
        ["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:8000/api/health"],
        timeout=10,
    )
    n8n_ok = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:5678/healthz", timeout=5) as r:
            n8n_ok = r.status == 200
    except Exception:
        n8n_ok = _service_active("n8n")

    integrations = {}
    try:
        from agency_secrets import check_integrations_health

        integrations = check_integrations_health(live=False)
    except Exception as exc:
        integrations = {"ok": False, "error": str(exc)[:120]}

    ram = _read_mem_percent()
    issues = []
    if not _service_active("snack-api"):
        issues.append("snack-api down")
    if ram is not None and ram >= 85:
        issues.append(f"RAM {ram}%")
    if not integrations.get("ok"):
        issues.append("Integrationen unvollständig")

    return {
        "ok": not issues,
        "services": {
            "snack_api": _service_active("snack-api"),
            "n8n": _service_active("n8n"),
            "nginx": _service_active("nginx"),
        },
        "api_health": api_ok,
        "n8n_health": n8n_ok,
        "ram_percent": ram,
        "backup": _last_backup_marker(),
        "integrations": integrations,
        "automations": global_automation_status(),
        "issues": issues,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


def get_client_health(kid: str, kunde: dict | None = None) -> dict:
    from integrations import load_kunde_json

    k = kunde or load_kunde_json(kid)
    if not k:
        return {"kid": kid.upper(), "ok": False, "error": "Kunde nicht gefunden"}

    urls = k.get("urls") or {}
    probe_url = (
        urls.get("test_bestellen")
        or urls.get("live_bestellen")
        or urls.get("test_hauptseite")
        or urls.get("onboarding_url")
        or ""
    )
    portal = _http_probe(probe_url)

    auto = k.get("automations") or {}
    whatsapp = k.get("whatsapp") or {}
    knowledge = k.get("knowledge") or {}
    sms_cfg = k.get("sms") or {}
    voice = k.get("voice") or {}
    integrations = k.get("integrations") or {}
    global_auto = global_automation_status()
    sms_wanted = sms_cfg.get("enabled", auto.get("sms", {}).get("requested", k.get("crm", {}).get("sms_enabled", False)))
    sms_active = bool(global_auto.get("sms", {}).get("active")) and bool(os.getenv("SMS_API_KEY", "").strip())

    checks = [
        {
            "id": "portal",
            "label": "Portal erreichbar",
            "ok": portal.get("ok", False),
            "detail": portal.get("error") or f"HTTP {portal.get('status', 0)}",
        },
        {
            "id": "n8n",
            "label": "n8n Webhook",
            "ok": bool((k.get("n8n") or {}).get("order_webhook")),
            "detail": (k.get("n8n") or {}).get("order_webhook", "fehlt")[:80],
        },
        {
            "id": "sms",
            "label": "SMS",
            "ok": not sms_wanted or sms_active,
            "detail": (
                f"Nummer {sms_cfg.get('phone_number') or 'noch offen'}"
                if sms_wanted and sms_active
                else ("gewünscht, Key fehlt" if sms_wanted else "aus")
            ),
        },
        {
            "id": "whatsapp",
            "label": "WhatsApp",
            "ok": not whatsapp.get("enabled") or bool(whatsapp.get("allowed_phones") or whatsapp.get("phone_number_id")),
            "detail": (
                "Nummern freigeschaltet"
                if whatsapp.get("allowed_phones")
                else ("Phone Number ID fehlt" if whatsapp.get("enabled") else "aus")
            ),
        },
        {
            "id": "voice",
            "label": "Voice",
            "ok": not voice.get("enabled") or bool(voice.get("agent_id") or voice.get("phone_number")),
            "detail": (
                f"{voice.get('provider') or 'provider'} · {voice.get('knowledge_pack') or 'pack'}"
                if voice.get("enabled")
                else "aus"
            ),
        },
        {
            "id": "knowledge",
            "label": "Knowledge Pack",
            "ok": bool(knowledge.get("pack") or voice.get("knowledge_pack")),
            "detail": knowledge.get("pack") or voice.get("knowledge_pack") or "kein Pack",
        },
        {
            "id": "lexware",
            "label": "Lexware",
            "ok": not integrations.get("lexware", {}).get("enabled") or bool(integrations.get("lexware", {}).get("api_key_env")),
            "detail": "optional",
        },
    ]

    failed = [c for c in checks if not c["ok"]]
    return {
        "kid": k.get("id", kid).upper(),
        "name": k.get("name", ""),
        "status": k.get("status", ""),
        "branche": k.get("branche", ""),
        "ok": len(failed) == 0,
        "checks": checks,
        "open_points": len(k.get("offene_punkte") or []),
        "portal_url": probe_url,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


def get_agency_overview(db: sqlite3.Connection) -> dict:
    kunden = list_kunden_summary()
    clients = []
    for row in kunden:
        kid = row.get("id") or row.get("kid") or ""
        if kid:
            clients.append(get_client_health(kid))
    kpis = get_kpis(db, days=7)
    events = recent_events(db, limit=15)
    server = get_server_health()
    return {
        "ok": server.get("ok") and all(c.get("ok") for c in clients) if clients else server.get("ok"),
        "server": server,
        "kpis": kpis,
        "kunden": clients,
        "recent_events": events,
        "kunde_count": len(clients),
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }

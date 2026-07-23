"""Ops-Guardian (Alleskönner, ehrlich): orchestriert Checks + Safe-Fixes.

Nicht magisch. Fixt was sicher ist. Meldet den Rest an Christian.
Takt: Cron alle 15 Min auf web. Kein Blind-Retry bei Auth/Zahlung/Meta.
"""
from __future__ import annotations

import json
import os
import socket
import ssl
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_PATH = Path(
    os.getenv("OPS_GUARDIAN_STATE", "/var/lib/webschmiede/ops-guardian-state.json")
)
# Lokal/Windows Fallback
if os.name == "nt":
    STATE_PATH = Path(__file__).resolve().parents[2] / "agency" / "ops-guardian-state.json"

CATALOG = (
    ("health", "https://digitalehandwerkskunst.de/api/health", True),
    ("agency-setup", "https://digitalehandwerkskunst.de/agency-setup", False),
    ("b2b", "https://digitalehandwerkskunst.de/b2b-portal.html", False),
    ("yassine-health", "https://yassine.digitalehandwerkskunst.de/api/health", True),
)

SAFE_FIXES = (
    "snack-api restart (max 2/h) wenn /api/health rot",
    "IONOS DNS A-Record (über Route-Watchdog, max 2/h)",
    "CRLF→LF + Job-Retry (Nightly Watchdog)",
    "Cal.com stop bei RAM kritisch (Resource-Watchdog)",
)

ALERT_ONLY = (
    "WhatsApp/Meta Tokens fehlen",
    "SSL Ablauf < 14 Tage",
    "Disk/RAM Warnung ohne klare Cleanup-Whitelist",
    "n8n Workflow-Fehler / Dual-Peer SSH tot",
    "Shipcheck Soft-404 auf Dashboards",
    "Stripe/SMTP Live-Auth-Fehler",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _probe(url: str, *, want_json: bool = False, timeout: int = 15) -> dict[str, Any]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "WebschmiedeOpsGuardian/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            body = r.read(4000).decode("utf-8", errors="replace")
            code = int(getattr(r, "status", None) or r.getcode())
            ok = 200 <= code < 400
            if want_json and ok:
                ok = "ok" in body.lower() or body.strip().startswith("{")
            return {"ok": ok, "status": code, "detail": f"HTTP {code}", "url": url}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": int(e.code), "detail": f"HTTP {e.code}", "url": url}
    except Exception as e:
        return {"ok": False, "status": 0, "detail": str(e)[:120], "url": url}


def _ssl_days_left(host: str = "digitalehandwerkskunst.de") -> dict[str, Any]:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        not_after = cert.get("notAfter") if cert else None
        if not not_after:
            return {"ok": False, "days": None, "detail": "Kein Zertifikat-Datum"}
        # e.g. 'Jul 19 12:00:00 2027 GMT'
        exp = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days = (exp - datetime.now(timezone.utc)).days
        ok = days >= 14
        return {
            "ok": ok,
            "days": days,
            "expires": exp.strftime("%Y-%m-%d"),
            "detail": f"SSL noch {days} Tage (bis {exp.date()})",
        }
    except Exception as e:
        return {"ok": False, "days": None, "detail": f"SSL-Check: {e}"[:120]}


def _restart_snack_api() -> dict[str, Any]:
    if os.name == "nt" or not Path("/usr/bin/systemctl").is_file() and not Path("/bin/systemctl").is_file():
        return {"ok": False, "skipped": True, "detail": "Kein systemctl hier"}
    try:
        from watchdog_cabinets import can_repair, record_repair
    except Exception:
        can_repair = lambda *a, **k: True  # noqa: E731
        record_repair = lambda *a, **k: None  # noqa: E731
    if not can_repair("guardian_snack_api", max_per_hour=2):
        return {"ok": False, "skipped": True, "detail": "Repair-Budget snack-api erschöpft (max 2/h)"}
    r = subprocess.run(
        ["systemctl", "restart", "snack-api"],
        capture_output=True,
        text=True,
        timeout=90,
    )
    if r.returncode == 0:
        record_repair("guardian_snack_api")
        return {"ok": True, "detail": "snack-api neu gestartet"}
    return {"ok": False, "detail": (r.stderr or r.stdout or "restart failed")[:160]}


def _whatsapp_readiness() -> dict[str, Any]:
    try:
        import nils_whatsapp_ops as wa

        if hasattr(wa, "status"):
            st = wa.status()
        elif hasattr(wa, "readiness"):
            st = wa.readiness()
        else:
            st = {"ok": False, "detail": "kein status()"}
        # Missing tokens = alert, not failure of whole platform
        missing = []
        for key in ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "OWNER_PHONE"):
            info = (st.get("secrets") or st.get("checks") or {}).get(key) if isinstance(st, dict) else None
            if isinstance(info, dict) and info.get("set") is False:
                missing.append(key)
            elif st.get(key) is False:
                missing.append(key)
        # Heuristik aus einfachen Feldern
        if st.get("ready") is False or st.get("configured") is False:
            if not missing:
                missing.append("whatsapp_not_ready")
        ready = bool(st.get("ready") or st.get("configured") or st.get("ops_ready"))
        if "token_ok" in st:
            ready = bool(st.get("token_ok") and st.get("phone_id_ok"))
        return {
            "ok": True,  # Check selbst ok
            "ready": ready,
            "alert": not ready,
            "missing": missing or st.get("missing") or [],
            "detail": "WhatsApp Ops bereit" if ready else "WhatsApp Ops: Tokens/Nummer fehlen (Alert only)",
            "raw_keys": list(st.keys())[:20] if isinstance(st, dict) else [],
        }
    except Exception as e:
        return {"ok": True, "ready": False, "alert": True, "detail": f"WhatsApp-Status: {e}"[:120], "missing": []}


def _env_secret_set(name: str) -> bool:
    v = (os.getenv(name) or "").strip()
    if v:
        return True
    for path in (Path("/root/app/backend/.env"), Path("/root/app/deploy.secrets.local")):
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith(f"{name}=") and len(line.split("=", 1)[-1].strip()) > 2:
                    return True
        except OSError:
            continue
    return False


def _whatsapp_simple() -> dict[str, Any]:
    token = _env_secret_set("WHATSAPP_ACCESS_TOKEN")
    phone = _env_secret_set("WHATSAPP_PHONE_NUMBER_ID")
    owner = _env_secret_set("OWNER_PHONE") or _env_secret_set("NILS_OPS_OWNER_PHONES")
    verify = _env_secret_set("WHATSAPP_VERIFY_TOKEN")
    ready = token and phone and owner
    missing = [k for k, ok in (
        ("WHATSAPP_ACCESS_TOKEN", token),
        ("WHATSAPP_PHONE_NUMBER_ID", phone),
        ("OWNER_PHONE", owner),
    ) if not ok]
    return {
        "ok": True,
        "ready": ready,
        "alert": not ready,
        "missing": missing,
        "verify_token": verify,
        "detail": "WhatsApp Ops bereit" if ready else f"WhatsApp fehlt: {', '.join(missing)}",
    }


def _dual_snapshot() -> dict[str, Any]:
    try:
        import dual_infra as dual

        st = dual.dual_status(use_ssh=False)
        return {
            "ok": bool(st.get("ok")),
            "pitch_safe": st.get("customer_pitch_safe"),
            "alerts": st.get("alerts") or [],
            "web_ok": (st.get("web") or {}).get("ok"),
            "auto_ok": (st.get("auto") or {}).get("ok"),
            "detail": "Dual lokal ok" if st.get("ok") else "Dual: Alerts",
        }
    except Exception as e:
        return {"ok": False, "detail": f"dual: {e}"[:120], "alerts": [str(e)[:80]]}


def _resource_snapshot() -> dict[str, Any]:
    if os.name == "nt" or not Path("/proc/meminfo").is_file():
        return {"ok": True, "skipped": True, "detail": "Resource nur auf Linux-Server"}
    try:
        import resource_watchdog as rw

        metrics = rw.collect_metrics()
        issues = rw.evaluate(metrics)
        # n8n läuft auf auto-01, nicht auf web – dort kein Alarm
        host_role = (os.getenv("SERVER_ROLE") or "").strip().lower()
        on_web = host_role in ("web", "web-01", "") or Path("/etc/systemd/system/snack-api.service").is_file()
        if on_web and not Path("/etc/systemd/system/n8n.service").is_file():
            issues = [i for i in issues if i.get("id") != "service_down_n8n"]
        actions: list[str] = []
        # Safe: Cal.com bei RAM kritisch
        if any(i["id"] == "ram_crit" for i in issues):
            if rw.stop_calcom():
                actions.append("Cal.com gestoppt (RAM kritisch)")
        return {
            "ok": len([i for i in issues if i["level"] == "critical"]) == 0,
            "alert": bool(issues),
            "metrics": {
                "ram": metrics.get("ram_percent"),
                "disk": metrics.get("disk_percent"),
                "load": metrics.get("load_1m"),
                "services": metrics.get("services"),
            },
            "issues": issues,
            "actions": actions,
            "detail": "Resource ok" if not issues else f"{len(issues)} Resource-Issues",
        }
    except Exception as e:
        return {"ok": False, "detail": f"resource: {e}"[:120], "issues": [], "actions": []}


def _ship_catalog() -> list[dict[str, Any]]:
    try:
        import agency_shipcheck as sc

        out = []
        for name, url, _ in CATALOG:
            c = sc.check_url(url)
            out.append({"id": name, **c})
        return out
    except Exception:
        return [
            {"id": name, **_probe(url, want_json=want_json)}
            for name, url, want_json in CATALOG
        ]


def run(*, repair: bool = True, mail: bool = False, force_mail: bool = False) -> dict[str, Any]:
    """Ein Guardian-Lauf. repair=Safe-Fixes, mail=bei Bedarf benachrichtigen."""
    checks: dict[str, Any] = {}
    repairs: list[dict[str, Any]] = []
    alerts: list[str] = []

    catalog = _ship_catalog()
    checks["surfaces"] = catalog
    health = next((c for c in catalog if c.get("id") == "health" or "api/health" in (c.get("url") or "")), None)
    if health and not health.get("ok"):
        alerts.append("API Health rot")
        if repair:
            result = _restart_snack_api()
            repairs.append({"action": "restart_snack_api", **result})
            # Re-check
            health2 = _probe(CATALOG[0][1], want_json=True)
            checks["health_after_repair"] = health2
            if health2.get("ok"):
                alerts = [a for a in alerts if a != "API Health rot"]
            else:
                alerts.append("API Health nach Restart weiter rot")

    for c in catalog:
        if not c.get("ok"):
            alerts.append(f"Surface {c.get('id')}: {', '.join(c.get('issues') or []) or c.get('detail')}")

    ssl_info = _ssl_days_left()
    checks["ssl"] = ssl_info
    if not ssl_info.get("ok"):
        alerts.append(ssl_info.get("detail") or "SSL Problem")

    wa = _whatsapp_simple()
    checks["whatsapp"] = wa
    if wa.get("alert"):
        alerts.append(wa.get("detail") or "WhatsApp nicht bereit")

    dual = _dual_snapshot()
    checks["dual"] = dual
    if not dual.get("ok"):
        for a in dual.get("alerts") or [dual.get("detail")]:
            if not a:
                continue
            s = str(a)[:160]
            # Lokaler Lauf ohne SSH ist kein Alarm
            if "ssh_disabled" in s.lower() or "ssh disabled" in s.lower():
                continue
            alerts.append(s)

    res = _resource_snapshot()
    checks["resource"] = res
    if res.get("actions"):
        repairs.append({"action": "resource", "detail": "; ".join(res["actions"])})
    for iss in res.get("issues") or []:
        if iss.get("level") == "critical":
            alerts.append(iss.get("detail") or iss.get("id"))

    # Score
    surface_ok = all(c.get("ok") for c in catalog)
    critical_open = [
        a
        for a in alerts
        if not a.startswith("WhatsApp")  # WA = Setup, kein Infra-Crash
    ]
    alleskönner_score = 100
    if not surface_ok:
        alleskönner_score -= 40
    if critical_open:
        alleskönner_score -= min(40, 10 * len(critical_open))
    if wa.get("alert"):
        alleskönner_score -= 10
    if not ssl_info.get("ok"):
        alleskönner_score -= 15
    alleskönner_score = max(0, alleskönner_score)

    status = "green" if alleskönner_score >= 80 and not critical_open else (
        "yellow" if alleskönner_score >= 50 else "red"
    )

    result = {
        "ok": status != "red",
        "status": status,
        "score": alleskönner_score,
        "as_of": _now(),
        "agent": "ops_guardian",
        "alerts": alerts,
        "repairs": repairs,
        "checks": checks,
        "safe_fixes": list(SAFE_FIXES),
        "alert_only": list(ALERT_ONLY),
        "honest": (
            "Alleskönner = maximaler sicherer Auto-Fix + eine klare Meldung. "
            "Keine Meta-Tokens kaufen, keine Domains, kein Blind-Auth-Retry."
        ),
    }
    result["markdown"] = _markdown(result)

    _save_state(result)

    if mail or force_mail:
        # Mail nur bei gelb/rot oder force; WhatsApp-only = max 1x / 24h über fingerprint
        should = force_mail or status in ("yellow", "red") or bool(repairs)
        if should:
            mailed = _maybe_mail(result, force=force_mail)
            result["mail"] = mailed

    return result


def _markdown(data: dict[str, Any]) -> str:
    lines = [
        f"# Ops-Guardian {data.get('as_of')}",
        f"Status: **{data.get('status')}** · Score {data.get('score')}/100",
        "",
        "## Alerts",
    ]
    alerts = data.get("alerts") or []
    if alerts:
        lines += [f"- {a}" for a in alerts]
    else:
        lines.append("- keine")
    lines += ["", "## Repairs"]
    repairs = data.get("repairs") or []
    if repairs:
        for r in repairs:
            lines.append(f"- {r.get('action')}: {r.get('detail') or r}")
    else:
        lines.append("- keine")
    lines += [
        "",
        "## Surfaces",
    ]
    for c in (data.get("checks") or {}).get("surfaces") or []:
        mark = "OK" if c.get("ok") else "FAIL"
        lines.append(f"- [{mark}] {c.get('id')} {c.get('status')} {c.get('url')}")
    wa = (data.get("checks") or {}).get("whatsapp") or {}
    lines += ["", f"## WhatsApp: {wa.get('detail')}", "", data.get("honest") or ""]
    return "\n".join(lines)


def _save_state(data: dict[str, Any]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        slim = {k: v for k, v in data.items() if k != "markdown"}
        STATE_PATH.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_state() -> dict[str, Any]:
    if not STATE_PATH.is_file():
        return {"ok": False, "error": "Noch kein Guardian-Lauf", "path": str(STATE_PATH)}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"ok": False, "error": str(e)}


def _maybe_mail(data: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    try:
        from watchdog_cabinets import can_alert, record_alert, fingerprint
    except Exception:
        can_alert = lambda *a, **k: True  # noqa: E731
        record_alert = lambda *a, **k: None  # noqa: E731

        def fingerprint(parts):  # type: ignore
            return "fp"

    fp = fingerprint([data.get("status"), "|".join(data.get("alerts") or [])])
    key = f"ops_guardian_{fp}"
    if not force and not can_alert(key, cooldown_hours=4):
        return {"ok": True, "skipped": True, "detail": "Cooldown – gleiche Meldung schon gesendet"}
    try:
        from agency_mail import send_html_email

        to = (os.getenv("AGENCY_OWNER_EMAIL") or "").strip()
        if not to:
            try:
                from agency_mail import _read_secrets

                sec = _read_secrets()
                to = (sec.get("AGENCY_OWNER_EMAIL") or sec.get("AGENCY_SMTP_USER") or "").strip()
            except Exception:
                to = ""
        if not to:
            return {"ok": False, "error": "AGENCY_OWNER_EMAIL fehlt"}
        subject = f"[Guardian {data.get('status')}] Score {data.get('score')} · Webschmiede"
        text = data.get("markdown") or json.dumps(data.get("alerts"), ensure_ascii=False)
        html = f"<pre style='font-family:ui-sans-serif,system-ui'>{text.replace('<', '&lt;')}</pre>"
        send_html_email(to=to, subject=subject, html=html, text=text)
        record_alert(key)
        return {"ok": True, "to": to, "subject": subject}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def status() -> dict[str, Any]:
    st = load_state()
    st["definition"] = {
        "safe_fixes": list(SAFE_FIXES),
        "alert_only": list(ALERT_ONLY),
        "honest": "Kein magischer Alleskönner. Maximaler Auto-Fix im erlaubten Rahmen.",
    }
    return st

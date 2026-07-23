"""Google Business / Review-Link im Kunden-Onboarding."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

KUNDEN_DIR = Path(os.getenv("KUNDEN_DIR", Path(__file__).resolve().parents[1] / "kunden"))

_URL_RE = re.compile(r"^https?://", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(kid: str) -> tuple[dict, Path] | None:
    kid = (kid or "").upper().strip()
    if not kid or not KUNDEN_DIR.is_dir():
        return None
    for p in KUNDEN_DIR.glob("*.json"):
        if p.name.startswith(kid):
            return json.loads(p.read_text(encoding="utf-8")), p
    return None


def _save(k: dict, path: Path) -> None:
    path.write_text(json.dumps(k, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _secrets() -> dict[str, str]:
    try:
        from agency_mail import _read_secrets

        return _read_secrets()
    except Exception:
        return {}


def default_google_block() -> dict:
    return {
        "status": "open",
        "review_url": "",
        "owner_email": "",
        "place_id": "",
        "location_name": "",
        "manager_invited": False,
        "oauth_connected": False,
        "auto_reply_enabled": False,
        "notes": "",
        "updated_at": "",
    }


def resolve_google(k: dict, env_review_url: str = "") -> dict:
    base = default_google_block()
    raw = k.get("google") or {}
    base.update({kk: vv for kk, vv in raw.items() if vv is not None})
    if not base.get("review_url") and env_review_url:
        base["review_url"] = env_review_url
        if base.get("status") == "open":
            base["status"] = "review_url_set"
    # derive status
    if base.get("oauth_connected"):
        base["status"] = "oauth_connected"
    elif base.get("manager_invited"):
        base["status"] = "manager_invited"
    elif base.get("review_url"):
        base["status"] = "review_url_set"
    return base


def payload_for_onboarding(k: dict, env_review_url: str = "") -> dict:
    g = resolve_google(k, env_review_url)
    return {
        "ok": True,
        "status": g.get("status") or "open",
        "review_url": g.get("review_url") or "",
        "owner_email": g.get("owner_email") or "",
        "place_id": g.get("place_id") or "",
        "location_name": g.get("location_name") or "",
        "manager_invited": bool(g.get("manager_invited")),
        "oauth_connected": bool(g.get("oauth_connected")),
        "auto_reply_enabled": bool(g.get("auto_reply_enabled")),
        "notes": g.get("notes") or "",
        "agency_manager_email": (
            os.getenv("AGENCY_GOOGLE_MANAGER_EMAIL")
            or _secrets().get("AGENCY_GOOGLE_MANAGER_EMAIL")
            or os.getenv("AGENCY_OWNER_EMAIL")
            or _secrets().get("AGENCY_OWNER_EMAIL")
            or "info@digitalehandwerkskunst.de"
        ),
        "howto": {
            "no_password": "Geben Sie uns niemals Ihr Google-Passwort. Zugang läuft über Einladung oder späteren Google-Login-Button.",
            "manager": (
                "Schnellster Weg: Im Google Unternehmensprofil unter Nutzer "
                "unsere Agency-Mail als Manager einladen. Danach können wir Bewertungen lesen und antworten."
            ),
            "review_link": (
                "Bewertungslink finden: Mit dem Google-Konto einloggen, das das Unternehmensprofil verwaltet. "
                "Auf Google nach „Snack House Yassine“ (bzw. Ihrem Laden) suchen → Profil verwalten. "
                "Dann „Um Rezensionen bitten“ / „Mehr Rezensionen erhalten“ / „Ask for reviews“. "
                "Dort Link kopieren (manchmal g.page/r/… oder maps.app.goo.gl/…). "
                "Alternativ: business.google.com → Ihr Standort → Rezensionen → Um Rezensionen bitten."
            ),
            "oauth_later": (
                "Später: Button „Mit Google verbinden“. Sie melden sich bei Google an und erlauben den Zugriff. "
                "Wir speichern nur Tokens, kein Passwort. Auto-Antworten mit Keywords kommen danach."
            ),
        },
    }


def save_google(kid: str, data: dict) -> dict:
    loaded = _load(kid)
    if not loaded:
        return {"ok": False, "error": "Kunde nicht gefunden"}
    k, path = loaded
    g = resolve_google(k)

    review_url = (data.get("review_url") or "").strip()
    owner_email = (data.get("owner_email") or "").strip()
    place_id = (data.get("place_id") or "").strip()
    location_name = (data.get("location_name") or "").strip()
    notes = (data.get("notes") or "").strip()
    manager_invited = bool(data.get("manager_invited"))

    if review_url and not _URL_RE.match(review_url):
        return {"ok": False, "error": "Bewertungslink muss mit https:// beginnen"}

    if owner_email and "@" not in owner_email:
        return {"ok": False, "error": "Bitte eine gültige E-Mail angeben"}

    g["review_url"] = review_url
    g["owner_email"] = owner_email
    g["place_id"] = place_id
    g["location_name"] = location_name
    g["notes"] = notes
    g["manager_invited"] = manager_invited
    g["updated_at"] = _now()

    if g.get("oauth_connected"):
        g["status"] = "oauth_connected"
    elif manager_invited:
        g["status"] = "manager_invited"
    elif review_url:
        g["status"] = "review_url_set"
    else:
        g["status"] = "open"

    k["google"] = g
    # sync env-style for portal followups if set in kunden
    pts = list(k.get("offene_punkte") or [])
    pts = [p for p in pts if "google" not in p.lower() and "bewertung" not in p.lower()]
    if g["status"] == "open":
        pts.append("Google Unternehmensprofil: Bewertungslink + Manager-Einladung")
    elif g["status"] == "review_url_set":
        pts.append("Google: Manager-Einladung an WebSchmiede noch offen")
    k["offene_punkte"] = pts

    k.setdefault("agency_history", []).append(
        {
            "at": _now(),
            "action": "google_onboarding",
            "detail": f"status={g['status']} review={'ja' if review_url else 'nein'} manager={manager_invited}",
        }
    )
    _save(k, path)

    mail_info = _notify_owner(k, g)
    return {"ok": True, "google": payload_for_onboarding(k), "mail": mail_info}


def _notify_owner(k: dict, g: dict) -> dict:
    sec = _secrets()
    to = (os.getenv("AGENCY_OWNER_EMAIL") or sec.get("AGENCY_OWNER_EMAIL") or "").strip()
    if not to:
        return {"sent": False, "to": ""}
    kid = k.get("id") or ""
    shop = k.get("name") or ""
    try:
        from agency_mail import send_html_email
        from email_templates import email_shell

        body = f"""
        <p style="margin:0 0 12px;color:#1A1A1A;font-size:15px;">
          <strong>{shop}</strong> ({kid}) hat Google-Daten im Onboarding aktualisiert.
        </p>
        <p style="margin:0 0 8px;color:#1A1A1A;font-size:14px;">Status: <strong>{g.get('status')}</strong></p>
        <p style="margin:0 0 8px;color:#666;font-size:14px;">Bewertungslink: {g.get('review_url') or '–'}</p>
        <p style="margin:0 0 8px;color:#666;font-size:14px;">Inhaber-Mail: {g.get('owner_email') or '–'}</p>
        <p style="margin:0;color:#666;font-size:14px;">Manager eingeladen: {'ja' if g.get('manager_invited') else 'nein'}</p>
        """
        html = email_shell(
            hero_title="Google Onboarding",
            hero_subtitle=f"{kid} · {shop}",
            body_html=body,
            preheader=f"{kid} Google-Daten",
        )
        text = (
            f"{kid} {shop}: Google status={g.get('status')}\n"
            f"review={g.get('review_url')}\nowner={g.get('owner_email')}\n"
            f"manager_invited={g.get('manager_invited')}\n"
        )
        send_html_email(to=to, subject=f"[{kid}] Google Unternehmensprofil", html=html, text=text)
        return {"sent": True, "to": to}
    except Exception as e:
        print(f"[google_onboarding] mail failed: {e}")
        return {"sent": False, "to": to, "error": str(e)[:120]}

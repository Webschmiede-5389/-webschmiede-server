"""Handelsregister / Firmen-Lookup: OpenRegister (günstig/gratis) + North Data (optional)."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "deploy.secrets.local"

COMPANY_RE = re.compile(
    r"([A-ZÄÖÜ][A-Za-zäöüß0-9&\.\-\s]{2,60}(?:GmbH|UG|AG|e\.?\s*K\.?|OHG|GbR))",
    re.MULTILINE,
)

OPENREGISTER_BASE = "https://api.openregister.de"


def _load_secret(key: str) -> str | None:
    env = (os.environ.get(key) or "").strip()
    if env:
        return env
    if SECRETS.exists():
        for line in SECRETS.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    # Server-.env Fallback
    for path in (Path("/root/app/backend/.env"), Path("/root/app/deploy.secrets.local")):
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'") or None
        except Exception:
            continue
    return None


def load_northdata_key() -> str | None:
    return _load_secret("NORTHDATA_API_KEY")


def load_openregister_key() -> str | None:
    return _load_secret("OPENREGISTER_API_KEY") or _load_secret("OPEN_REGISTER_API_KEY")


def extract_company_name(lead: dict, sig: dict) -> str:
    if sig.get("legal_form"):
        person = sig.get("contact_person") or ""
        lf = sig.get("legal_form", "")
        if person and lf:
            return f"{person} {lf}".strip()
    for blob in [lead.get("name", ""), sig.get("title", "")]:
        m = COMPANY_RE.search(blob or "")
        if m:
            return m.group(1).strip()
    return lead.get("name", "")


def _or_headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Accept": "application/json", "Content-Type": "application/json"}


def _pick_best_company(items: list[dict], query: str, city: str = "") -> dict:
    """Besten Treffer wählen (Name + optional Stadt)."""
    q = (query or "").lower()
    city_l = (city or "").lower()
    scored: list[tuple[int, dict]] = []
    for co in items:
        if not isinstance(co, dict):
            continue
        name = (co.get("name") or "").lower()
        addr = co.get("address") if isinstance(co.get("address"), dict) else {}
        cty = (addr.get("city") or co.get("city") or "").lower()
        score = 0
        if q and q in name:
            score += 50
        if "psa marketing" in name:
            score += 40
        for part in q.split():
            if len(part) > 2 and part in name:
                score += 8
        if city_l and city_l in cty:
            score += 30
        if co.get("active") is True:
            score += 5
        scored.append((score, co))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else {}


def lookup_openregister_company(query: str, *, city: str = "") -> dict[str, Any]:
    """OpenRegister Suche (Free: 500 Credits/Monat)."""
    key = load_openregister_key()
    if not key:
        return {"found": False, "error": "missing_key", "source": "openregister"}
    q = f"{query} {city}".strip()
    headers = _or_headers(key)
    try:
        # 1 credit: GET /v0/search/company?query=
        r = requests.get(
            f"{OPENREGISTER_BASE}/v0/search/company",
            params={"query": q, "per_page": 10, "active": "true"},
            headers=headers,
            timeout=25,
        )
        if r.status_code == 401:
            return {"found": False, "error": "OpenRegister Key ungültig", "source": "openregister"}
        if r.status_code == 402:
            return {"found": False, "error": "OpenRegister Credits leer", "source": "openregister"}
        # Fallback: POST /v1/search/company (10 credits)
        if not r.ok or not (r.json().get("results") if r.content else None):
            r = requests.post(
                f"{OPENREGISTER_BASE}/v1/search/company",
                headers=headers,
                json={
                    "query": {"value": q},
                    "pagination": {"page": 1, "per_page": 10},
                },
                timeout=25,
            )
            if r.status_code == 401:
                return {"found": False, "error": "OpenRegister Key ungültig", "source": "openregister"}
            if r.status_code == 402:
                return {"found": False, "error": "OpenRegister Credits leer", "source": "openregister"}
        if not r.ok:
            return {"found": False, "error": f"http_{r.status_code}", "source": "openregister"}
        data = r.json() if r.content else {}
        items = data.get("results") or []
        if not items:
            return {"found": False, "source": "openregister", "query": q}
        co = _pick_best_company(items, query, city)
        if not co:
            return {"found": False, "source": "openregister", "query": q}
        name = co.get("name") or query
        cid = co.get("company_id") or co.get("id") or ""
        managers = _openregister_company_managers(key, cid)
        addr = co.get("address") if isinstance(co.get("address"), dict) else {}
        return {
            "found": True,
            "company_name": name,
            "company_id": cid,
            "managers": managers[:8],
            "register_id": co.get("register_number") or "",
            "register_type": co.get("register_type") or "",
            "register_court": co.get("register_court") or "",
            "city": addr.get("city") or city,
            "purpose": (co.get("purpose") or "")[:240],
            "source": "openregister",
            "openregister_url": f"https://openregister.de/company/{cid}" if cid else "",
        }
    except requests.RequestException as e:
        return {"found": False, "error": str(e)[:80], "source": "openregister"}


def _openregister_company_managers(key: str, company_id: str) -> list[str]:
    if not company_id:
        return []
    try:
        r = requests.get(
            f"{OPENREGISTER_BASE}/v1/company/{company_id}",
            headers=_or_headers(key),
            timeout=25,
        )
        if not r.ok:
            return []
        data = r.json() if r.content else {}
        managers: list[str] = []
        for m in (
            data.get("representation")
            or data.get("representatives")
            or data.get("managers")
            or []
        ):
            if not isinstance(m, dict):
                if isinstance(m, str) and m.strip():
                    managers.append(m.strip())
                continue
            if m.get("end_date"):
                continue
            n = m.get("name") or ""
            if not n:
                np = m.get("natural_person") if isinstance(m.get("natural_person"), dict) else {}
                fn = (np.get("first_name") or "").strip()
                ln = (np.get("last_name") or "").strip()
                n = f"{fn} {ln}".strip()
            role = m.get("role") or m.get("position") or ""
            if n:
                managers.append(f"{n}" + (f" ({role})" if role else ""))
        return managers
    except requests.RequestException:
        return []


def lookup_openregister_person(name: str) -> dict[str, Any]:
    """Personensuche inkl. Holdings."""
    key = load_openregister_key()
    if not key:
        return {"found": False, "error": "missing_key", "source": "openregister"}
    person = (name or "").strip()
    if not person:
        return {"found": False, "error": "empty_name", "source": "openregister"}
    headers = _or_headers(key)
    try:
        r = requests.post(
            f"{OPENREGISTER_BASE}/v1/search/person",
            headers=headers,
            json={
                "query": {"value": person},
                "pagination": {"page": 1, "per_page": 5},
            },
            timeout=25,
        )
        if r.status_code == 401:
            return {"found": False, "error": "OpenRegister Key ungültig", "source": "openregister"}
        if r.status_code == 402:
            return {"found": False, "error": "OpenRegister Credits leer", "source": "openregister"}
        if not r.ok:
            return {"found": False, "error": f"http_{r.status_code}", "source": "openregister"}
        data = r.json() if r.content else {}
        items = data.get("results") or []
        if not items:
            return {"found": False, "source": "openregister", "query": person}
        p0 = items[0] if isinstance(items[0], dict) else {}
        pid = p0.get("id") or ""
        holdings: list[dict[str, str]] = []
        if pid:
            try:
                rh = requests.get(
                    f"{OPENREGISTER_BASE}/v1/person/{pid}/holdings",
                    headers=headers,
                    timeout=25,
                )
                if rh.ok:
                    hd = rh.json() if rh.content else {}
                    for h in hd.get("holdings") or []:
                        if isinstance(h, dict) and h.get("name"):
                            holdings.append(
                                {
                                    "name": h.get("name") or "",
                                    "role": h.get("relation_type") or "",
                                    "city": "",
                                    "company_id": h.get("company_id") or "",
                                }
                            )
            except requests.RequestException:
                pass
        return {
            "found": True,
            "person_name": p0.get("name") or person,
            "person_id": pid,
            "city": p0.get("city") or "",
            "holdings": holdings[:25],
            "source": "openregister",
        }
    except requests.RequestException as e:
        return {"found": False, "error": str(e)[:80], "source": "openregister"}


def lookup_northdata(company: str, city: str, api_key: str) -> dict:
    """North Data Universal Search API (kostenpflichtig, ab ~500 €/Monat)."""
    url = "https://www.northdata.de/_api/search/v1/universal"
    params = {"query": f"{company} {city}".strip(), "domain": "company", "limit": 3}
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=20)
        if r.status_code == 401:
            return {"found": False, "error": "North Data API Key ungültig"}
        data = r.json()
        items = data.get("results") or data.get("companies") or []
        if not items:
            return {"found": False, "source": "northdata"}
        co = items[0]
        managers = []
        for m in co.get("managers") or co.get("relatedPersons") or []:
            managers.append(m.get("name") or m.get("title", ""))
        founded = co.get("founded") or co.get("registerDate") or ""
        return {
            "found": True,
            "company_name": co.get("name") or company,
            "managers": [x for x in managers if x][:5],
            "founded": str(founded)[:10],
            "register_id": co.get("registerId") or co.get("register") or "",
            "source": "northdata",
            "northdata_url": co.get("northDataUrl") or f"https://www.northdata.de/?q={company}",
        }
    except requests.RequestException as e:
        return {"found": False, "error": str(e)[:80], "source": "northdata"}


def lookup_public_hint(company: str, city: str) -> dict:
    """Kostenlose Deep-Links (kein Scraping-Lock-in)."""
    q = f"{company} {city}".strip()
    return {
        "found": False,
        "source": "manual",
        "northdata_url": f"https://www.northdata.de/?q={requests.utils.quote(q)}",
        "handelsregister_url": "https://www.handelsregister.de/rp_web/welcome.xhtml",
        "openregister_signup": "https://openregister.de/",
        "hint": (
            "Kein API-Key. Für Automatik: OPENREGISTER_API_KEY (Free 500 Credits/Monat) "
            "oder NORTHDATA_API_KEY (teuer). Bis dahin Northdata/Handelsregister manuell."
        ),
    }


def lookup_company(company: str, city: str = "") -> dict[str, Any]:
    """Beste verfügbare Quelle: OpenRegister → North Data → Links."""
    company = (company or "").strip()
    city = (city or "").strip()
    if not company:
        return {"found": False, "error": "empty_company"}
    or_key = load_openregister_key()
    if or_key:
        hit = lookup_openregister_company(company, city=city)
        if hit.get("found"):
            return hit
        if hit.get("error") not in ("missing_key",):
            # weiter versuchen
            pass
    nd = load_northdata_key()
    if nd:
        hit = lookup_northdata(company, city, nd)
        if hit.get("found"):
            return hit
    hint = lookup_public_hint(company, city)
    hint["tried"] = {
        "openregister": bool(or_key),
        "northdata": bool(nd),
    }
    return hint


def lookup_person(name: str) -> dict[str, Any]:
    """Person → Mandate. OpenRegister wenn Key da, sonst Northdata-Personenlink."""
    name = (name or "").strip()
    if not name:
        return {"found": False, "error": "empty_name"}
    if load_openregister_key():
        hit = lookup_openregister_person(name)
        if hit.get("found"):
            return hit
    return {
        "found": False,
        "source": "manual",
        "person_name": name,
        "northdata_url": f"https://www.northdata.de/{requests.utils.quote(name)}",
        "hint": "OPENREGISTER_API_KEY setzen für automatische Personen-/Holding-Suche.",
    }


def enrich_lead_register(lead: dict, sig: dict, api_key: str | None) -> dict:
    city = ""
    if lead.get("address"):
        parts = [p.strip() for p in lead["address"].split(",")]
        for p in reversed(parts):
            if re.search(r"\d{5}", p):
                city = re.sub(r"^\d{5}\s*", "", p).strip()
                break
    company = extract_company_name(lead, sig)
    # Prefer OpenRegister even if only Northdata key was passed historically
    reg = lookup_company(company, city)
    if reg.get("found"):
        return reg
    if api_key and company and not reg.get("found"):
        reg2 = lookup_northdata(company, city, api_key)
        if reg2.get("found"):
            return reg2
    hint = lookup_public_hint(company, city)
    if sig.get("contact_person"):
        hint["impressum_manager"] = sig["contact_person"]
    return hint


def enrich_leads_register(leads: list[dict], cfg: dict, *, max_checks: int = 25) -> int:
    if not cfg.get("register", {}).get("enabled", True):
        return 0
    api_key = load_northdata_key()
    priority = sorted(leads, key=lambda l: -l.get("score", 0))
    done = 0
    for lead in priority[:max_checks]:
        sig = lead.setdefault("signals", {})
        if sig.get("register_checked"):
            continue
        reg = enrich_lead_register(lead, sig, api_key)
        sig["register"] = reg
        sig["register_checked"] = True
        if reg.get("managers"):
            sig["register_managers"] = reg["managers"]
        done += 1
        time.sleep(0.2 if (api_key or load_openregister_key()) else 0.05)
    return done


def readiness() -> dict[str, Any]:
    return {
        "openregister": bool(load_openregister_key()),
        "northdata": bool(load_northdata_key()),
        "recommendation": (
            "OpenRegister Free (500 Credits/Monat) für Agency-Alltag. "
            "North Data API erst ab ~500 €/Monat sinnvoll."
        ),
        "signup_openregister": "https://openregister.de/",
        "signup_northdata": "https://www.northdata.com/_data",
    }

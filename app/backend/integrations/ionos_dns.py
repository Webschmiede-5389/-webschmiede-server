"""IONOS Hosting DNS API (Präfix + Secret → X-API-Key).

Hinweis: GET /zones/{id}/records liefert oft 401.
Records kommen über GET /zones/{id} (eingebettet). Updates: PUT .../records/{id}.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


API = "https://api.hosting.ionos.com/dns/v1"


def _secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        from agency_mail import _read_secrets

        out.update(_read_secrets())
    except Exception:
        pass
    roots = [
        Path("/root/app"),
        Path(__file__).resolve().parents[3],
    ]
    for root in roots:
        for name in ("ionos-api.local.txt", "deploy.secrets.local"):
            path = root / name
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def api_key(secrets: dict[str, str] | None = None) -> str:
    sec = secrets if secrets is not None else _secrets()
    prefix = (sec.get("IONOS_API_PREFIX") or os.getenv("IONOS_API_PREFIX") or "").strip()
    secret = (sec.get("IONOS_API_SECRET") or os.getenv("IONOS_API_SECRET") or "").strip()
    if not prefix:
        return ""
    if "." in prefix and not secret:
        return prefix
    if not secret:
        return ""
    return f"{prefix}.{secret}"


def _request(method: str, path: str, key: str, body: dict | list | None = None) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "X-API-Key": key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw[:300]}
        return e.code, parsed


def list_zones(key: str | None = None) -> list[dict]:
    k = key or api_key()
    if not k:
        return []
    code, data = _request("GET", "/zones", k)
    if code != 200 or not isinstance(data, list):
        return []
    return data


def find_zone(domain: str, key: str | None = None) -> dict | None:
    domain = domain.lower().rstrip(".")
    for z in list_zones(key):
        name = (z.get("name") or "").lower().rstrip(".")
        if name == domain:
            return z
    return None


def get_zone_detail(zone_id: str, key: str) -> dict:
    code, data = _request("GET", f"/zones/{zone_id}", key)
    if code != 200 or not isinstance(data, dict):
        return {}
    return data


def point_domain_to_ip(domain: str, ip: str, *, secrets: dict | None = None) -> dict:
    """Set A @, www, cal, yassine, muster, voice, * to ip."""
    k = api_key(secrets)
    if not k:
        return {"ok": False, "error": "IONOS_API_PREFIX/SECRET fehlen"}
    zone = find_zone(domain, k)
    if not zone:
        return {"ok": False, "error": f"Zone {domain} nicht bei IONOS DNS gefunden"}
    zid = zone["id"]
    detail = get_zone_detail(zid, k)
    records = detail.get("records") or []
    if not records:
        return {"ok": False, "error": "Keine Records in Zone-Details"}

    hosts = ("@", "www", "cal", "yassine", "muster", "voice", "*")

    def fqdn(host: str) -> str:
        return domain if host == "@" else f"{host}.{domain}"

    wanted = {fqdn(h).lower(): fqdn(h) for h in hosts}
    a_by_name = {
        (r.get("name") or "").lower(): r
        for r in records
        if (r.get("type") or "").upper() == "A"
    }
    changed: list[str] = []

    for lower, name in wanted.items():
        existing = a_by_name.get(lower)
        payload = {
            "disabled": False,
            "type": "A",
            "name": name,
            "content": ip,
            "ttl": 300,
            "prio": 0,
        }
        if existing:
            if (existing.get("content") or "") == ip:
                continue
            rid = existing["id"]
            code, _ = _request("PUT", f"/zones/{zid}/records/{rid}", k, payload)
            if code in (200, 201):
                changed.append(name)
        else:
            code, _ = _request("POST", f"/zones/{zid}/records", k, [payload])
            if code in (200, 201):
                changed.append(name)

    return {"ok": True, "domain": domain, "ip": ip, "zone_id": zid, "changed": changed}

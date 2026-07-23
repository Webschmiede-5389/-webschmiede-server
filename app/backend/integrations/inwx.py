"""INWX DomRobot JSON-RPC: Domain-Kauf + DNS (A-Records).

Secrets (deploy.secrets.local / Agency Setup):
  INWX_USER, INWX_PASSWORD
  INWX_CONTACT_ID   — Handle für Registrant/Admin/Tech/Billing (einmal im INWX-Panel anlegen)
  INWX_OTE=1        — optional Test-API

Docs: https://www.inwx.com/en/help/apidoc
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API_LIVE = "https://api.domrobot.com/jsonrpc/"
API_OTE = "https://api.ote.domrobot.com/jsonrpc/"

DEFAULT_NS = ("ns.inwx.de", "ns2.inwx.de", "ns3.inwx.eu")


def _read_secrets() -> dict[str, str]:
    try:
        from agency_mail import _read_secrets

        return _read_secrets()
    except Exception:
        pass
    for path in (
        Path("/root/app/deploy.secrets.local"),
        Path(__file__).resolve().parents[3] / "deploy.secrets.local",
    ):
        if not path.exists():
            continue
        out: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            out[k.strip()] = v.strip()
        return out
    return {}


class InwxError(RuntimeError):
    def __init__(self, message: str, *, code: int | None = None, raw: Any = None):
        super().__init__(message)
        self.code = code
        self.raw = raw


class InwxClient:
    def __init__(
        self,
        user: str | None = None,
        password: str | None = None,
        *,
        ote: bool | None = None,
        secrets: dict[str, str] | None = None,
    ):
        sec = secrets if secrets is not None else _read_secrets()
        self.user = user or sec.get("INWX_USER") or os.getenv("INWX_USER", "")
        self.password = password or sec.get("INWX_PASSWORD") or os.getenv("INWX_PASSWORD", "")
        if ote is None:
            ote = (sec.get("INWX_OTE") or os.getenv("INWX_OTE", "")).lower() in ("1", "true", "yes")
        self.api = API_OTE if ote else API_LIVE
        self.contact_id = int(sec.get("INWX_CONTACT_ID") or os.getenv("INWX_CONTACT_ID") or "0")
        self._cookie: str | None = None
        self._req_id = 0

    def configured(self) -> bool:
        return bool(self.user and self.password)

    def _call(self, method: str, params: dict | None = None) -> dict:
        if not self.configured():
            raise InwxError("INWX_USER / INWX_PASSWORD fehlen")
        self._req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._req_id,
        }
        headers = {"Content-Type": "application/json"}
        if self._cookie:
            headers["Cookie"] = self._cookie
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.api, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                cookie = resp.headers.get("Set-Cookie")
                if cookie:
                    self._cookie = cookie.split(";")[0]
                body = json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise InwxError(f"HTTP {e.code}: {raw[:300]}", code=e.code) from e
        except Exception as e:
            raise InwxError(str(e)[:200]) from e

        result = body.get("result") or {}
        code = result.get("code")
        if code not in (1000, 1001, None) and method != "account.login":
            msg = result.get("msg") or result.get("reason") or str(result)[:200]
            raise InwxError(msg, code=code if isinstance(code, int) else None, raw=result)
        return result

    def login(self) -> dict:
        result = self._call(
            "account.login",
            {"user": self.user, "pass": self.password, "lang": "en"},
        )
        code = result.get("code")
        if code not in (1000, 1001):
            raise InwxError(result.get("msg") or "Login fehlgeschlagen", code=code, raw=result)
        return result

    def ensure_login(self) -> None:
        if not self._cookie:
            self.login()

    def check_domain(self, domain: str) -> dict:
        self.ensure_login()
        result = self._call("domain.check", {"domain": domain})
        data = result.get("resData") or result
        domains = data.get("domain") or []
        if isinstance(domains, dict):
            domains = [domains]
        row = domains[0] if domains else {}
        avail = str(row.get("avail", row.get("status", ""))).lower()
        available = avail in ("1", "true", "available", "free")
        return {
            "domain": domain,
            "available": available,
            "raw": row,
            "price": row.get("price") or row.get("registration_price"),
        }

    def register_domain(self, domain: str, *, years: int = 1, ns: list[str] | None = None) -> dict:
        self.ensure_login()
        if not self.contact_id:
            raise InwxError("INWX_CONTACT_ID fehlt (Kontakt-Handle im INWX-Panel anlegen)")
        ns = list(ns or DEFAULT_NS)
        cid = self.contact_id
        params = {
            "domain": domain,
            "period": years,
            "registrant": cid,
            "admin": cid,
            "tech": cid,
            "billing": cid,
            "ns": ns,
        }
        result = self._call("domain.create", params)
        return {"ok": True, "domain": domain, "result": result}

    def create_zone(self, domain: str, *, ns: list[str] | None = None) -> dict:
        self.ensure_login()
        ns = list(ns or DEFAULT_NS)
        try:
            return self._call(
                "nameserver.create",
                {"domain": domain, "type": "MASTER", "ns": ns},
            )
        except InwxError as e:
            if e.code in (2302, 2303) or "exist" in str(e).lower():
                return {"code": 1000, "msg": "zone exists", "skipped": True}
            raise

    def list_records(self, domain: str) -> list[dict]:
        self.ensure_login()
        result = self._call("nameserver.info", {"domain": domain})
        data = result.get("resData") or {}
        recs = data.get("record") or []
        if isinstance(recs, dict):
            recs = [recs]
        return list(recs)

    def upsert_a_record(self, domain: str, name: str, ip: str, *, ttl: int = 300) -> dict:
        self.ensure_login()
        host = "" if name in ("", "@") else name
        fqdn = domain if not host else f"{host}.{domain}"
        existing = self.list_records(domain)
        for rec in existing:
            rtype = (rec.get("type") or "").upper()
            rname = (rec.get("name") or "").rstrip(".")
            if rtype != "A":
                continue
            if rname in (fqdn, host, name, f"{host}.{domain}" if host else domain):
                rid = rec.get("id")
                if rid:
                    return self._call(
                        "nameserver.updateRecord",
                        {"id": int(rid), "content": ip, "ttl": ttl},
                    )
        return self._call(
            "nameserver.createRecord",
            {
                "domain": domain,
                "type": "A",
                "content": ip,
                "name": host,
                "ttl": ttl,
            },
        )

    def point_web_to_ip(self, domain: str, ip: str) -> dict:
        self.create_zone(domain)
        apex = self.upsert_a_record(domain, "@", ip)
        www = self.upsert_a_record(domain, "www", ip)
        return {"ok": True, "domain": domain, "ip": ip, "apex": apex, "www": www}

    def set_nameservers(self, domain: str, nameservers: list[str]) -> dict:
        """Registrar-NS umstellen (z. B. auf Cloudflare)."""
        self.ensure_login()
        ns = [n.strip().rstrip(".") for n in nameservers if n.strip()]
        if len(ns) < 2:
            raise InwxError("Mindestens 2 Nameserver nötig")
        return self._call("domain.update", {"domain": domain, "ns": ns})


def test_connection(secrets: dict[str, str] | None = None) -> dict:
    try:
        c = InwxClient(secrets=secrets)
        if not c.configured():
            return {"ok": False, "error": "INWX_USER / INWX_PASSWORD nicht gesetzt"}
        c.login()
        return {
            "ok": True,
            "message": "INWX Login OK",
            "ote": c.api == API_OTE,
            "contact_id": c.contact_id or None,
        }
    except InwxError as e:
        return {"ok": False, "error": str(e), "code": e.code}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def purchase_and_point(
    domain: str,
    origin_ip: str,
    *,
    years: int = 1,
    secrets: dict | None = None,
    via_cloudflare: bool = True,
) -> dict:
    """Kauf bei INWX. Standard: DNS/WAF über Cloudflare (Proxy), NS umstellen."""
    c = InwxClient(secrets=secrets)
    if not c.configured():
        return {"status": "pending_agency", "message": "INWX Zugangsdaten fehlen"}
    try:
        check = c.check_domain(domain)
        if check.get("available"):
            reg = c.register_domain(domain, years=years)
            purchase_status = "purchased"
            purchase_msg = f"{domain} bei INWX registriert"
        else:
            reg = None
            purchase_status = "dns_updated"
            purchase_msg = f"{domain} war nicht frei zum Neukauf"

        cf_info = None
        if via_cloudflare:
            try:
                from integrations.cloudflare_protect import provision_customer_domain

                cf_info = provision_customer_domain(domain, origin_ip, secrets=secrets)
                if cf_info.get("ok") and cf_info.get("name_servers"):
                    try:
                        c.set_nameservers(domain, cf_info["name_servers"])
                        purchase_msg += "; Cloudflare NS gesetzt, Proxy/WAF an"
                    except InwxError as e:
                        purchase_msg += (
                            f"; Cloudflare Zone OK, NS manuell setzen: {cf_info['name_servers']} ({e})"
                        )
                elif not cf_info.get("ok"):
                    purchase_msg += f"; Cloudflare fehlgeschlagen: {cf_info.get('error')}"
                    # Fallback: INWX DNS
                    dns = c.point_web_to_ip(domain, origin_ip)
                    return {
                        "status": purchase_status,
                        "message": purchase_msg,
                        "registration": reg,
                        "dns": dns,
                        "cloudflare": cf_info,
                        "check": check,
                    }
            except Exception as e:
                purchase_msg += f"; Cloudflare Fehler: {e}"
                dns = c.point_web_to_ip(domain, origin_ip)
                return {
                    "status": purchase_status,
                    "message": purchase_msg,
                    "registration": reg,
                    "dns": dns,
                    "check": check,
                }
        else:
            dns = c.point_web_to_ip(domain, origin_ip)
            return {
                "status": purchase_status,
                "message": f"{purchase_msg}, DNS → {origin_ip}",
                "registration": reg,
                "dns": dns,
                "check": check,
            }

        return {
            "status": purchase_status,
            "message": purchase_msg,
            "registration": reg,
            "cloudflare": cf_info,
            "check": check,
            "origin": origin_ip,
        }
    except InwxError as e:
        return {"status": "failed", "message": str(e), "code": e.code, "raw": e.raw}

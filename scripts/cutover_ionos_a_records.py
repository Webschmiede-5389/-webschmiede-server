#!/usr/bin/env python3
"""IONOS Cutover via GET /zones/{id} (Records eingebettet) + PUT /records/{id}."""
from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import _read_file_secrets

DOMAIN = "digitalehandwerkskunst.de"
API = "https://api.hosting.ionos.com/dns/v1"
HOSTS = ("@", "www", "cal", "yassine", "muster", "voice", "*")


def load_key() -> tuple[str, str]:
    sec = _read_file_secrets()
    for path in (ROOT / "ionos-api.local.txt",):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            sec[k.strip()] = v.strip()
    prefix = (sec.get("IONOS_API_PREFIX") or "").strip()
    secret = (sec.get("IONOS_API_SECRET") or "").strip()
    ip = (sec.get("WEB_HOST") or "").strip()
    if not prefix or not secret:
        raise SystemExit("IONOS Keys fehlen")
    if not ip:
        raise SystemExit("WEB_HOST fehlt")
    return f"{prefix}.{secret}", ip


def call(method: str, path: str, key: str, body=None):
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
            parsed = {"raw": raw[:400]}
        return e.code, parsed


def fqdn(host: str) -> str:
    if host == "@":
        return DOMAIN
    return f"{host}.{DOMAIN}"


def resolve(name: str) -> str:
    try:
        return socket.gethostbyname(name)
    except OSError:
        return "?"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    key, ip = load_key()
    dry = "--dry-run" in sys.argv
    print(f"Ziel-IP: {ip}")

    code, zones = call("GET", "/zones", key)
    if code != 200:
        print(f"Zones fehlgeschlagen HTTP {code}: {zones}")
        return 1
    zone_meta = next(
        (z for z in zones if (z.get("name") or "").lower().rstrip(".") == DOMAIN),
        None,
    )
    if not zone_meta:
        print("Zone nicht gefunden")
        return 1
    zid = zone_meta["id"]

    code, zone = call("GET", f"/zones/{zid}", key)
    if code != 200:
        print(f"Zone-Details HTTP {code}: {zone}")
        return 1

    recs = zone.get("records") or []
    print(f"Zone {DOMAIN} Records gesamt: {len(recs)}")
    a_recs = [r for r in recs if (r.get("type") or "").upper() == "A"]
    for r in a_recs:
        print(f"  A {r.get('name')} = {r.get('content')}")

    wanted = {fqdn(h): ip for h in HOSTS}
    changed: list[str] = []
    missing: list[str] = []

    by_name = {(r.get("name") or "").lower(): r for r in a_recs}

    for name, new_ip in wanted.items():
        r = by_name.get(name.lower())
        if not r:
            missing.append(name)
            if dry:
                print(f"  [dry] CREATE {name} -> {new_ip}")
                continue
            payload = [
                {
                    "disabled": False,
                    "type": "A",
                    "name": name,
                    "content": new_ip,
                    "ttl": 300,
                    "prio": 0,
                }
            ]
            c2, body = call("POST", f"/zones/{zid}/records", key, payload)
            print(f"  POST {name} HTTP {c2} {str(body)[:100]}")
            if c2 in (200, 201):
                changed.append(name)
            continue

        if (r.get("content") or "") == new_ip:
            print(f"  OK schon {name}")
            continue

        rid = r.get("id")
        if not rid:
            print(f"  FEHLER kein id fuer {name}")
            continue

        payload = {
            "disabled": False,
            "type": "A",
            "name": r.get("name"),
            "content": new_ip,
            "ttl": int(r.get("ttl") or 300),
            "prio": int(r.get("prio") or 0),
        }
        if dry:
            print(f"  [dry] PUT {name}: {r.get('content')} -> {new_ip}")
            continue

        c2, body = call("PUT", f"/zones/{zid}/records/{rid}", key, payload)
        ok = c2 in (200, 201)
        print(f"  PUT {name}: {r.get('content')} -> {new_ip} HTTP {c2} {'OK' if ok else body}")
        if ok:
            changed.append(name)
        else:
            # Fallback: ganze Zone PUT mit geaenderten Records
            print("  versuche Zone-PUT Fallback…")
            new_records = []
            for x in recs:
                item = {
                    "name": x.get("name"),
                    "type": x.get("type"),
                    "content": x.get("content"),
                    "ttl": x.get("ttl") or 3600,
                    "disabled": bool(x.get("disabled")),
                }
                if x.get("prio") is not None:
                    item["prio"] = x.get("prio")
                if (x.get("id") == rid) or (
                    (x.get("type") or "").upper() == "A"
                    and (x.get("name") or "").lower() == name.lower()
                ):
                    item["content"] = new_ip
                    item["ttl"] = 300
                new_records.append(item)
            c3, body3 = call(
                "PUT",
                f"/zones/{zid}",
                key,
                {"name": DOMAIN, "records": new_records},
            )
            print(f"  Zone-PUT HTTP {c3} {str(body3)[:150]}")
            if c3 in (200, 201):
                changed.append(name)
                # refresh recs for next iteration
                code, zone = call("GET", f"/zones/{zid}", key)
                recs = zone.get("records") or [] if code == 200 else recs
                a_recs = [rr for rr in recs if (rr.get("type") or "").upper() == "A"]
                by_name = {(rr.get("name") or "").lower(): rr for rr in a_recs}

    print(f"Geaendert: {changed}")
    if missing and not dry:
        print(f"Neu angelegt / fehlend war: {missing}")

    print("DNS-Check (kann Minuten brauchen):")
    for h in HOSTS:
        name = fqdn(h) if h != "*" else f"wildcard-test.{DOMAIN}"
        print(f"  {name} -> {resolve(name)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

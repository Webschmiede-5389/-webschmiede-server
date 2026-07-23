#!/usr/bin/env python3
"""Find Hetzner server by public IP; with --delete power-off + delete (irreversible)."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import _read_file_secrets

API = "https://api.hetzner.cloud/v1"
TARGET_IP = "204.168.170.97"
# Safety: never touch these
PROTECTED = {"167.233.150.230", "88.198.170.156"}


def api(method: str, path: str, token: str, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw[:400]}
        return e.code, parsed


def server_ips(server: dict) -> list[str]:
    ips = []
    pub = (server.get("public_net") or {}).get("ipv4") or {}
    if pub.get("ip"):
        ips.append(pub["ip"])
    for net in server.get("private_net") or []:
        if net.get("ip"):
            ips.append(net["ip"])
    return ips


def find_by_ip(token: str, ip: str) -> dict | None:
    code, data = api("GET", "/servers", token)
    if code != 200:
        raise SystemExit(f"Hetzner servers list HTTP {code}: {data}")
    for s in data.get("servers") or []:
        if ip in server_ips(s):
            return s
    return None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    sec = _read_file_secrets()
    token = (sec.get("HETZNER_API_TOKEN") or "").strip()
    if not token:
        print("HETZNER_API_TOKEN fehlt")
        return 1

    do_delete = "--delete" in sys.argv
    ip = TARGET_IP
    for a in sys.argv[1:]:
        if a.startswith("--ip="):
            ip = a.split("=", 1)[1].strip()

    if ip in PROTECTED:
        print(f"ABBRUCH: {ip} ist geschuetzt (neuer Web/Auto)")
        return 2

    print(f"Suche Server mit IP {ip} …")
    srv = find_by_ip(token, ip)
    if not srv:
        print("Kein Server mit dieser IP gefunden (schon geloescht?)")
        # list all for overview
        code, data = api("GET", "/servers", token)
        for s in data.get("servers") or []:
            print(f"  - {s.get('name')} id={s.get('id')} ips={server_ips(s)} status={s.get('status')}")
        return 0 if not do_delete else 1

    sid = srv["id"]
    name = srv.get("name")
    status = srv.get("status")
    typ = ((srv.get("server_type") or {}).get("name"))
    loc = ((srv.get("datacenter") or {}).get("location") or {}).get("name")
    print(f"Gefunden: name={name} id={sid} type={typ} loc={loc} status={status} ips={server_ips(srv)}")

    if not do_delete:
        print("Nur Anzeige. Zum Loeschen: python scripts/hetzner_delete_by_ip.py --delete")
        return 0

    # Power off first if running
    if status == "running":
        print("Power off …")
        code, body = api("POST", f"/servers/{sid}/actions/poweroff", token)
        print(f"  poweroff HTTP {code}")
        for _ in range(30):
            time.sleep(2)
            c2, s2 = api("GET", f"/servers/{sid}", token)
            st = (s2.get("server") or {}).get("status")
            print(f"  status={st}")
            if st in ("off", "stopping"):
                if st == "off":
                    break
        time.sleep(3)

    print("DELETE server …")
    code, body = api("DELETE", f"/servers/{sid}", token)
    print(f"  delete HTTP {code} {body if code >= 400 else 'OK'}")
    if code not in (200, 204):
        return 1

    # verify gone
    time.sleep(2)
    again = find_by_ip(token, ip)
    print("Noch vorhanden:" if again else "Server weg (IP nicht mehr in Liste).")
    if again:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

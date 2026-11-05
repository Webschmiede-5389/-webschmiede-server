"""Dual-CX43 Infra (web + auto, Nuernberg): Topology, Health, Cross-Backup-Hinweise."""
from __future__ import annotations

import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOPOLOGY = {
    "region": "Nuernberg, DE (Hetzner)",
    "not": "Kein Helsinki als Live-Standort",
    "iso27001_provider": True,
    "roles": {
        "web": {
            "name": "web-01neu (Gesicht & Daten)",
            "hosts": ["snack-api", "nginx", "static dashboards", "SQLite orders.db", "B2B-Uploads"],
            "env_host_key": "WEB_HOST",
        },
        "auto": {
            "name": "auto-01neu (Gehirn & Kette)",
            "hosts": ["n8n", "Cron/Watchdogs", "Voice-Demo soweit aktiv"],
            "env_host_key": "AUTO_HOST",
        },
    },
    "isolation_claim": (
        "Verarbeitung (n8n auf auto) und Kunden-API/Uploads (web) sind auf getrennten Hosts. "
        "Noch kein dedizierter Postgres-db-01 – SQLite auf web. Keine falsche Enterprise-DB-Isolation behaupten."
    ),
    "router": (
        "Oeffentlicher Router: https://digitalehandwerkskunst.de/api/agency/router "
        "(nginx web -> snack-api). n8n auf auto wird ueber /n8n/ von web geproxyt."
    ),
}

RAM_WARN = int(os.getenv("DUAL_RAM_WARN", "85"))
DISK_WARN = int(os.getenv("DUAL_DISK_WARN", "80"))

SECRETS_CANDIDATES = (
    Path("/root/app/deploy.secrets.local"),
    Path(__file__).resolve().parents[2] / "deploy.secrets.local",
)


def topology() -> dict[str, Any]:
    return {
        "ok": True,
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **TOPOLOGY,
    }


def _read_secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in SECRETS_CANDIDATES:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
        break
    return out


def _role_target(role: str, sec: dict[str, str]) -> tuple[str, str, str]:
    user = sec.get("SERVER_USER") or "root"
    if role == "web":
        host = sec.get("WEB_HOST") or ""
        password = sec.get("WEB_PASSWORD") or sec.get("SERVER_PASSWORD") or ""
    elif role == "auto":
        host = sec.get("AUTO_HOST") or ""
        password = sec.get("AUTO_PASSWORD") or sec.get("SERVER_PASSWORD") or ""
    else:
        host = sec.get("SERVER_HOST") or ""
        password = sec.get("SERVER_PASSWORD") or ""
    return host, user, password


def _local_ips() -> set[str]:
    ips: set[str] = set()
    try:
        out = subprocess.check_output(
            "hostname -I 2>/dev/null || true",
            shell=True,
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
        for part in out.split():
            ips.add(part.strip())
    except Exception:
        pass
    try:
        ips.add(socket.gethostbyname(socket.gethostname()))
    except Exception:
        pass
    return {i for i in ips if i and not i.startswith("127.")}


def _running_on_role(role: str, sec: dict[str, str], local: dict[str, Any]) -> bool:
    host, _, _ = _role_target(role, sec)
    if host and host in _local_ips():
        return True
    guess = local.get("role_guess") or ""
    # Service-Heuristik: nur auf dem jeweiligen Host (nicht vom Laptop)
    if role == "web" and guess == "web" and local.get("snack_api") == "active":
        return True
    if role == "auto" and guess == "auto" and local.get("n8n") == "active":
        return True
    return False


def _as_role_probe(role: str, local: dict[str, Any], host: str) -> dict[str, Any]:
    alerts = list(local.get("alerts") or [])
    snack = local.get("snack_api") or "inactive"
    n8n = local.get("n8n") or "inactive"
    # role-spezifische Alerts neu bewerten
    alerts = [a for a in alerts if "snack-api" not in a and "n8n" not in a]
    if role == "web" and snack != "active":
        alerts.append("snack-api nicht active")
    if role == "auto" and n8n != "active":
        alerts.append("n8n nicht active")
    return {
        "ok": len(alerts) == 0,
        "role": role,
        "host": host or "local",
        "hostname": local.get("hostname") or "",
        "ram_mb_total": local.get("ram_mb_total") or 0,
        "ram_mb_used": local.get("ram_mb_used") or 0,
        "ram_pct": local.get("ram_pct") or 0,
        "disk_pct": local.get("disk_pct") or 0,
        "load1": local.get("load1") or "",
        "snack_api": snack,
        "n8n": n8n,
        "alerts": alerts,
        "source": "local",
    }


def probe_local() -> dict[str, Any]:
    def sh(cmd: str) -> str:
        try:
            return subprocess.check_output(
                cmd, shell=True, text=True, timeout=15, stderr=subprocess.DEVNULL
            ).strip()
        except Exception:
            return ""

    hostname = sh("hostname")
    mem = sh("free -m | awk '/Mem:/{printf \"%s %s %.1f\", $2,$3,($3/$2)*100}'").split()
    disk = sh("df -P / | awk 'NR==2{print $5}'").rstrip("%")
    load = sh("cat /proc/loadavg | awk '{print $1}'")
    snack = sh("systemctl is-active snack-api 2>/dev/null || echo inactive")
    n8n = sh("systemctl is-active n8n 2>/dev/null || echo inactive")
    ram_total = int(float(mem[0])) if len(mem) > 0 and mem[0] else 0
    ram_used = int(float(mem[1])) if len(mem) > 1 and mem[1] else 0
    ram_pct = float(mem[2]) if len(mem) > 2 else 0.0
    disk_pct = float(disk) if disk else 0.0
    role = "auto" if n8n == "active" and snack != "active" else "web" if snack == "active" else "unknown"
    alerts = []
    if ram_pct >= RAM_WARN:
        alerts.append(f"RAM {ram_pct:.0f}% >= {RAM_WARN}%")
    if disk_pct >= DISK_WARN:
        alerts.append(f"Disk {disk_pct:.0f}% >= {DISK_WARN}%")
    if role == "web" and snack != "active":
        alerts.append("snack-api nicht active")
    if role == "auto" and n8n != "active":
        alerts.append("n8n nicht active")
    return {
        "hostname": hostname,
        "role_guess": role,
        "ram_mb_total": ram_total,
        "ram_mb_used": ram_used,
        "ram_pct": ram_pct,
        "disk_pct": disk_pct,
        "load1": load,
        "snack_api": snack,
        "n8n": n8n,
        "alerts": alerts,
        "ok": len(alerts) == 0,
    }


def probe_via_ssh(role: str) -> dict[str, Any]:
    sec = _read_secrets()
    host, user, password = _role_target(role, sec)
    if not host or not password:
        return {"ok": False, "role": role, "error": "host/password fehlen in deploy.secrets.local"}
    try:
        import paramiko
    except Exception as e:
        return {"ok": False, "role": role, "error": f"paramiko:{e}"}

    client = paramiko.SSHClient()
    try:
        # Fail closed: only server keys pre-approved in known_hosts are trusted.
        # load_system_host_keys() reads the service account's ~/.ssh/known_hosts.
        client.load_system_host_keys()
        pinned_hosts = os.getenv("DUAL_SSH_KNOWN_HOSTS", "").strip()
        if pinned_hosts:
            # If explicitly configured, a missing/unreadable pin file is an error.
            client.load_host_keys(pinned_hosts)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(
            host,
            username=user,
            password=password,
            timeout=20,
            look_for_keys=False,
            allow_agent=False,
            banner_timeout=20,
        )
        # Einzeiler – Heredoc ueber Paramiko ist unzuverlaessig
        remote = (
            "hostname; "
            "free -m | awk '/^Mem:/{printf \"%s %s %.1f\\n\", $2,$3,($3/$2)*100}'; "
            "df -P / | awk 'NR==2{gsub(/%/,\"\"); print $5}'; "
            "awk '{print $1}' /proc/loadavg; "
            "s=$(systemctl is-active snack-api 2>/dev/null); echo ${s:-inactive}; "
            "s=$(systemctl is-active n8n 2>/dev/null); echo ${s:-inactive}"
        )
        _, stdout, stderr = client.exec_command(remote, timeout=40)
        raw = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace")[:200]
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if len(lines) < 6:
            return {"ok": False, "role": role, "host": host, "error": raw[:120] or err or "parse"}
        hostname = lines[0]
        mem = lines[1].split()
        disk_pct = float(lines[2])
        load1 = lines[3]
        snack = lines[4]
        n8n = lines[5]
        ram_total = int(float(mem[0])) if len(mem) > 0 else 0
        ram_used = int(float(mem[1])) if len(mem) > 1 else 0
        ram_pct = float(mem[2]) if len(mem) > 2 else 0.0
        alerts = []
        if ram_pct >= RAM_WARN:
            alerts.append(f"RAM {ram_pct:.0f}%")
        if disk_pct >= DISK_WARN:
            alerts.append(f"Disk {disk_pct:.0f}%")
        if role == "web" and snack != "active":
            alerts.append("snack-api down")
        if role == "auto" and n8n != "active":
            alerts.append("n8n down")
        return {
            "ok": len(alerts) == 0,
            "role": role,
            "host": host,
            "hostname": hostname,
            "ram_mb_total": ram_total,
            "ram_mb_used": ram_used,
            "ram_pct": ram_pct,
            "disk_pct": disk_pct,
            "load1": load1,
            "snack_api": snack,
            "n8n": n8n,
            "alerts": alerts,
            "source": "ssh",
        }
    except Exception as e:
        return {"ok": False, "role": role, "host": host, "error": str(e)[:200]}
    finally:
        client.close()


def dual_status(*, use_ssh: bool = True) -> dict[str, Any]:
    """Auf web/auto: lokale Seite ohne SSH, Peer per SSH. Vom Laptop: beide per SSH."""
    sec = _read_secrets()
    local = probe_local()
    web_host, _, _ = _role_target("web", sec)
    auto_host, _, _ = _role_target("auto", sec)
    on_web = _running_on_role("web", sec, local)
    on_auto = _running_on_role("auto", sec, local)

    if on_web and not on_auto:
        web = _as_role_probe("web", local, web_host)
        auto = (
            probe_via_ssh("auto")
            if use_ssh
            else {"ok": False, "role": "auto", "error": "ssh_disabled"}
        )
    elif on_auto and not on_web:
        auto = _as_role_probe("auto", local, auto_host)
        web = (
            probe_via_ssh("web")
            if use_ssh
            else {"ok": False, "role": "web", "error": "ssh_disabled"}
        )
    elif use_ssh:
        web = probe_via_ssh("web")
        auto = probe_via_ssh("auto")
    else:
        web = (
            _as_role_probe("web", local, web_host)
            if local.get("role_guess") == "web"
            else {"ok": False, "role": "web", "error": "ssh_disabled"}
        )
        auto = (
            _as_role_probe("auto", local, auto_host)
            if local.get("role_guess") == "auto"
            else {"ok": False, "role": "auto", "error": "ssh_disabled"}
        )

    alerts = []
    for side in (web, auto):
        for a in side.get("alerts") or []:
            alerts.append(f"{side.get('role')}: {a}")
        if side.get("error"):
            alerts.append(f"{side.get('role')}: {side['error']}")
    return {
        "ok": len(alerts) == 0 and bool(web.get("ok")) and bool(auto.get("ok")),
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "topology": TOPOLOGY,
        "local": local,
        "web": web,
        "auto": auto,
        "alerts": alerts,
        "customer_pitch_safe": (
            "Systeme auf getrennten Hetzner-Servern in Nuernberg (DE), Anbieter ISO 27001. "
            "Automation (n8n) und Kunden-Portal/API auf getrennten Hosts. "
            "Kein Helsinki. SQLite auf dem Web-Host bis Postgres-Trigger greifen."
        ),
    }


def markdown_status(data: dict[str, Any] | None = None) -> str:
    data = data or dual_status()
    lines = [
        "# Dual-CX43 Status",
        f"Stand: {data.get('as_of')}",
        f"Gesamt: {'OK' if data.get('ok') else 'ALARM'}",
        "",
        "## Topology",
        f"- Region: {TOPOLOGY['region']}",
        f"- {TOPOLOGY['isolation_claim']}",
        f"- Router: {TOPOLOGY['router']}",
        "",
        "## web",
        json.dumps(data.get("web") or {}, ensure_ascii=False, indent=2),
        "",
        "## auto",
        json.dumps(data.get("auto") or {}, ensure_ascii=False, indent=2),
        "",
        "## Alerts",
        *[f"- {a}" for a in (data.get("alerts") or ["keine"])],
        "",
        "## Pitch (sicher)",
        data.get("customer_pitch_safe") or "",
    ]
    return "\n".join(lines)

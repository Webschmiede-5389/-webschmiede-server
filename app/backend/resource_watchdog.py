"""RAM, Disk, CPU und Dienste prüfen, bei Grenzwerten mailen."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

STATE_FILE = Path("/var/lib/webschmiede/resource-alert-state.json")

RAM_WARN = int(os.getenv("RESOURCE_RAM_WARN", "85"))
RAM_CRIT = int(os.getenv("RESOURCE_RAM_CRIT", "92"))
DISK_WARN = int(os.getenv("RESOURCE_DISK_WARN", "80"))
DISK_CRIT = int(os.getenv("RESOURCE_DISK_CRIT", "90"))
LOAD_PER_CPU_WARN = float(os.getenv("RESOURCE_LOAD_WARN", "1.2"))
ALERT_COOLDOWN_HOURS = int(os.getenv("RESOURCE_ALERT_COOLDOWN_HOURS", "4"))

SERVICES = ("snack-api", "n8n")


def _load_env() -> None:
    env_path = Path("/root/app/backend/.env")
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def owner_email() -> str:
    owner = os.getenv("AGENCY_OWNER_EMAIL", "").strip()
    if owner:
        return owner
    try:
        from agency_mail import _read_secrets

        values = _read_secrets()
        return (
            values.get("AGENCY_OWNER_EMAIL")
            or values.get("AGENCY_SMTP_USER")
            or "info@digitalehandwerkskunst.de"
        ).strip()
    except Exception:
        return "info@digitalehandwerkskunst.de"


def _read_mem_percent() -> tuple[float, dict]:
    info: dict[str, int] = {}
    with open("/proc/meminfo", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                info[parts[0].rstrip(":")] = int(parts[1])
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", info.get("MemFree", 0))
    if total <= 0:
        return 0.0, info
    used_pct = 100.0 * (total - avail) / total
    return used_pct, {"total_kb": total, "avail_kb": avail}


def _read_disk_percent(path: str = "/") -> tuple[float, str]:
    out = subprocess.check_output(["df", "-P", path], text=True, timeout=10)
    line = out.strip().splitlines()[-1]
    parts = line.split()
    pct = int(parts[4].rstrip("%"))
    return float(pct), parts[0]


def _read_load() -> tuple[float, int]:
    load1, _, _ = os.getloadavg()
    try:
        cpus = os.cpu_count() or 1
    except Exception:
        cpus = 1
    return load1, cpus


def _service_active(name: str) -> bool:
    proc = subprocess.run(
        ["systemctl", "is-active", name],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.stdout.strip() == "active"


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _should_alert(state: dict, key: str) -> bool:
    last = state.get(key)
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    return datetime.now() - last_dt > timedelta(hours=ALERT_COOLDOWN_HOURS)


def stop_calcom() -> bool:
    compose = Path("/opt/calcom/docker-compose.yml")
    if not compose.is_file():
        return False
    proc = subprocess.run(
        ["docker", "compose", "-f", str(compose), "ps", "-q"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=compose.parent,
    )
    if not proc.stdout.strip():
        return False
    subprocess.run(
        ["docker", "compose", "-f", str(compose), "stop"],
        timeout=120,
        cwd=compose.parent,
        check=False,
    )
    return True


def collect_metrics() -> dict:
    ram_pct, mem = _read_mem_percent()
    disk_pct, disk_dev = _read_disk_percent("/")
    load1, cpus = _read_load()
    load_ratio = load1 / max(cpus, 1)
    services = {name: _service_active(name) for name in SERVICES}
    return {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "ram_percent": round(ram_pct, 1),
        "ram_avail_mb": round(mem.get("avail_kb", 0) / 1024, 1),
        "disk_percent": disk_pct,
        "disk_device": disk_dev,
        "load_1m": round(load1, 2),
        "cpus": cpus,
        "load_ratio": round(load_ratio, 2),
        "services": services,
    }


def evaluate(metrics: dict) -> list[dict]:
    issues: list[dict] = []
    ram = metrics["ram_percent"]
    if ram >= RAM_CRIT:
        issues.append({"id": "ram_crit", "level": "critical", "detail": f"RAM {ram}% (kritisch ab {RAM_CRIT}%)"})
    elif ram >= RAM_WARN:
        issues.append({"id": "ram_warn", "level": "warn", "detail": f"RAM {ram}% (Warnung ab {RAM_WARN}%)"})

    disk = metrics["disk_percent"]
    if disk >= DISK_CRIT:
        issues.append({"id": "disk_crit", "level": "critical", "detail": f"Disk {disk}% auf {metrics['disk_device']}"})
    elif disk >= DISK_WARN:
        issues.append({"id": "disk_warn", "level": "warn", "detail": f"Disk {disk}% auf {metrics['disk_device']}"})

    if metrics["load_ratio"] >= LOAD_PER_CPU_WARN:
        issues.append({
            "id": "load_warn",
            "level": "warn",
            "detail": f"Load {metrics['load_1m']} bei {metrics['cpus']} CPUs",
        })

    for name, active in metrics["services"].items():
        if not active:
            issues.append({"id": f"service_down_{name}", "level": "critical", "detail": f"Dienst {name} nicht active"})

    return issues


def send_alert_email(metrics: dict, issues: list[dict], actions: list[str]) -> dict:
    to = owner_email()
    if not to:
        return {"ok": False, "error": "Keine Ziel-E-Mail"}

    from email_templates import email_shell
    from agency_mail import send_html_email

    crit = sum(1 for i in issues if i["level"] == "critical")
    title = "Server: kritische Last" if crit else "Server: Ressourcen-Warnung"
    issue_lines = "".join(f"<li><strong>{i['id']}</strong>: {i['detail']}</li>" for i in issues)
    action_lines = "".join(f"<li>{a}</li>" for a in actions) if actions else "<li>keine</li>"
    svc = ", ".join(f"{k}={'ok' if v else 'AUS'}" for k, v in metrics["services"].items())

    body = f"""
    <p>Der Resource-Watchdog hat Grenzwerte überschritten.</p>
    <ul>
      <li>RAM: {metrics['ram_percent']}% ({metrics['ram_avail_mb']} MB frei)</li>
      <li>Disk: {metrics['disk_percent']}%</li>
      <li>Load: {metrics['load_1m']} / {metrics['cpus']} CPUs</li>
      <li>Dienste: {svc}</li>
    </ul>
    <p><strong>Meldungen:</strong></p><ul>{issue_lines}</ul>
    <p><strong>Auto-Aktionen:</strong></p><ul>{action_lines}</ul>
    <p>Bei anhaltender Last: Cal.com gestoppt lassen, CX-Upgrade planen.</p>
    """
    html = email_shell(
        hero_title=title,
        hero_subtitle=metrics["checked_at"],
        preheader=f"RAM {metrics['ram_percent']}%",
        body_html=body,
    )
    send_html_email(
        to=to,
        subject=f"[Server] {title} (RAM {metrics['ram_percent']}%)",
        html=html,
        text=f"Resource alert: {issues} metrics={metrics} actions={actions}",
    )
    return {"ok": True, "to": to}


def run_watchdog(*, auto_repair: bool = True) -> dict:
    _load_env()
    # Schrank: kein Parallel-Lauf
    try:
        from watchdog_cabinets import flock
    except ImportError:
        flock = None

    def _run() -> dict:
        metrics = collect_metrics()
        issues = evaluate(metrics)
        actions: list[str] = []
        state = _load_state()
        alerts_to_send: list[dict] = []

        for issue in issues:
            key = f"alert_{issue['id']}"
            if _should_alert(state, key):
                alerts_to_send.append(issue)
                state[key] = datetime.now().isoformat(timespec="seconds")

        if auto_repair and metrics["ram_percent"] >= RAM_CRIT:
            if stop_calcom():
                actions.append("Cal.com Container gestoppt (RAM kritisch)")

        if alerts_to_send:
            send_alert_email(metrics, alerts_to_send, actions)
            _save_state(state)
        elif actions:
            send_alert_email(metrics, [{"id": "auto_repair", "level": "warn", "detail": "Auto-Reparatur"}], actions)
            _save_state(state)

        return {
            "ok": not any(i["level"] == "critical" for i in issues),
            "metrics": metrics,
            "issues": issues,
            "actions": actions,
            "alerted": bool(alerts_to_send or actions),
        }

    if flock is None:
        return _run()
    with flock("resource_watchdog", blocking=False) as got:
        if not got:
            return {"ok": True, "skipped": True, "reason": "flock belegt"}
        return _run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resource-Watchdog")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--no-email", action="store_true")
    args = parser.parse_args(argv)

    result = run_watchdog(auto_repair=not args.check_only)
    if args.no_email:
        result["alerted"] = False
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    backend = Path(__file__).resolve().parent
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    raise SystemExit(main())

"""Prüft Nacht-Jobs, repariert automatisch, meldet per E-Mail."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

# (job_id, logfile, Erfolgs-Marker in Logzeile)
NIGHTLY_JOBS = (
    ("akquise_gastro", "/var/log/akquise.log", "done gastro"),
    ("akquise_handwerk", "/var/log/akquise.log", "done handwerk"),
    ("followups", "/var/log/snack-followups.log", '"success"'),
    ("backup", "/var/log/snack-backup.log", "backup ok"),
)

SHELL_SCRIPTS = (
    "/root/app/scripts/akquise_nightly.sh",
    "/root/app/scripts/run_followups.sh",
    "/root/app/scripts/backup_agency.sh",
    "/root/app/scripts/backup_offsite.sh",
    "/root/app/scripts/nightly_watchdog.sh",
)

AKQUISE_TIMEOUT = 7200
JOB_TIMEOUT = 120


def _today() -> str:
    return date.today().isoformat()


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


def _log_has_success_today(log_path: str, marker: str) -> bool:
    if not os.path.isfile(log_path):
        return False
    today = _today()
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if today in line and marker in line:
                    return True
    except OSError:
        return False
    return False


def check_shell_scripts() -> list[dict]:
    bad: list[dict] = []
    for path in SHELL_SCRIPTS:
        if not os.path.isfile(path):
            continue
        proc = subprocess.run(
            ["bash", "-n", path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            bad.append(
                {
                    "job": f"script:{os.path.basename(path)}",
                    "reason": "bash_syntax_error",
                    "detail": (proc.stderr or proc.stdout or "bash -n failed").strip()[:200],
                }
            )
    return bad


def check_nightly_jobs() -> list[dict]:
    failures: list[dict] = []
    hour = datetime.now().hour
    for job_id, log_path, marker in NIGHTLY_JOBS:
        if job_id == "followups" and hour < 10:
            continue
        if not os.path.isfile(log_path):
            failures.append({"job": job_id, "reason": "log_missing", "log": log_path})
            continue
        if not _log_has_success_today(log_path, marker):
            failures.append(
                {
                    "job": job_id,
                    "reason": "no_success_today",
                    "log": log_path,
                    "marker": marker,
                }
            )
    return failures


def normalize_shell_scripts() -> list[str]:
    """CRLF auf allen Shell-Scripts entfernen (präventiv + Reparatur)."""
    fixed: list[str] = []
    for path in SHELL_SCRIPTS:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as f:
                data = f.read()
            normalized = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            if normalized != data:
                with open(path, "wb") as f:
                    f.write(normalized)
                os.chmod(path, 0o755)
                fixed.append(path)
        except OSError:
            continue
    return fixed


def _run_logged(cmd: list[str], log_path: str, timeout: int) -> dict:
    stamp = datetime.now().isoformat(timespec="seconds")
    header = f"===== watchdog repair {stamp} {' '.join(cmd)} =====\n"
    try:
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(header)
            proc = subprocess.run(
                cmd,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                cwd="/root/app" if os.path.isdir("/root/app") else None,
            )
        return {"ok": proc.returncode == 0, "exit_code": proc.returncode}
    except subprocess.TimeoutExpired:
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(f"===== watchdog TIMEOUT after {timeout}s =====\n")
        return {"ok": False, "error": "timeout"}
    except OSError as exc:
        return {"ok": False, "error": str(exc)[:200]}


def repair_job(job_id: str) -> dict:
    """Einzelnen Job nachholen."""
    if job_id == "akquise_gastro":
        return _run_logged(
            ["/bin/bash", "/root/app/scripts/akquise_nightly.sh", "gastro"],
            "/var/log/akquise.log",
            AKQUISE_TIMEOUT,
        )
    if job_id == "akquise_handwerk":
        return _run_logged(
            ["/bin/bash", "/root/app/scripts/akquise_nightly.sh", "handwerk"],
            "/var/log/akquise.log",
            AKQUISE_TIMEOUT,
        )
    if job_id == "backup":
        return _run_logged(
            ["/bin/bash", "/root/app/scripts/backup_agency.sh"],
            "/var/log/snack-backup.log",
            JOB_TIMEOUT,
        )
    if job_id == "followups":
        secret = os.getenv("CRON_SECRET", "").strip()
        if not secret:
            return {"ok": False, "error": "CRON_SECRET fehlt"}
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/cron/followups",
            method="POST",
            headers={
                "X-Cron-Secret": secret,
                "Content-Type": "application/json",
            },
            data=b"{}",
        )
        try:
            with urllib.request.urlopen(req, timeout=JOB_TIMEOUT) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            with open("/var/log/snack-followups.log", "a", encoding="utf-8") as log:
                log.write(f"===== watchdog repair {datetime.now().isoformat()} =====\n{body}\n")
            return {"ok": '"success"' in body or '"success": true' in body, "body": body[:200]}
        except urllib.error.HTTPError as exc:
            return {"ok": False, "error": f"HTTP {exc.code}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}
    return {"ok": False, "error": "unknown job"}


def run_watchdog(*, auto_repair: bool = True, integration_live: bool = False) -> dict:
    _load_env()
    actions: list[dict] = []

    normalized = normalize_shell_scripts()
    if normalized:
        actions.append({"action": "normalize_crlf", "files": normalized})

    initial_script_failures = check_shell_scripts()
    initial_job_failures = check_nightly_jobs()
    initial_failures = initial_script_failures + initial_job_failures

    integration_failures: list[dict] = []
    try:
        from agency_secrets import check_integrations_health

        ih = check_integrations_health(live=integration_live)
        integration_failures = ih.get("failures") or []
    except Exception as exc:
        integration_failures = [{"job": "integration:check", "reason": "exception", "detail": str(exc)[:120]}]

    if auto_repair and initial_failures:
        if initial_script_failures:
            normalize_shell_scripts()
        for failure in list(initial_job_failures):
            job_id = failure["job"]
            if job_id.startswith("script:"):
                continue
            result = repair_job(job_id)
            actions.append({"action": "repair_job", "job": job_id, **result})

    final_script_failures = check_shell_scripts()
    final_job_failures = check_nightly_jobs()
    final_failures = final_script_failures + final_job_failures + integration_failures
    all_initial = initial_failures + integration_failures

    return {
        "ok": not final_failures,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "initial_failures": all_initial,
        "failures": final_failures,
        "actions": actions,
        "repaired_scripts": normalized,
        "retried_jobs": [a["job"] for a in actions if a.get("action") == "repair_job"],
        "integration_live": integration_live,
    }


def send_status_email(result: dict) -> dict:
    to = owner_email()
    if not to:
        return {"ok": False, "error": "Keine Ziel-E-Mail"}

    from email_templates import email_shell
    from agency_mail import send_html_email

    initial = result.get("initial_failures") or []
    final = result.get("failures") or []
    actions = result.get("actions") or []

    if not initial and not actions:
        return {"ok": True, "skipped": True, "reason": "nothing_to_report"}

    if result.get("ok"):
        title = "Nacht-Jobs: Fehler automatisch behoben"
        pre = "Watchdog hat repariert, alles ok"
        intro = "<p>Heute Nacht gab es ein Problem. Der Watchdog hat es automatisch behoben.</p>"
    else:
        title = "Nacht-Jobs: Fehler, bitte prüfen"
        pre = f"{len(final)} Job(s) noch offen"
        intro = "<p>Heute Nacht ist etwas schief gelaufen. Auto-Reparatur hat nicht gereicht.</p>"

    def _items(items: list[dict]) -> str:
        if not items:
            return "<li>keine</li>"
        return "".join(
            f"<li><strong>{f.get('job')}</strong>: {f.get('reason')} "
            f"({f.get('detail') or f.get('log') or f.get('marker') or f.get('error') or ''})</li>"
            for f in items
        )

    action_lines = ""
    if actions:
        action_lines = "<p><strong>Was der Watchdog gemacht hat:</strong></p><ul>"
        for a in actions:
            if a.get("action") == "normalize_crlf":
                action_lines += f"<li>CRLF entfernt: {', '.join(os.path.basename(f) for f in a.get('files', []))}</li>"
            elif a.get("action") == "repair_job":
                status = "ok" if a.get("ok") else f"fehlgeschlagen ({a.get('error') or a.get('exit_code')})"
                action_lines += f"<li>Job {a.get('job')} nachgeholt: {status}</li>"
        action_lines += "</ul>"

    body = f"""
    {intro}
    <p><strong>Erkannt:</strong></p><ul>{_items(initial)}</ul>
    {action_lines}
    <p><strong>Noch offen:</strong></p><ul>{_items(final)}</ul>
    <p>Logs auf dem Server: <code>/var/log/akquise.log</code>, <code>/var/log/nightly-watchdog.log</code></p>
    """
    html = email_shell(
        hero_title=title,
        hero_subtitle=_today(),
        preheader=pre,
        body_html=body,
    )
    send_html_email(
        to=to,
        subject=f"[Server] {title}",
        html=html,
        text=f"Watchdog {_today()}: initial={initial} final={final} actions={actions}",
    )
    return {"ok": True, "to": to}


def purge_old_operational_logs(days: int = 90) -> dict:
    """Löscht alte technische Nachrichten-/Inbox-Logs (nicht Bestellstammdaten)."""
    import sqlite3

    db_path = Path("/root/app/backend/orders.db")
    if not db_path.is_file():
        backend = Path(__file__).resolve().parent
        alt = backend / "orders.db"
        db_path = alt if alt.is_file() else db_path
    if not db_path.is_file():
        return {"ok": False, "error": "orders.db fehlt", "path": str(db_path)}

    cutoff = f"-{int(days)} days"
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        deleted = {}
        for table in ("message_log", "inbox_log"):
            try:
                cur.execute(
                    f"DELETE FROM {table} WHERE created_at < datetime('now', ?)",
                    (cutoff,),
                )
                deleted[table] = cur.rowcount
            except sqlite3.Error as e:
                deleted[table] = f"skip:{e}"
        # Router-Audit: kuerzer behalten (redigiert, aber trotzdem minimal halten)
        try:
            cur.execute(
                "DELETE FROM router_audit WHERE created_at < datetime('now', ?)",
                ("-30 days",),
            )
            deleted["router_audit"] = cur.rowcount
        except sqlite3.Error as e:
            deleted["router_audit"] = f"skip:{e}"
        conn.commit()
        return {"ok": True, "days": days, "deleted": deleted, "path": str(db_path)}
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nacht-Watchdog")
    parser.add_argument("--repair", action="store_true", help="Fehler erkennen und beheben")
    parser.add_argument("--check-only", action="store_true", help="Nur prüfen, nicht reparieren")
    parser.add_argument("--no-email", action="store_true", help="Keine E-Mail senden")
    parser.add_argument("--integration-live", action="store_true", help="SMTP/Stripe/Places live testen")
    args = parser.parse_args(argv)

    auto_repair = not args.check_only
    integration_live = args.integration_live or datetime.now().hour >= 10
    result = run_watchdog(auto_repair=auto_repair, integration_live=integration_live)

    # Operative Log-Retention (Fakt in Datenschutz: 90 Tage)
    try:
        result["log_purge"] = purge_old_operational_logs(90)
        print("log_purge", result["log_purge"])
    except Exception as e:
        result["log_purge"] = {"ok": False, "error": str(e)}
        print("log_purge_err", e)

    # B2B Zero-Retention (Roh-Uploads nach Frist)
    try:
        import sqlite3
        import b2b_portal as b2b_portal_svc

        db_path = Path("/root/app/backend/orders.db")
        if not db_path.is_file():
            alt = Path(__file__).resolve().parent / "orders.db"
            db_path = alt if alt.is_file() else db_path
        if db_path.is_file():
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                result["b2b_purge"] = b2b_portal_svc.purge_expired_jobs(conn)
            finally:
                conn.close()
        else:
            result["b2b_purge"] = {"ok": False, "error": "orders.db fehlt"}
        print("b2b_purge", result["b2b_purge"])
    except Exception as e:
        result["b2b_purge"] = {"ok": False, "error": str(e)}
        print("b2b_purge_err", e)

    if not args.no_email and (result.get("initial_failures") or result.get("actions")):
        alert = send_status_email(result)
        result["alert"] = alert
    elif not args.no_email and not result.get("ok"):
        alert = send_status_email(result)
        result["alert"] = alert

    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    backend = Path(__file__).resolve().parent
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    raise SystemExit(main())

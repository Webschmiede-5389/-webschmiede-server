#!/usr/bin/env python3
"""Branding-Pilot: isoliertes PostgreSQL-Staging für CRM (kein Production).

Nutzt lokalen Windows-Postgres-Service postgresql-crm-parity-16 (:55432).
DB: crm_branding_pilot — eigene Datenbank, keine crm_parity_* / Production.

Usage:
  set CRM_ROOT=…\\crm-branding-pilot-wt
  set CRM_VENV=…\\crm\\.venv\\Scripts\\python.exe
  python scripts/branding_pilot_staging.py ensure-db|migrate|seed|start|stop|health|status
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

WS_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CRM = WS_ROOT.parent / "crm-branding-pilot-wt"
CRM_ROOT = Path(os.environ.get("CRM_ROOT", str(DEFAULT_CRM))).resolve()
EVIDENCE = WS_ROOT / "docs" / "platform-unification" / "evidence" / "step-5"
PORT = int(os.environ.get("BRANDING_PILOT_PORT", "8093"))
BASE = f"http://127.0.0.1:{PORT}"
PG_BIN = Path(
    os.environ.get(
        "CRM_PG_BIN",
        str(Path.home() / "AppData/Local/crm-pg-parity-16/bin"),
    )
)
ADMIN_URL_PASSWORD = os.environ.get("CRM_PG_ADMIN_PASSWORD", "CrmParityLocalOnly_2026!")
DB_NAME = "crm_branding_pilot"
DB_USER = "crm_parity_test"
DB_PASS = os.environ.get("CRM_BRANDING_PILOT_DB_PASS", "crm_parity_test_only_local")
DB_URL = (
    f"postgresql+psycopg://{DB_USER}:{DB_PASS}@127.0.0.1:55432/{DB_NAME}"
)
RUN_DIR = CRM_ROOT / "staging" / "run" / "branding-pilot"
LOG_DIR = CRM_ROOT / "staging" / "logs" / "branding-pilot"
PID_FILE = RUN_DIR / "uvicorn.pid"
ENV_FILE = CRM_ROOT / ".env.branding-pilot"


def die(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def assert_safe() -> None:
    if not CRM_ROOT.exists():
        die(f"CRM_ROOT fehlt: {CRM_ROOT}")
    if "hetzner" in DB_URL.lower() or "digitalehandwerkskunst" in DB_URL.lower():
        die("unsichere DATABASE_URL")
    if "127.0.0.1" not in DB_URL and "localhost" not in DB_URL:
        die("nur localhost erlaubt")
    if DB_NAME not in DB_URL:
        die("falsche DB")


def psql(sql: str, *, db: str = "postgres", user: str = "postgres", password: str | None = None) -> str:
    exe = PG_BIN / ("psql.exe" if sys.platform == "win32" else "psql")
    if not exe.exists():
        die(f"psql fehlt: {exe}")
    env = os.environ.copy()
    env["PGPASSWORD"] = password if password is not None else (
        ADMIN_URL_PASSWORD if user == "postgres" else DB_PASS
    )
    cp = subprocess.run(
        [
            str(exe),
            "-h",
            "127.0.0.1",
            "-p",
            "55432",
            "-U",
            user,
            "-d",
            db,
            "-v",
            "ON_ERROR_STOP=1",
            "-tAc",
            sql,
        ],
        env=env,
        text=True,
        capture_output=True,
    )
    if cp.returncode != 0:
        die(f"psql failed: {cp.stderr or cp.stdout}")
    return (cp.stdout or "").strip()


def venv_python() -> Path:
    override = os.environ.get("CRM_VENV")
    if override:
        p = Path(override)
        if p.exists():
            return p
    for cand in (
        CRM_ROOT.parent / "crm" / ".venv" / "Scripts" / "python.exe",
        CRM_ROOT / ".venv" / "Scripts" / "python.exe",
        CRM_ROOT.parent / "crm" / ".venv" / "bin" / "python",
    ):
        if cand.exists():
            return cand
    return Path(sys.executable)


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        return
    example = CRM_ROOT / ".env.branding-pilot.example"
    if not example.exists():
        die(f"fehlende Env-Vorlage: {example}")
    text = example.read_text(encoding="utf-8").replace("CHANGE_ME", DB_PASS)
    ENV_FILE.write_text(text, encoding="utf-8")
    print(f"PASS wrote {ENV_FILE}")


def cmd_ensure_db() -> dict:
    assert_safe()
    exists = psql(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
    created = False
    if exists != "1":
        psql(f"CREATE DATABASE {DB_NAME} OWNER {DB_USER}")
        psql(f"GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO {DB_USER}")
        created = True
    ver = psql("SELECT version()", db=DB_NAME, user=DB_USER, password=DB_PASS)
    out = {
        "db": DB_NAME,
        "created": created,
        "version": ver.split("\n")[0][:120],
        "port": 55432,
        "host": "127.0.0.1",
    }
    print(f"PASS ensure-db {json.dumps(out, ensure_ascii=False)}")
    return out


def _crm_env() -> dict[str, str]:
    ensure_env_file()
    env = os.environ.copy()
    env["CRM_ENV_FILE"] = str(ENV_FILE)
    env["DATABASE_URL"] = DB_URL
    env["APP_ENV"] = "staging"
    env["PUBLIC_BASE_URL"] = BASE
    env["ALLOW_CREATE_ALL"] = "false"
    env["ALLOW_LEGACY_SCHEMA_ENSURE"] = "false"
    env["CSRF_ENABLED"] = "true"
    env["RATE_LIMIT_ENABLED"] = "false"
    env["SALES_OUTBOUND_ENABLED"] = "false"
    env["OUTBOUND_ENABLED"] = "false"
    env["N8N_ENABLED"] = "false"
    env["SUPERADMIN_EMAIL"] = "branding-pilot@example.local"
    env["SUPERADMIN_PASSWORD"] = "branding-pilot-pass-local"
    env["SUPERADMIN_TENANT_NAME"] = "WebSchmiede Branding Pilot"
    env["SUPERADMIN_TENANT_SLUG"] = "webschmiede-branding-pilot"
    env["SECRET_KEY"] = "branding-pilot-local-only-secret-key!!"
    return env


def cmd_migrate() -> dict:
    assert_safe()
    py = venv_python()
    env = _crm_env()
    # sync URL for alembic (sync driver)
    sync_url = DB_URL  # psycopg works sync + async
    cp = subprocess.run(
        [
            str(py),
            "-c",
            (
                "from alembic.config import Config; from alembic import command; "
                f"cfg=Config(r'{CRM_ROOT / 'alembic.ini'}'); "
                f"cfg.set_main_option('sqlalchemy.url', r'{sync_url}'); "
                "command.upgrade(cfg, 'head'); print('alembic_upgrade_head_ok')"
            ),
        ],
        cwd=str(CRM_ROOT),
        env=env,
        text=True,
        capture_output=True,
    )
    text = (cp.stdout or "") + (cp.stderr or "")
    print(text[-4000:])
    if cp.returncode != 0:
        die("alembic upgrade failed")
    rev = psql(
        "SELECT version_num FROM alembic_version LIMIT 1",
        db=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )
    out = {"alembic": "upgrade_head_ok", "revision": rev, "database_url_host": "127.0.0.1:55432"}
    print(f"PASS migrate {out}")
    return out


def cmd_seed() -> dict:
    assert_safe()
    py = venv_python()
    env = _crm_env()
    seed_py = r'''
import asyncio, os, sys, json
from pathlib import Path
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
ROOT = Path(r"""''' + str(CRM_ROOT).replace("\\", "\\\\") + r'''""")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ["CRM_ENV_FILE"] = str(ROOT / ".env.branding-pilot")
from app.config import reset_settings_cache
reset_settings_cache()
import importlib
import app.config, app.database
importlib.reload(app.config)
importlib.reload(app.database)
import app.models  # noqa
from sqlalchemy import select
from app.auth import hash_password
from app.models import Tenant, User, Company, Campaign, PipelineStage, Contact
from app.services.seed_sales_os import seed_sales_os_for_tenant
from datetime import datetime, timedelta, timezone

async def main():
    SessionLocal = app.database.SessionLocal
    email = os.environ["SUPERADMIN_EMAIL"].lower()
    password = os.environ["SUPERADMIN_PASSWORD"]
    tname = os.environ["SUPERADMIN_TENANT_NAME"]
    tslug = os.environ["SUPERADMIN_TENANT_SLUG"]
    async with SessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.slug == tslug))).scalar_one_or_none()
        if not tenant:
            tenant = Tenant(name=tname, slug=tslug, notify_email=email)
            db.add(tenant)
            await db.flush()
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not user:
            db.add(User(tenant_id=tenant.id, email=email, password_hash=hash_password(password),
                        name="Branding Pilot Admin", role="superadmin"))
        else:
            user.password_hash = hash_password(password)
            user.tenant_id = tenant.id
        await db.commit()
        await seed_sales_os_for_tenant(db, tenant.id)
        camp = (await db.execute(select(Campaign).where(Campaign.tenant_id==tenant.id))).scalars().first()
        co = (await db.execute(select(Company).where(Company.tenant_id==tenant.id, Company.name=="BRANDING PILOT TESTDATA"))).scalar_one_or_none()
        if not co:
            kwargs = dict(
                tenant_id=tenant.id,
                name="BRANDING PILOT TESTDATA",
                industry="Gastronomie",
                city="Mechernich",
                campaign_id=camp.id if camp else None,
                lead_source="branding_pilot",
                legal_basis="art6_1_f",
                next_activity="Pilot-Check",
                next_activity_at=datetime.now(timezone.utc)+timedelta(days=1),
            )
            co = Company(**kwargs)
            db.add(co)
            await db.flush()
            db.add(Contact(tenant_id=tenant.id, company_id=co.id, first_name="Pilot", last_name="Test",
                           email="pilot-contact@example.local"))
        await db.commit()
        print(json.dumps({"tenant_id": tenant.id, "company": "BRANDING PILOT TESTDATA", "admin": email}))

asyncio.run(main())
'''
    cp = subprocess.run([str(py), "-c", seed_py], cwd=str(CRM_ROOT), env=env, text=True, capture_output=True)
    text = (cp.stdout or "") + (cp.stderr or "")
    print(text[-4000:])
    if cp.returncode != 0:
        die("seed failed")
    out = {"seed": "ok", "testdata": "BRANDING PILOT TESTDATA"}
    print(f"PASS seed {out}")
    return out


def cmd_start() -> dict:
    assert_safe()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        old = PID_FILE.read_text(encoding="utf-8").strip()
        print(f"WARN pid-file exists pid={old} — stop first or continue")
    py = venv_python()
    env = _crm_env()
    log_path = LOG_DIR / "uvicorn.log"
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    # Windows + psycopg async: SelectorEventLoop (kein Proactor)
    launcher = (
        "import asyncio, sys; "
        "asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) if sys.platform=='win32' else None; "
        "import uvicorn; "
        f"uvicorn.run('app.main:app', host='127.0.0.1', port={PORT}, loop='asyncio')"
    )
    with log_path.open("a", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [str(py), "-c", launcher],
            cwd=str(CRM_ROOT),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    # wait health
    ok = False
    last = ""
    for _ in range(40):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=2) as r:
                last = r.read().decode("utf-8", errors="replace")
                if r.status == 200:
                    ok = True
                    break
        except Exception as e:
            last = str(e)
    out = {"pid": proc.pid, "url": BASE, "health_ok": ok, "health_body": last[:500], "log": str(log_path)}
    if not ok:
        die(f"health failed: {out}")
    print(f"PASS start {json.dumps(out, ensure_ascii=False)}")
    return out


def cmd_stop() -> dict:
    if not PID_FILE.exists():
        print("PASS stop (no pid-file)")
        return {"stopped": False, "reason": "no_pid"}
    pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception as e:
        print(f"WARN kill: {e}")
    PID_FILE.unlink(missing_ok=True)
    print(f"PASS stop pid={pid}")
    return {"stopped": True, "pid": pid}


def cmd_health() -> dict:
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=5) as r:
            body = r.read().decode("utf-8", errors="replace")
            out = {"ok": r.status == 200, "status": r.status, "body": body[:800], "url": f"{BASE}/health"}
    except urllib.error.URLError as e:
        out = {"ok": False, "error": str(e), "url": f"{BASE}/health"}
    # login page
    try:
        with urllib.request.urlopen(f"{BASE}/login", timeout=5) as r:
            html = r.read().decode("utf-8", errors="replace")
            out["login_status"] = r.status
            out["login_has_webschmiede"] = "WebSchmiede" in html or "Webschmiede" in html
            out["login_has_gold"] = ("#C9A84C" in html) or ("c9a84c" in html.lower())
            out["login_has_orange"] = ("#FF6600" in html) or ("ff6600" in html.lower()) or ("ws-" in html)
    except Exception as e:
        out["login_error"] = str(e)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if not out.get("ok"):
        die("health not ok")
    return out


def cmd_status() -> dict:
    out = {
        "at": utc_now(),
        "crm_root": str(CRM_ROOT),
        "crm_commit": subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(CRM_ROOT), text=True
        ).strip(),
        "db": DB_NAME,
        "port": PORT,
        "pid_file": PID_FILE.exists(),
        "env_file": ENV_FILE.exists(),
    }
    print(json.dumps(out, indent=2))
    return out


def cmd_bootstrap() -> dict:
    """ensure-db → migrate → seed → start → health; write evidence."""
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    report = {
        "at": utc_now(),
        "ensure_db": cmd_ensure_db(),
        "migrate": cmd_migrate(),
        "seed": cmd_seed(),
        "start": cmd_start(),
        "health": cmd_health(),
        "status": cmd_status(),
    }
    path = EVIDENCE / "staging-bootstrap.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"PASS bootstrap evidence={path}")
    return report


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1].strip().lower()
    mapping = {
        "ensure-db": cmd_ensure_db,
        "migrate": cmd_migrate,
        "seed": cmd_seed,
        "start": cmd_start,
        "stop": cmd_stop,
        "health": cmd_health,
        "status": cmd_status,
        "bootstrap": cmd_bootstrap,
    }
    if cmd not in mapping:
        die(f"unknown cmd {cmd}")
    mapping[cmd]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

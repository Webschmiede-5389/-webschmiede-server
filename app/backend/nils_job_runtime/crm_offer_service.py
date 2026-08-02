# -*- coding: utf-8 -*-
"""Nils adapter for CRM offer reads via existing offer_read service.

Isolated DB only (NILS_CRM_DB). No production writes.
"""
from __future__ import annotations

import importlib.util
import os
import sqlite3
from pathlib import Path
from typing import Any

_OFFER_READ = None


def _crm_root() -> Path:
    env = (os.getenv("NILS_CRM_ROOT") or "").strip()
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    # Server layout: /root/app/backend/nils_job_runtime → /root/app/crm-read
    for cand in (
        Path("/root/app/crm-read"),
        Path("/root/app/crm"),
        here.parents[2] / "crm-read",  # …/backend → …/app/crm-read sibling under /root/app
        here.parents[2] / "crm",
    ):
        if (cand / "app" / "services" / "offer_read.py").is_file():
            return cand
    # Dev layout: …/webschmiede-server/app/backend/nils_job_runtime → …/projects/crm
    try:
        cand = here.parents[4] / "crm"
        if (cand / "app" / "services" / "offer_read.py").is_file():
            return cand
    except IndexError:
        pass
    try:
        cand2 = here.parents[5] / "projects" / "crm"
        if (cand2 / "app" / "services" / "offer_read.py").is_file():
            return cand2
    except IndexError:
        pass
    return Path("/root/app/crm-read")


def _load_offer_read():
    global _OFFER_READ
    if _OFFER_READ is not None:
        return _OFFER_READ
    path = _crm_root() / "app" / "services" / "offer_read.py"
    if not path.is_file():
        raise FileNotFoundError(f"CRM offer_read nicht gefunden: {path}")
    spec = importlib.util.spec_from_file_location("crm_offer_read_svc", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Kann offer_read nicht laden: {path}")
    mod = importlib.util.module_from_spec(spec)
    import sys

    sys.modules["crm_offer_read_svc"] = mod
    spec.loader.exec_module(mod)
    _OFFER_READ = mod
    return mod


def crm_db_path() -> Path:
    raw = (os.getenv("NILS_CRM_DB") or "").strip()
    if raw:
        return Path(raw)
    # default isolated test/staging path under agency data
    if os.name == "nt":
        return Path(__file__).resolve().parents[3] / "agency" / "nils-crm-test.db"
    return Path("/var/lib/webschmiede/nils-crm-test.db")


def crm_backend() -> str:
    raw = (os.getenv("NILS_CRM_BACKEND") or "").strip().lower()
    if raw in ("postgres", "postgresql", "pg"):
        return "postgres"
    if raw in ("sqlite", "file"):
        return "sqlite"
    # Auto: URL wins over sqlite file
    if (os.getenv("NILS_CRM_DATABASE_URL") or "").strip():
        return "postgres"
    return "sqlite"


def crm_database_url() -> str:
    raw = (os.getenv("NILS_CRM_DATABASE_URL") or "").strip()
    if not raw:
        return ""
    # SQLAlchemy dialects → libpq/psycopg DSN
    for prefix in (
        "postgresql+psycopg2://",
        "postgresql+psycopg://",
        "postgres+psycopg2://",
        "postgres+psycopg://",
    ):
        if raw.startswith(prefix):
            raw = "postgresql://" + raw[len(prefix) :]
            break
    # Optional host override when Nils runs on host and DB is docker-published
    host_override = (os.getenv("NILS_CRM_PGHOST") or "").strip()
    if host_override and "@" in raw:
        # rewrite host between @ and /
        userpart, _, rest = raw.partition("@")
        _hostport, _, path = rest.partition("/")
        port = ""
        if ":" in host_override:
            host, port = host_override.split(":", 1)
            hostport = f"{host}:{port}"
        else:
            # keep original port if present
            if ":" in _hostport:
                port = _hostport.split(":", 1)[1]
                hostport = f"{host_override}:{port}"
            else:
                hostport = host_override
        raw = f"{userpart}@{hostport}/{path}"
    return raw


def tenant_id() -> int:
    try:
        return int(os.getenv("NILS_CRM_TENANT_ID", "1") or "1")
    except ValueError:
        return 1


class _PgConn:
    """Minimal adapter: ? placeholders → %s, dict-like rows."""

    def __init__(self, dsn: str, *, readonly: bool = True):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as e:  # pragma: no cover
            raise ImportError("psycopg required for NILS_CRM_BACKEND=postgres") from e
        self._readonly = readonly
        self._con = psycopg.connect(dsn, connect_timeout=8, row_factory=dict_row)
        if readonly:
            self._con.execute("SET default_transaction_read_only = on")
        else:
            self._con.execute("SET default_transaction_read_only = off")

    def execute(self, sql: str, params: Any = ()):
        q = sql.replace("?", "%s")
        try:
            cur = self._con.execute(q, tuple(params or ()))
            return _PgCursor(cur)
        except Exception:
            try:
                self._con.rollback()
            except Exception:
                pass
            raise

    def commit(self) -> None:
        if self._readonly:
            raise PermissionError("CRM Postgres connection is read-only")
        self._con.commit()

    def close(self) -> None:
        self._con.close()


class _PgCursor:
    def __init__(self, cur: Any):
        self._cur = cur
        self._rows = None

    def fetchall(self):
        if self._rows is None:
            self._rows = list(self._cur.fetchall())
        return self._rows

    def fetchone(self):
        rows = self.fetchall()
        return rows[0] if rows else None

    def __getitem__(self, idx: int):  # pragma: no cover
        return self.fetchall()[idx]


def probe() -> dict[str, Any]:
    mod = _load_offer_read()
    if crm_backend() == "postgres":
        url = crm_database_url()
        if not url:
            return {
                "ok": False,
                "outcome": "NOT_CONFIGURED",
                "detail": "NILS_CRM_DATABASE_URL fehlt",
            }
        try:
            con = _PgConn(url)
            try:
                n_co = con.execute("SELECT COUNT(*) AS c FROM companies").fetchone()["c"]
                n_of = con.execute("SELECT COUNT(*) AS c FROM offers").fetchone()["c"]
                return {
                    "ok": True,
                    "outcome": "AVAILABLE",
                    "detail": f"CRM Postgres lesbar companies={n_co} offers={n_of}",
                    "companies": int(n_co),
                    "offers": int(n_of),
                    "backend": "postgres",
                }
            finally:
                con.close()
        except Exception as e:
            return {
                "ok": False,
                "outcome": "CONNECTION_FAILED",
                "detail": f"{type(e).__name__}: {e}",
                "backend": "postgres",
            }
    return mod.probe_readable(crm_db_path())


def _connect(*, readonly: bool = True):
    if crm_backend() == "postgres":
        url = crm_database_url()
        if not url:
            raise FileNotFoundError("NILS_CRM_DATABASE_URL fehlt")
        return _PgConn(url, readonly=readonly)
    mod = _load_offer_read()
    path = crm_db_path()
    if not path.is_file() and readonly:
        raise FileNotFoundError(f"CRM-DB nicht erreichbar: {path}")
    con = mod.open_sqlite(path, readonly=readonly)
    # sqlite3 connections already have commit(); ensure attribute for writers
    return con


def search_companies(query: str) -> list[Any]:
    mod = _load_offer_read()
    con = _connect(readonly=True)
    try:
        return mod.search_companies(con, tenant_id=tenant_id(), query=query)
    finally:
        con.close()


def list_offers(company_id: int) -> list[Any]:
    mod = _load_offer_read()
    con = _connect(readonly=True)
    try:
        return mod.list_offers_for_company(
            con, tenant_id=tenant_id(), company_id=company_id
        )
    finally:
        con.close()


def get_offer(offer_id: int) -> Any | None:
    mod = _load_offer_read()
    con = _connect(readonly=True)
    try:
        return mod.get_offer(con, tenant_id=tenant_id(), offer_id=offer_id)
    finally:
        con.close()


def get_offer_by_number(company_id: int | None, offer_number: str) -> Any | None:
    mod = _load_offer_read()
    con = _connect(readonly=True)
    try:
        return mod.get_offer_by_number(
            con,
            tenant_id=tenant_id(),
            company_id=company_id,
            offer_number=offer_number,
        )
    finally:
        con.close()


def list_offers_by_number(offer_number: str) -> list[Any]:
    mod = _load_offer_read()
    con = _connect(readonly=True)
    try:
        return mod.list_offers_by_number(
            con, tenant_id=tenant_id(), offer_number=offer_number
        )
    finally:
        con.close()


def format_offer(offer: Any) -> str:
    return _load_offer_read().format_offer_telegram(offer)


def format_no_offer(company_name: str) -> str:
    return _load_offer_read().format_no_offer(company_name)


def format_offer_choices(offers: list[Any]) -> str:
    return _load_offer_read().format_offer_choice_list(offers)


def format_company_choices(companies: list[Any]) -> str:
    return _load_offer_read().format_company_choice_list(companies)


def seed_isolated_fixture(path: Path | None = None, *, reset: bool = True) -> Path:
    """Create isolated CRM sqlite with MBP Service + offers (no prod).

    Lifecycle rules = Production policy (lifecycle_policy):
    - LEAD/PROSPECT companies have NO customer_number
    - CUSTOMER row (optional contrast) may have a number
    No Sonderlogik nur für Tests.
    """
    mod = _load_offer_read()
    try:
        from nils_job_runtime import crm_language

        pol = crm_language.policy()
    except Exception:
        pol = None
    p = path or crm_db_path()
    if reset and p.exists():
        p.unlink()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                customer_number TEXT DEFAULT '',
                sales_lifecycle TEXT DEFAULT 'PROSPECT',
                lifecycle_status TEXT DEFAULT 'PROSPECT',
                lead_source TEXT DEFAULT 'manual',
                status TEXT DEFAULT 'neu',
                archived_at TEXT,
                industry TEXT DEFAULT '',
                sub_industry TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                company_id INTEGER,
                title TEXT NOT NULL,
                stage_id INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS offers (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                deal_id INTEGER NOT NULL,
                company_id INTEGER,
                offer_number TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                services TEXT,
                setup_price_eur REAL,
                monthly_price_eur REAL,
                status TEXT DEFAULT 'entwurf',
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS agency_customers (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                crm_company_id INTEGER NOT NULL,
                customer_number TEXT,
                lifecycle_status TEXT NOT NULL DEFAULT 'prospect'
            );
            """
        )
        con.execute(
            "INSERT OR REPLACE INTO tenants (id, name, slug) VALUES (1, 'Webschmiede', 'agency')"
        )
        # Prospects / Leads — keine Kundennummer (Policy)
        prospect = (pol.LIFECYCLE_PROSPECT if pol else "PROSPECT")
        lead = (pol.LIFECYCLE_LEAD if pol else "LEAD")
        customer = (pol.LIFECYCLE_CUSTOMER if pol else "CUSTOMER")
        con.execute(
            """
            INSERT INTO companies (
                id, tenant_id, name, customer_number, sales_lifecycle, lead_source, status
            ) VALUES (10, 1, 'MBP Service', '', ?, 'manual', 'neu')
            """,
            (prospect,),
        )
        con.execute(
            """
            INSERT INTO companies (
                id, tenant_id, name, customer_number, sales_lifecycle, lead_source, status
            ) VALUES (11, 1, 'MBP Service West', '', ?, 'manual', 'neu')
            """,
            (prospect,),
        )
        con.execute(
            """
            INSERT INTO companies (
                id, tenant_id, name, customer_number, sales_lifecycle, lead_source, status
            ) VALUES (12, 1, 'MBP Service Ost', '', ?, 'manual', 'neu')
            """,
            (prospect,),
        )
        con.execute(
            """
            INSERT INTO companies (
                id, tenant_id, name, customer_number, sales_lifecycle, lead_source, status
            ) VALUES (20, 1, 'Alpha Reinigung', '', ?, 'manual', 'neu')
            """,
            (prospect,),
        )
        # Optional LEAD without offer (import-like)
        con.execute(
            """
            INSERT INTO companies (
                id, tenant_id, name, customer_number, sales_lifecycle, lead_source, status
            ) VALUES (30, 1, 'Lead Import Demo GmbH', '', ?, 'b2b_import', 'neu')
            """,
            (lead,),
        )
        # True CUSTOMER contrast row (Won path) — only this has a number
        con.execute(
            """
            INSERT INTO companies (
                id, tenant_id, name, customer_number, sales_lifecycle, lead_source, status
            ) VALUES (40, 1, 'Won Customer GmbH', 'KUN001', ?, 'manual', 'gewonnen')
            """,
            (customer,),
        )
        con.execute(
            """
            INSERT INTO agency_customers (
                id, tenant_id, crm_company_id, customer_number, lifecycle_status
            ) VALUES (1, 1, 40, 'KUN001', 'active')
            """
        )
        # Draft prospect (Option A) — no number
        con.execute(
            """
            INSERT INTO agency_customers (
                id, tenant_id, crm_company_id, customer_number, lifecycle_status
            ) VALUES (2, 1, 10, NULL, 'prospect')
            """
        )
        # Digitale Handwerkskunst + ANG-0004 (canary mirror) + ProOffice ohne Angebot
        con.execute(
            """
            INSERT INTO companies (
                id, tenant_id, name, customer_number, sales_lifecycle, lead_source, status
            ) VALUES (50, 1, 'Digitale Handwerkskunst', 'KUN001', ?, 'manual', 'gewonnen')
            """,
            (customer,),
        )
        con.execute(
            """
            INSERT INTO companies (
                id, tenant_id, name, customer_number, sales_lifecycle, lead_source, status
            ) VALUES (51, 1, 'ProOffice Leverkusen', '', ?, 'manual', 'gewonnen')
            """,
            (prospect,),
        )
        # Enrich DHK + ProOffice for customer_read tests
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                company_id INTEGER,
                name TEXT,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                phone TEXT,
                mobile TEXT,
                position TEXT
            )
            """
        )
        for _ddl in (
            "ALTER TABLE companies ADD COLUMN phone TEXT DEFAULT ''",
            "ALTER TABLE companies ADD COLUMN email TEXT DEFAULT ''",
            "ALTER TABLE companies ADD COLUMN website TEXT DEFAULT ''",
            "ALTER TABLE companies ADD COLUMN city TEXT DEFAULT ''",
            "ALTER TABLE companies ADD COLUMN street TEXT DEFAULT ''",
            "ALTER TABLE companies ADD COLUMN postal_code TEXT DEFAULT ''",
            "ALTER TABLE agency_customers ADD COLUMN company_name TEXT DEFAULT ''",
            "ALTER TABLE agency_customers ADD COLUMN contact_name TEXT DEFAULT ''",
            "ALTER TABLE agency_customers ADD COLUMN contact_email TEXT DEFAULT ''",
            "ALTER TABLE agency_customers ADD COLUMN billing_email TEXT DEFAULT ''",
            "ALTER TABLE agency_customers ADD COLUMN lead_recipient_email TEXT DEFAULT ''",
            "ALTER TABLE agency_customers ADD COLUMN onboarding_status TEXT DEFAULT 'not_started'",
            "ALTER TABLE agency_customers ADD COLUMN delivery_status TEXT DEFAULT 'not_started'",
            "ALTER TABLE agency_customers ADD COLUMN product TEXT DEFAULT ''",
            "ALTER TABLE agency_customers ADD COLUMN terms_confirmed INTEGER DEFAULT 0",
            "ALTER TABLE agency_customers ADD COLUMN avv_privacy_status TEXT DEFAULT 'missing'",
        ):
            try:
                con.execute(_ddl)
            except Exception:
                pass
        con.execute(
            "UPDATE companies SET phone=?, email=?, city=?, website=? WHERE id=50",
            ("0221-111111", "office@digitalehandwerkskunst.de", "Mechernich", "https://digitalehandwerkskunst.de"),
        )
        con.execute(
            "UPDATE companies SET phone=?, email=?, city=? WHERE id=51",
            ("0214-222222", "info@prooffice-test.example", "Leverkusen"),
        )
        con.execute(
            """
            INSERT INTO contacts (
                id, tenant_id, company_id, name, email, phone, position
            ) VALUES (1, 1, 50, 'Christian Kummetat', 'christian@example.test', '0171-0000000', 'Owner')
            """
        )
        con.execute(
            """
            INSERT OR REPLACE INTO agency_customers (
                id, tenant_id, crm_company_id, customer_number, lifecycle_status,
                company_name, contact_name, contact_email, billing_email,
                onboarding_status, delivery_status, product, terms_confirmed,
                avv_privacy_status
            ) VALUES (
                3, 1, 50, 'KUN001', 'ready_for_provisioning',
                'Digitale Handwerkskunst', 'Christian Kummetat', 'christian@example.test',
                'billing@example.test',
                'in_progress', 'approved_pending_start', 'Website+CRM', 1, 'missing'
            )
            """
        )
        con.execute(
            "INSERT INTO deals (id, tenant_id, company_id, title) VALUES (100, 1, 10, 'MBP Website')"
        )
        con.execute(
            "INSERT INTO deals (id, tenant_id, company_id, title) VALUES (101, 1, 20, 'Alpha Deal')"
        )
        con.execute(
            "INSERT INTO deals (id, tenant_id, company_id, title) VALUES (150, 1, 50, 'Deal DHK')"
        )
        con.execute(
            "INSERT INTO deals (id, tenant_id, company_id, title) VALUES (151, 1, 51, 'ProOffice Meta')"
        )
        lines_json = (
            '[{"description":"Website Setup","qty":1,"unit_price_eur":1490,'
            '"total_eur":1490},'
            '{"description":"Hosting monatlich","qty":1,"unit_price_eur":49,'
            '"total_eur":49},'
            '{"description":"Support-Paket","qty":2,"unit_price_eur":75,'
            '"total_eur":150}]'
        )
        con.execute(
            """
            INSERT INTO offers (
                id, tenant_id, deal_id, company_id, offer_number, version,
                services, setup_price_eur, monthly_price_eur, status, created_at
            ) VALUES (
                1000, 1, 100, 10, 'ANG-1000', 1, ?, 1490, 49, 'gesendet', '2026-07-15T10:00:00+00:00'
            )
            """,
            (lines_json,),
        )
        con.execute(
            """
            INSERT INTO offers (
                id, tenant_id, deal_id, company_id, offer_number, version,
                services, setup_price_eur, monthly_price_eur, status, created_at
            ) VALUES (
                2000, 1, 101, 20, 'ANG-2000', 1,
                '[{"description":"Basis","qty":1,"unit_price_eur":500,"total_eur":500}]',
                500, 29, 'entwurf', '2026-06-01T10:00:00+00:00'
            )
            """
        )
        con.execute(
            """
            INSERT INTO offers (
                id, tenant_id, deal_id, company_id, offer_number, version,
                services, setup_price_eur, monthly_price_eur, status, created_at
            ) VALUES (
                2001, 1, 101, 20, 'ANG-2001', 1,
                '[{"description":"Premium","qty":1,"unit_price_eur":1200,"total_eur":1200}]',
                1200, 79, 'gesendet', '2026-07-20T10:00:00+00:00'
            )
            """
        )
        con.execute(
            """
            INSERT INTO offers (
                id, tenant_id, deal_id, company_id, offer_number, version,
                services, setup_price_eur, monthly_price_eur, status, created_at
            ) VALUES (
                4, 1, 150, 50, 'ANG-0004', 1,
                '[{"description":"Agency Setup","qty":1,"unit_price_eur":0,"total_eur":0}]',
                0, 0, 'angenommen', '2026-08-01T09:52:21+00:00'
            )
            """
        )
        con.execute(
            "UPDATE companies SET lifecycle_status = sales_lifecycle "
            "WHERE sales_lifecycle IS NOT NULL AND sales_lifecycle != ''"
        )
        con.commit()
        # Invariant: non-CUSTOMER rows must not carry numbers
        if pol:
            rows = con.execute(
                "SELECT name, customer_number, sales_lifecycle FROM companies"
            ).fetchall()
            for name, num, life in rows:
                pol.assert_customer_number_rule(
                    lifecycle_status=life,
                    customer_number=(num or None) or None,
                )
    finally:
        con.close()
    _ = mod.probe_readable(p)
    return p

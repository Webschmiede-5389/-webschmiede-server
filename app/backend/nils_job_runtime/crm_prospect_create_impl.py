# -*- coding: utf-8 -*-
"""Create CRM PROSPECT company (+ optional contact). Standalone SQL — no ORM.

Safety rules:
- lifecycle_status always PROSPECT
- customer_number always NULL
- never creates offers/deals/CUSTOMER
- tenant-scoped
"""
from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


def _lifecycle_policy():
    """Load CRM lifecycle policy: local copy first, then CRM root."""
    candidates = [
        Path(__file__).resolve().with_name("crm_lifecycle_policy.py"),
        Path(__file__).resolve().with_name("lifecycle_policy.py"),
    ]
    try:
        from nils_job_runtime import crm_offer_service as offer_svc

        candidates.append(
            offer_svc._crm_root() / "app" / "services" / "lifecycle_policy.py"
        )
    except Exception:
        pass
    name = "crm_lifecycle_policy_sibling"
    if name in sys.modules:
        return sys.modules[name]
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod
    raise FileNotFoundError("lifecycle_policy not found for prospect create")


class _Conn(Protocol):
    def execute(self, sql: str, params: Any = ()) -> Any: ...

    def commit(self) -> None: ...


@dataclass
class ProspectCreateResult:
    company_id: int
    company_name: str
    contact_id: int | None
    contact_name: str
    lifecycle_status: str
    customer_number: str
    already_existed: bool = False
    country: str | None = None
    legal_basis: str | None = None
    do_not_contact: bool = True
    outbound_allowed: bool = False


def _has_column(con: _Conn, table: str, column: str) -> bool:
    try:
        rows = con.execute(
            """
            SELECT 1 AS ok FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ? AND column_name = ?
            LIMIT 1
            """,
            (table, column),
        ).fetchall()
        if rows:
            return True
    except Exception:
        pass
    try:
        import sqlite3

        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
        names = set()
        for r in rows:
            if isinstance(r, sqlite3.Row):
                names.add(r["name"])
            elif isinstance(r, dict):
                names.add(r.get("name") or r.get("column_name") or "")
            else:
                names.add(r[1])
        return column in names
    except Exception:
        return False


def normalize_company_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())[:200]


def find_company_exact(
    con: _Conn, *, tenant_id: int, name: str
) -> dict[str, Any] | None:
    n = normalize_company_name(name)
    if not n:
        return None
    life_sel = (
        "COALESCE(lifecycle_status, '')"
        if _has_column(con, "companies", "lifecycle_status")
        else "''"
    )
    num_sel = (
        "COALESCE(customer_number, '')"
        if _has_column(con, "companies", "customer_number")
        else "''"
    )
    arch = ""
    if _has_column(con, "companies", "archived_at"):
        arch = "AND (archived_at IS NULL OR CAST(archived_at AS TEXT) = '')"
    row = con.execute(
        f"""
        SELECT id, name, {life_sel} AS lifecycle_status,
               {num_sel} AS customer_number
        FROM companies
        WHERE tenant_id = ? AND lower(name) = lower(?)
          {arch}
        ORDER BY id DESC
        LIMIT 1
        """,
        (tenant_id, n),
    ).fetchone()
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "name": str(row["name"] or ""),
        "lifecycle_status": str(row["lifecycle_status"] or ""),
        "customer_number": str(row["customer_number"] or ""),
    }


def create_prospect(
    con: _Conn,
    *,
    tenant_id: int,
    company_name: str,
    contact_name: str = "",
    lead_source: str = "nils_telegram",
    notes: str = "",
    country: str | None = None,
    legal_basis: str | None = None,
    outbound_allowed: bool = False,
    do_not_contact: bool | None = None,
) -> ProspectCreateResult:
    """Insert PROSPECT company (+ optional contact). Raises ValueError on bad input.

    country / legal_basis stay NULL unless explicitly provided.
    Outbound is never auto-approved (do_not_contact=True by default).
    """
    name = normalize_company_name(company_name)
    if len(name) < 2:
        raise ValueError("Firmenname fehlt oder ist zu kurz")

    lp = _lifecycle_policy()
    life = lp.initial_lifecycle_for_create(as_lead=False)
    assert life == lp.LIFECYCLE_PROSPECT
    lp.assert_customer_number_rule(lifecycle_status=life, customer_number=None)

    country_norm = (country or "").strip().upper()[:8] or None
    legal_norm = (legal_basis or "").strip()[:40] or None
    # Storage ≠ outbound: default block marketing/contact campaigns
    outbound = bool(outbound_allowed)
    dnc = (not outbound) if do_not_contact is None else bool(do_not_contact)
    if outbound and dnc:
        # explicit outbound approval must clear do_not_contact
        dnc = False
    if not outbound:
        dnc = True

    existing = find_company_exact(con, tenant_id=tenant_id, name=name)
    if existing:
        return ProspectCreateResult(
            company_id=int(existing["id"]),
            company_name=existing["name"],
            contact_id=None,
            contact_name="",
            lifecycle_status=existing["lifecycle_status"] or life,
            customer_number=existing["customer_number"] or "",
            already_existed=True,
            country=None,
            legal_basis=None,
            do_not_contact=True,
            outbound_allowed=False,
        )

    cols = ["tenant_id", "name", "status", "lead_source"]
    vals: list[Any] = [tenant_id, name, "neu", (lead_source or "nils_telegram")[:60]]
    if _has_column(con, "companies", "lifecycle_status"):
        cols.append("lifecycle_status")
        vals.append(life)
    if _has_column(con, "companies", "customer_number"):
        cols.append("customer_number")
        vals.append(None)
    # Explicit NULL so DB default 'DE' cannot silently fill country
    if _has_column(con, "companies", "country"):
        cols.append("country")
        vals.append(country_norm)
    if _has_column(con, "companies", "legal_basis"):
        cols.append("legal_basis")
        vals.append(legal_norm)
    if _has_column(con, "companies", "do_not_contact"):
        cols.append("do_not_contact")
        vals.append(bool(dnc))
    if notes and _has_column(con, "companies", "notes"):
        cols.append("notes")
        vals.append(notes[:2000])

    placeholders = ", ".join("?" for _ in cols)
    col_sql = ", ".join(cols)
    # SQLite vs PG returning
    def _id_of(row: Any) -> int | None:
        if row is None:
            return None
        try:
            v = row["id"]
        except Exception:
            try:
                v = row[0]
            except Exception:
                return None
        return int(v) if v is not None else None

    try:
        row = con.execute(
            f"INSERT INTO companies ({col_sql}) VALUES ({placeholders}) RETURNING id",
            tuple(vals),
        ).fetchone()
        company_id = _id_of(row)
        if company_id is None:
            raise RuntimeError("no returning id")
    except Exception:
        con.execute(
            f"INSERT INTO companies ({col_sql}) VALUES ({placeholders})",
            tuple(vals),
        )
        row = con.execute("SELECT last_insert_rowid() AS id").fetchone()
        company_id = _id_of(row)
        if company_id is None:
            row = con.execute(
                "SELECT id FROM companies WHERE tenant_id = ? AND name = ? ORDER BY id DESC LIMIT 1",
                (tenant_id, name),
            ).fetchone()
            company_id = _id_of(row)
        if company_id is None:
            raise RuntimeError("company insert without id")

    contact_id: int | None = None
    cname = re.sub(r"\s+", " ", (contact_name or "").strip())[:200]
    if cname and _table_exists(con, "contacts"):
        parts = cname.split(" ", 1)
        first = parts[0][:100]
        last = parts[1][:100] if len(parts) > 1 else ""
        c_cols = ["tenant_id", "company_id", "name"]
        c_vals: list[Any] = [tenant_id, company_id, cname]
        if _has_column(con, "contacts", "source"):
            c_cols.append("source")
            c_vals.append("nils_telegram")
        if _has_column(con, "contacts", "status"):
            c_cols.append("status")
            c_vals.append("neu")
        if _has_column(con, "contacts", "first_name"):
            c_cols.append("first_name")
            c_vals.append(first)
        if _has_column(con, "contacts", "last_name"):
            c_cols.append("last_name")
            c_vals.append(last or None)
        ph = ", ".join("?" for _ in c_cols)
        try:
            crow = con.execute(
                f"INSERT INTO contacts ({', '.join(c_cols)}) VALUES ({ph}) RETURNING id",
                tuple(c_vals),
            ).fetchone()
            contact_id = _id_of(crow)
        except Exception:
            con.execute(
                f"INSERT INTO contacts ({', '.join(c_cols)}) VALUES ({ph})",
                tuple(c_vals),
            )
            crow = con.execute("SELECT last_insert_rowid() AS id").fetchone()
            contact_id = _id_of(crow)

    if hasattr(con, "commit"):
        con.commit()

    return ProspectCreateResult(
        company_id=company_id,
        company_name=name,
        contact_id=contact_id,
        contact_name=cname,
        lifecycle_status=life,
        customer_number="",
        already_existed=False,
        country=country_norm,
        legal_basis=legal_norm,
        do_not_contact=bool(dnc),
        outbound_allowed=bool(outbound) and not dnc,
    )


def _table_exists(con: _Conn, table: str) -> bool:
    try:
        rows = con.execute(
            """
            SELECT 1 AS ok FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = ?
            LIMIT 1
            """,
            (table,),
        ).fetchall()
        if rows:
            return True
    except Exception:
        pass
    try:
        con.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchall()
        return True
    except Exception:
        return False


def format_created_telegram(result: ProspectCreateResult) -> str:
    if result.already_existed:
        life = result.lifecycle_status or "—"
        num = result.customer_number or "—"
        return (
            f"Unternehmen „{result.company_name}“ gibt es schon im CRM "
            f"(id={result.company_id}, Lifecycle={life}, Kundennummer={num}). "
            "Kein neuer Interessent angelegt."
        )
    lines = [
        "Interessent angelegt (kein Kunde).",
        f"Unternehmen: {result.company_name}",
        f"Company-ID: {result.company_id}",
        f"Lifecycle: {result.lifecycle_status}",
        "Kundennummer: — (erst bei gewonnenem Deal)",
        f"Land: {result.country or 'nicht angegeben'}",
        (
            "Rechtsgrundlage: noch nicht bewertet"
            if not result.legal_basis
            else f"Rechtsgrundlage: {result.legal_basis}"
        ),
        (
            "Outbound: nicht freigegeben"
            if not result.outbound_allowed
            else "Outbound: freigegeben"
        ),
    ]
    if result.contact_name:
        lines.append(
            f"Kontakt: {result.contact_name}"
            + (f" (id={result.contact_id})" if result.contact_id else "")
        )
    return "\n".join(lines)


def format_approval_prompt(*, company_name: str, contact_name: str = "") -> str:
    lines = [
        "Freigabe nötig — Interessent anlegen (kein Kunde, keine Kundennummer):",
        f"Unternehmen: {company_name}",
    ]
    if contact_name:
        lines.append(f"Kontakt: {contact_name}")
    lines.append('Antworte mit „ja“ / „freigabe ja“, sonst „stop“.')
    return "\n".join(lines)

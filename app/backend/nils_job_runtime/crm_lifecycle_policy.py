# -*- coding: utf-8 -*-
"""Sales-Lifecycle-Policy (Soll) — reine Regeln, keine DB-Migration.

Trennt ENTITY (Company/Contact), LIFECYCLE, DEAL und OFFER.
„Im CRM vorhanden“ != „Kunde“.
"""
from __future__ import annotations

from typing import Final

# --- ENTITY (kein Lifecycle) ---
ENTITY_COMPANY = "company"
ENTITY_CONTACT = "contact"

# --- SALES LIFECYCLE (Company-Ebene, Soll) ---
LIFECYCLE_LEAD: Final = "LEAD"
LIFECYCLE_PROSPECT: Final = "PROSPECT"
LIFECYCLE_CUSTOMER: Final = "CUSTOMER"
LIFECYCLE_FORMER_CUSTOMER: Final = "FORMER_CUSTOMER"
LIFECYCLE_ARCHIVED: Final = "ARCHIVED"

LIFECYCLE_STATUSES: frozenset[str] = frozenset(
    {
        LIFECYCLE_LEAD,
        LIFECYCLE_PROSPECT,
        LIFECYCLE_CUSTOMER,
        LIFECYCLE_FORMER_CUSTOMER,
        LIFECYCLE_ARCHIVED,
    }
)

# Lifecycle-Werte, die KEINE Kundennummer tragen dürfen
NO_CUSTOMER_NUMBER: frozenset[str] = frozenset(
    {
        LIFECYCLE_LEAD,
        LIFECYCLE_PROSPECT,
    }
)

# --- Mapping Ist (AgencyCustomer.lifecycle_status) → Soll-Company-Lifecycle ---
AGENCY_CUSTOMER_TO_COMPANY_LIFECYCLE: dict[str, str] = {
    "prospect": LIFECYCLE_PROSPECT,
    "won_pending_onboarding": LIFECYCLE_CUSTOMER,
    "onboarding_in_progress": LIFECYCLE_CUSTOMER,
    "ready_for_provisioning": LIFECYCLE_CUSTOMER,
    "provisioning": LIFECYCLE_CUSTOMER,
    "internal_testing": LIFECYCLE_CUSTOMER,
    "ready_for_go_live": LIFECYCLE_CUSTOMER,
    "active": LIFECYCLE_CUSTOMER,
    "provisioning_failed": LIFECYCLE_CUSTOMER,  # schon nummeriert / gewonnen
    "blocked_missing_data": LIFECYCLE_CUSTOMER,
    "blocked_approval": LIFECYCLE_CUSTOMER,
    "suspended": LIFECYCLE_FORMER_CUSTOMER,
}

# Company.status (Ist) ist Qualifikations-/Arbeitsstatus, KEIN Kundenstatus
COMPANY_STATUS_IS_NOT_CUSTOMER = True


def may_have_customer_number(lifecycle_status: str) -> bool:
    """Kundennummer nur bei CUSTOMER / FORMER_CUSTOMER / ARCHIVED (Historie)."""
    return lifecycle_status in (
        LIFECYCLE_CUSTOMER,
        LIFECYCLE_FORMER_CUSTOMER,
        LIFECYCLE_ARCHIVED,
    )


def assert_customer_number_rule(
    *, lifecycle_status: str, customer_number: str | None
) -> None:
    """Geschäftliche Invariante: Nummer nur wenn Kunde (gewesen) / Archiv mit Historie."""
    num = (customer_number or "").strip() or None
    if lifecycle_status not in LIFECYCLE_STATUSES:
        raise ValueError(f"ungültiger lifecycle_status: {lifecycle_status}")
    if lifecycle_status in NO_CUSTOMER_NUMBER and num:
        raise ValueError(
            f"customer_number muss NULL sein bei lifecycle={lifecycle_status}"
        )
    if lifecycle_status == LIFECYCLE_CUSTOMER and not num:
        raise ValueError("CUSTOMER erfordert customer_number")
    # FORMER_CUSTOMER / ARCHIVED: Nummer optional (Historie)

def initial_lifecycle_for_create(*, as_lead: bool = False) -> str:
    """Neue Company ohne gewonnenes Geschäft."""
    return LIFECYCLE_LEAD if as_lead else LIFECYCLE_PROSPECT


def initial_lifecycle_for_import() -> str:
    return LIFECYCLE_LEAD


def lifecycle_after_offer_created(current: str) -> str:
    """Angebot anlegen ändert Lifecycle nicht zu CUSTOMER."""
    if current == LIFECYCLE_LEAD:
        return LIFECYCLE_PROSPECT
    return current


def lifecycle_after_offer_sent(current: str) -> str:
    """Versand ≠ Kunde."""
    return lifecycle_after_offer_created(current)


def lifecycle_after_deal_won(current: str) -> str:
    """Deal WON / Angebot verbindlich angenommen → CUSTOMER."""
    if current == LIFECYCLE_ARCHIVED:
        raise ValueError("Archivierte Company kann nicht zu CUSTOMER werden")
    return LIFECYCLE_CUSTOMER


def should_allocate_customer_number(
    *,
    previous_lifecycle: str,
    new_lifecycle: str,
    existing_number: str | None,
) -> bool:
    """Genau einmal: erstmaliger Wechsel auf CUSTOMER ohne bestehende Nummer."""
    if existing_number and str(existing_number).strip():
        return False
    return (
        previous_lifecycle != LIFECYCLE_CUSTOMER
        and new_lifecycle == LIFECYCLE_CUSTOMER
    )


def nils_entity_label(lifecycle_status: str | None = None) -> str:
    """Telegram-Sprache: nie „Kunde“, wenn noch kein CUSTOMER."""
    if lifecycle_status == LIFECYCLE_CUSTOMER:
        return "Kunde"
    if lifecycle_status == LIFECYCLE_FORMER_CUSTOMER:
        return "ehemaliger Kunde"
    if lifecycle_status == LIFECYCLE_LEAD:
        return "Lead"
    if lifecycle_status == LIFECYCLE_PROSPECT:
        return "Interessent"
    return "Unternehmen"


def nils_ask_company_prompt() -> str:
    """Neutral — CRM kann Leads/Prospects/Kunden enthalten."""
    return "Welche Firma oder welchen Kontakt meinst du?"


def nils_company_not_found(query: str) -> str:
    q = (query or "").strip() or "—"
    return (
        f"Kein Unternehmen zu „{q}“ im CRM gefunden. "
        "Bitte anderen Namen versuchen."
    )


def nils_offer_company_line(*, company_name: str, lifecycle_status: str | None = None) -> str:
    """Angebotszeile: nur bei CUSTOMER „Kunde“, sonst „Unternehmen“."""
    name = company_name or "–"
    if lifecycle_status == LIFECYCLE_CUSTOMER:
        return f"Kunde: {name}"
    return f"Unternehmen: {name}"


def nils_multi_company_prompt() -> str:
    return "Mehrere Unternehmen gefunden — welches meinst du?"


def is_true_customer_agency_status(agency_lifecycle_status: str | None) -> bool:
    """AgencyCustomer.prospect ist KEIN echter Kunde."""
    if not agency_lifecycle_status:
        return False
    mapped = AGENCY_CUSTOMER_TO_COMPANY_LIFECYCLE.get(agency_lifecycle_status)
    return mapped == LIFECYCLE_CUSTOMER


# ---------------------------------------------------------------------------
# AgencyCustomer-Draft Entscheidung (keine Verhaltensänderung in diesem Schritt)
# ---------------------------------------------------------------------------
#
# Domain: AgencyCustomer ist **Provisioning-/Delivery-SoR**, nicht reine Sales-Entity.
# - ensure_customer_draft bei UI-Company-Create → prospect, customer_number=None
# - UI: Company-Detail + Deal-Detail linken auf Kundenakte (auch ohne Nummer)
# - run_won_provisioning reused denselben Datensatz (Unique tenant+company)
# - Import legt bewusst KEINEN Draft an
#
# Option A (empfohlen): Draft vor WON erlaubt, wird aber nie als CUSTOMER behandelt
# Option B: Draft erst bei WON — bräche UI-Links und get_customer_by_company vor Won
#
AGENCY_CUSTOMER_DRAFT_POLICY: Final = "A"
AGENCY_CUSTOMER_DRAFT_RATIONALE: Final = (
    "Option A: AgencyCustomer darf als vorbereiteter Draft (lifecycle=prospect, "
    "customer_number=NULL) vor WON existieren. Es ist Provisioning-Domain, kein "
    "Sales-„Kunde“. Echter Kunde erst nach run_won_provisioning. Option B würde "
    "Company-/Deal-UI und Idempotenz-Pfad unnötig brechen."
)

# -*- coding: utf-8 -*-
"""Nils Orchestrator – Chef-Hirn für Telegram/Voice.

Auftrag rein → Plan (Mitarbeiter, LLM-Route, Tools, n8n, Cursor) → Ausführen → kurze Meldung.

Ziel: Nils entscheidet, wer mitzieht und welches Modell (billig zuerst).
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

log = logging.getLogger("nils_orchestrator")

ROOT = Path(__file__).resolve().parents[2]

# Agent → typische n8n-Workflows (Katalog, Trigger optional)
N8N_BY_AGENT: dict[str, list[dict[str, str]]] = {
    "stefan": [{"id": "agency-02-stefan", "name": "Stefan Digest"}],
    "scout": [{"id": "agency-03-scout", "name": "Markt-Scout"}, {"id": "workflow-akquise-reminders", "name": "Akquise Reminders"}],
    "outreach": [{"id": "agency-04-outreach", "name": "Outreach"}],
    "crm": [{"id": "workflow-followups", "name": "Follow-ups"}, {"id": "agency-05-crm", "name": "CRM"}],
    "texter": [{"id": "agency-06-texter", "name": "Texter"}],
    "design": [{"id": "agency-07-design", "name": "Design"}],
    "lektor": [{"id": "agency-08-lektor", "name": "Lektor"}],
    "nils": [{"id": "workflow-healthcheck", "name": "Healthcheck"}, {"id": "agency-09-nils", "name": "Nils Infra"}],
    "anwalt": [{"id": "agency-10-anwalt", "name": "Anwalt"}],
    "finanz": [{"id": "workflow-buchhaltung-monat", "name": "Buchhaltung Monat"}, {"id": "agency-11-finanz", "name": "Finanz"}],
    "account": [{"id": "workflow-inbox-agent", "name": "Inbox"}, {"id": "agency-12-account", "name": "Account"}],
    "service": [{"id": "agency-13-service", "name": "Service-Wächter"}],
    "radar": [{"id": "agency-14-radar", "name": "Radar"}],
    "router": [{"id": "agency-brain", "name": "Agency Brain"}, {"id": "agency-01-router", "name": "Router"}],
}

ROLE_LEAD = {
    "stefan": "führt Priorität",
    "nils": "führt Ops/Technik",
    "anwalt": "führt Vertragsprüfung",
    "scout": "führt Marktsuche",
    "radar": "führt Trend-Sicht",
    "texter": "führt Text",
    "finanz": "führt Geld/Belege",
    "account": "führt Kundenkommunikation",
}

WORK_RE = re.compile(
    r"\b("
    r"bau|erstell|programmier|implement|scann|analys|recherch|deploy|"
    r"angebot|rechnung|onboarding|vertrag|avv|akquise|lead|outreach|"
    r"kunde|portal|dashboard|website|instagram|golf|dgv|radar|guardian|"
    r"status|fix|reparier|schreib|text|mail|schick|senden|prüf|pruef|"
    r"cursor|workorder|auftrag|briefing|tagesplan|shipcheck|freigabe"
    r")\w*\b",
    re.I,
)

CHATTY_RE = re.compile(
    r"^(hey|hi|hallo|moin|servus|jo|yo|was geht|wie geht|danke|ok|okay|cool|nice)[\s!.?]*$",
    re.I,
)


def _env(name: str, default: str = "") -> str:
    v = (os.environ.get(name) or "").strip()
    if v:
        return v
    for base in (ROOT, ROOT / "app", Path("/root/app")):
        for fname in ("deploy.secrets.local", "requesty.secrets.local", "cursor.secrets.local"):
            p = base / fname
            if not p.is_file():
                continue
            try:
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, _, val = s.partition("=")
                    if k.strip() == name:
                        return val.strip().strip('"').strip("'")
            except Exception:
                continue
    return default


def should_orchestrate(text: str, *, force_agent: str | None = None, has_tools: bool = False) -> bool:
    """Nur echte Multi-Agent-/Ops-Arbeit – nicht Chat und nicht reine Research."""
    if force_agent:
        return True
    t = (text or "").strip()
    if not t:
        return False
    if CHATTY_RE.match(t) and len(t) < 40:
        return False
    # Research/Plaudern → Companion, nicht Orchestrator-Rohdump
    try:
        import nils_research as research

        if research.looks_like_research(t) and not any(
            x in t.lower() for x in ("programmier", "cursor:", "deploy", "sende mail", "schick angebot")
        ):
            return False
    except Exception:
        pass
    hard = (
        "programmier", "cursor:", "deploy", "workorder", "auftrag:",
        "sende angebot", "schick angebot", "onboarding senden", "baue website",
        "baue dashboard", "baue portal", "im repo",
    )
    low = t.lower()
    if any(x in low for x in hard):
        return True
    # Tools allein reichen nicht – sonst landet jede Recherche im Plan-Dump
    if has_tools:
        return False
    return False


def _pick_lead(agents: list[str]) -> str:
    for a in ("stefan", "nils", "anwalt", "scout", "radar", "finanz", "texter", "account"):
        if a in agents:
            return a
    return agents[0] if agents else "nils"


def _llm_route_for(message: str, agents: list[str], *, coding: bool = False) -> str:
    try:
        import nils_dispatcher as nd

        hint = None
        if coding or any(a in agents for a in ("anwalt", "stefan")):
            hint = "B"
        if any(a in agents for a in ("design",)) or "vision" in (message or "").lower():
            hint = "C"
        return nd.classify_route(message or "", hint=hint)
    except Exception:
        return "A"


def _n8n_suggestions(agents: list[str]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for a in ["router"] + list(agents):
        for w in N8N_BY_AGENT.get(a) or []:
            wid = w.get("id") or ""
            if wid and wid not in seen:
                seen.add(wid)
                out.append(dict(w))
    return out[:8]


def _n8n_base() -> str:
    return (
        _env("N8N_WEBHOOK_BASE")
        or _env("N8N_BASE_URL")
        or "http://127.0.0.1:5678"
    ).rstrip("/")


def trigger_n8n(plan: dict[str, Any], message: str) -> dict[str, Any]:
    """Optional: Agency-Brain Webhook pingen. Fail-open."""
    if _env("NILS_N8N_TRIGGER", "1").lower() in ("0", "false", "no", "off"):
        return {"ok": False, "skipped": True, "reason": "disabled"}
    path = _env("N8N_AGENCY_BRAIN_PATH", "agency-brain")
    url = f"{_n8n_base()}/webhook/{path.lstrip('/')}"
    payload = {
        "source": "nils_orchestrator",
        "message": (message or "")[:4000],
        "plan": {
            "lead": plan.get("lead"),
            "agents": plan.get("agents"),
            "llm_route": plan.get("llm_route"),
            "cursor": plan.get("cursor"),
            "tools": [t.get("name") for t in (plan.get("tools") or []) if isinstance(t, dict)],
        },
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "NilsOrchestrator/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", errors="replace")[:400]
            return {"ok": True, "status": resp.status, "url": url, "body": body}
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)[:200]}


def build_plan(
    message: str,
    *,
    force_agent: str | None = None,
    pre_tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    import agency_router as router

    try:
        import nils_cursor_bridge as bridge

        coding = bridge.looks_like_coding_task(message or "")
    except Exception:
        coding = False

    route = router.classify(
        message or "",
        source="telegram_orchestrator",
        force_agent=force_agent,
        tenant_id="AGENCY",
        redact=True,
    )
    agents = list(route.get("mitarbeiter") or [])[:5]
    if force_agent and force_agent not in agents:
        agents = [force_agent] + [a for a in agents if a != force_agent]
    if coding and "nils" not in agents:
        agents = ["nils"] + agents
    if not agents:
        agents = ["nils", "stefan"]

    lead = _pick_lead(agents)
    llm_route = _llm_route_for(message or "", agents, coding=coding)
    tools = list(pre_tools or [])

    # Coding → Cursor-Tool (Freigabe später)
    if coding and not any(t.get("name") == "cursor_code" for t in tools):
        tools.insert(0, {"name": "cursor_code", "args": {"task": message or ""}})

    # Text-lastige Agents ohne konkretes Tool → draft
    low = (message or "").lower()
    if any(a in agents for a in ("texter", "lektor", "outreach")) and not any(
        t.get("name") in ("draft_document", "golf_club_text", "instagram_caption", "send_mail") for t in tools
    ):
        if any(x in low for x in ("rechnung",)):
            tools.append({"name": "draft_document", "args": {"kind": "rechnung", "details": message}})
        elif any(x in low for x in ("angebot",)):
            tools.append({"name": "draft_document", "args": {"kind": "angebot", "details": message}})
        elif any(x in low for x in ("onboarding",)):
            tools.append({"name": "draft_document", "args": {"kind": "onboarding", "details": message}})

    n8n = _n8n_suggestions(agents)
    labels = []
    for a in agents:
        meta = router.AGENTS.get(a) or {}
        labels.append(str(meta.get("label") or a))

    return {
        "ok": bool(route.get("ok", True)),
        "ziel": route.get("ziel") or "Auftrag umsetzen",
        "prioritaet": route.get("prioritaet") or "normal",
        "lead": lead,
        "lead_role": ROLE_LEAD.get(lead, "koordiniert"),
        "agents": agents,
        "agent_labels": labels,
        "llm_route": llm_route,
        "llm_note": {
            "A": "billig/schnell (lokal oder günstiges Cloud-Modell)",
            "B": "stärker (Analyse/Vertrag/Plan)",
            "C": "Vision/schwer",
        }.get(llm_route, ""),
        "tools": tools[:6],
        "cursor": coding,
        "n8n": n8n,
        "route_raw": {k: route.get(k) for k in ("ziel", "prioritaet", "mitarbeiter", "payload") if k in route},
    }


def _format_plan_header(plan: dict[str, Any]) -> str:
    agents = ", ".join(plan.get("agent_labels") or plan.get("agents") or []) or "–"
    n8n = plan.get("n8n") or []
    n8n_s = ", ".join(w.get("name") or w.get("id") for w in n8n[:3]) if n8n else "–"
    cursor = "ja (Freigabe)" if plan.get("cursor") else "nein"
    return (
        f"Plan: {plan.get('lead')} {plan.get('lead_role')} · "
        f"Team: {agents} · "
        f"LLM-Route {plan.get('llm_route')} ({plan.get('llm_note')}) · "
        f"Cursor: {cursor} · n8n: {n8n_s}"
    )


def _enrich_texter(message: str, llm_route: str) -> str:
    try:
        import llm_client as llm

        r = llm.chat(
            [
                {
                    "role": "system",
                "content": (
                    "Du bist Texter der Webschmiede. Deutsch, menschlich, kein Agentur-Sprech. "
                    "Liefere den fertigen Text, kurz lektoriert. "
                    "HALLUZINATIONS-VERBOT: Keine erfundenen Preise, Kunden, Termine. "
                    "Platzhalter in [eckigen Klammern] wenn Daten fehlen."
                ),
                },
                {"role": "user", "content": (message or "")[:3000]},
            ],
            max_tokens=900,
            temperature=0.55,
            timeout=55,
            route=llm_route or "A",
        )
        if r.get("ok") and r.get("reply"):
            return r["reply"].strip()
    except Exception as e:
        return f"(Texter-LLM: {e})"
    return ""


def run(
    db: Any,
    message: str,
    *,
    force_agent: str | None = None,
    pre_tools: list[dict[str, Any]] | None = None,
    history: list[dict] | None = None,
    memory_block: str = "",
    from_voice: bool = False,
    execute_tools_fn: Any = None,
) -> dict[str, Any]:
    """Orchestrator: intern planen, nach außen menschlich antworten (kein Plan-Dump)."""
    plan = build_plan(message, force_agent=force_agent, pre_tools=pre_tools)
    fact_notes: list[str] = []
    if memory_block:
        fact_notes.append(memory_block[:1200])

    pending = None
    ran_tools: list[str] = []
    n8n_result: dict[str, Any] | None = None

    tools = list(plan.get("tools") or [])
    if execute_tools_fn and tools:
        for t in tools[:4]:
            name = t.get("name") or ""
            args = t.get("args") or {}
            try:
                out = execute_tools_fn(db, name, args, confirmed=False)
            except Exception as e:
                fact_notes.append(f"[{name}] Fehler: {e}")
                continue
            ran_tools.append(name)
            if out.get("needs_confirm"):
                pending = out.get("pending")
                return {
                    "ok": True,
                    "reply": out.get("text") or "Kurz bestätigen mit „ja“ oder „abbrechen“.",
                    "pending": pending,
                    "needs_confirm": True,
                    "route": "orchestrator_confirm",
                    "plan": plan,
                    "tools": ran_tools,
                }
            if out.get("text"):
                fact_notes.append(f"[{name}]\n{out['text']}")
            elif out.get("error"):
                fact_notes.append(f"[{name}] {out['error']}")

    try:
        import agency_brain as brain

        lead = plan.get("lead") or force_agent or "nils"
        res = brain.process(
            message,
            source="telegram_orchestrator",
            force_agent=lead if lead in ("stefan", "nils", "radar", "scout", "anwalt", "service") else None,
            dispatch=True,
            include_commander=("commander" in (message or "").lower() or "tagesplan" in (message or "").lower()),
            fast=False,
            max_agents=3,
        )
        if res.get("summary"):
            fact_notes.append("Brain:\n" + str(res.get("summary"))[:1800])
        results = res.get("results") or {}
        for aid, payload in list(results.items())[:4]:
            if not isinstance(payload, dict):
                continue
            for key in ("empfehlung", "urteil", "summary", "text", "note"):
                if payload.get(key):
                    fact_notes.append(
                        f"{aid}: {json.dumps(payload.get(key), ensure_ascii=False)[:600]}"
                    )
                    break
    except Exception as e:
        log.exception("orchestrator brain")
        fact_notes.append(f"Brain: {e}")

    agents = plan.get("agents") or []
    if any(a in agents for a in ("texter", "lektor", "outreach")) and not any(
        x in ran_tools for x in ("draft_document", "golf_club_text", "instagram_caption")
    ):
        draft = _enrich_texter(message, str(plan.get("llm_route") or "A"))
        if draft:
            fact_notes.append(f"[texter]\n{draft}")

    try:
        n8n_result = trigger_n8n(plan, message)
        if n8n_result.get("ok"):
            fact_notes.append("n8n: Webhook ausgelöst.")
    except Exception:
        pass

    try:
        import human_voice as voice
        import llm_client as llm
        import nils_truth as truth
        import telegram_session as tg_sess

        grounded = truth.grounding_block(
            memory=memory_block or "",
            tool_notes=fact_notes,
            plan_header=_format_plan_header(plan),
        )
        try:
            import nils_inventory as inv

            grounded = inv.for_prompt(compact=True) + "\n\n" + grounded
        except Exception:
            pass
        system = voice.nils_system(
            " Christian schreibt per Telegram. Antworte wie ein menschlicher Mitarbeiter. "
            "Du kennst deinen Werkzeugkasten und hast ihn ggf. schon genutzt. "
            "Kein Plan-Jargon, keine Policy-Texte. Nur belegte Fakten."
            + (" Sprachnachricht möglich." if from_voice else ""),
            fast=False,
        )
        messages = tg_sess.build_llm_messages(
            system=system,
            user_text=message[:2000],
            history=[{**h, "body": (h.get("body") or "")[:500]} for h in (history or [])],
            history_limit=8,
            user_prefix=grounded + "\n\nNachricht von Christian:",
        )
        result = llm.chat(
            messages,
            max_tokens=900,
            temperature=0.65,
            timeout=70,
            route=str(plan.get("llm_route") or "A"),
        )
        if result.get("ok") and result.get("reply"):
            return {
                "ok": True,
                "reply": result["reply"].strip()[:4000],
                "pending": None,
                "needs_confirm": False,
                "route": "orchestrator",
                "plan": plan,
                "tools": ran_tools,
                "n8n": n8n_result,
                "llm_route": plan.get("llm_route"),
                "stream_messages": messages,
            }
    except Exception as e:
        log.exception("orchestrator humanize")
        fact_notes.append(f"humanize:{e}")

    fallback = "\n\n".join(
        n
        for n in fact_notes
        if n and "HALLUZINATION" not in n and not n.startswith("Nur belegte")
    )[:3500]
    return {
        "ok": True,
        "reply": fallback or "Kurz hängt’s. Versuch die Frage nochmal etwas konkreter.",
        "pending": None,
        "needs_confirm": False,
        "route": "orchestrator_fallback",
        "plan": plan,
        "tools": ran_tools,
        "n8n": n8n_result,
    }


def status_text() -> str:
    agents = sorted({a for a in N8N_BY_AGENT if a != "router"})
    return (
        "Nils-Orchestrator aktiv.\n"
        f"Mitarbeiter im Katalog: {', '.join(agents)}\n"
        "Entscheidet: Lead, Team, LLM-Route A/B/C, Tools, Cursor, n8n-Hinweise.\n"
        "Antwort immer menschlich. Research/Chat = Companion + deep_research."
    )

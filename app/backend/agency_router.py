"""Agency AI-Router: Intent → 13 digitale Mitarbeiter / Kern-Workflows."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import agency_router_security as router_sec

# IDs = Workflow-Slugs im 13er-System (docs/agency/13-workflows.md)
AGENTS: dict[str, dict[str, Any]] = {
    "stefan": {
        "label": "Stefan",
        "wf": 2,
        "skill": ".cursor/skills/stefan/SKILL.md",
        "keywords": (
            "priorität", "prioritaet", "was zuerst", "roadmap", "strategie",
            "stefan", "überblick", "ueberblick", "reality", "brauch ich",
            "guru", "skalier", "mitarbeiter plan", "nächster schritt agentur",
            "tagesplan", "wochenplan", "schlachtplan", "onboarden wir",
            "was muessen wir bauen", "was müssen wir bauen", "bauplan",
            "b2b-kunde", "b2b kunde", "projektsumme", "5000", "5k",
        ),
        "cursor": "Skill Stefan: Schlachtplan (Architektur, Onboarding-Entwurf, To-dos). Kein Auto-Send.",
    },
    "scout": {
        "label": "Markt-Scout",
        "wf": 3,
        "skill": "akquise/",
        "keywords": (
            "scout", "akquise", "leads suchen", "markt", "finden kunden",
            "places", "verzeichnis", "prospect", "käufer",
        ),
        "cursor": "Akquise-Engine / Queue prüfen, keine Spam-Mails ohne Freigabe.",
    },
    "outreach": {
        "label": "Outreach",
        "wf": 4,
        "skill": ".cursor/skills/texter/SKILL.md",
        "keywords": (
            "outreach", "kaltakquise", "anschreiben lead", "akquise mail",
            "erstkontakt", "pitch nachricht",
        ),
        "cursor": "Persönliche Akquise-Nachricht (menschlicher Ton). Nur Entwurf, Send nur mit OK.",
    },
    "crm": {
        "label": "CRM/Follow-Up",
        "wf": 5,
        "skill": "docs/agency/inbox-agent.md",
        "keywords": (
            "follow-up", "followup", "nachfass", "crm", "erinnerung termin",
            "lead pflegen", "win-back",
        ),
        "cursor": "Follow-ups/Reminders prüfen, keine Massenmails ohne Freigabe.",
    },
    "texter": {
        "label": "Texter",
        "wf": 6,
        "skill": ".cursor/skills/texter/SKILL.md",
        "keywords": (
            "schreib", "text", "mail", "e-mail", "email", "anschreiben",
            "angebotstext", "landing", "copy", "whatsapp nachricht", "sms text",
            "blog", "skript", "formulie",
        ),
        "cursor": "Skill Texter: menschlicher Ton, dann Lektor-Pass.",
    },
    "design": {
        "label": "Design",
        "wf": 7,
        "skill": ".cursor/skills/design/SKILL.md",
        "keywords": (
            "design", "bild", "flyer", "logo", "midjourney", "flux",
            "grafik", "prompt bild", "visitenkarte", "mockup",
        ),
        "cursor": "Skill Design: präzise Bild-Prompts, keine bezahlte API ohne OK.",
    },
    "lektor": {
        "label": "Lektor",
        "wf": 8,
        "skill": ".cursor/skills/texter/SKILL.md",
        "keywords": (
            "lektor", "korrektur", "gegenlesen", "stil prüfen", "grammatik",
            "qualität", "überarbeite den text",
        ),
        "cursor": "Lektor-Pass: Verbotsliste + Klarheit, konkrete Fixes.",
    },
    "nils": {
        "label": "Nils",
        "wf": 9,
        "skill": ".cursor/skills/nils/SKILL.md",
        "keywords": (
            "server", "deploy", "n8n", "nginx", "hetzner", "cloudflare",
            "dns", "watchdog", "api fehler", "ssl", "cron", "health",
            "snack-api", "ops", "nils",
        ),
        "cursor": "Als Nils: Status prüfen, fixen, kurz melden.",
    },
    "anwalt": {
        "label": "Anwalt",
        "wf": 10,
        "skill": ".cursor/skills/anwalt/SKILL.md",
        "keywords": (
            "vertrag", "avv", "agb", "nda", "haftung", "anwalt", "klausel",
            "datenschutz", "dsgvo", "rechts", "kündigung", "auftraggeber",
        ),
        "cursor": "Skill Anwalt: Checkliste A–D, Prüfprotokoll. Keine Wasserdicht-Garantie.",
    },
    "finanz": {
        "label": "Finanz",
        "wf": 11,
        "skill": "docs/agency/buchhaltung-setup.md",
        "keywords": (
            "rechnung", "angebot preis", "mahnung", "buchhaltung", "zahlung",
            "stripe", "lexware", "umsatz", "finanz", "beleg",
        ),
        "cursor": "Angebot/Rechnung/Buchhaltung-Pfad. Keine Käufe ohne OK.",
    },
    "account": {
        "label": "Account-Manager",
        "wf": 12,
        "skill": "docs/agency/inbox-agent.md",
        "keywords": (
            "kundenfrage", "support", "inbox", "faq kunde", "account manager",
            "beschwerde", "ticket",
        ),
        "cursor": "Inbox/FAQ/Queue. Eskalation an Christian bei heikel.",
    },
    "service": {
        "label": "Service-Wächter",
        "wf": 13,
        "skill": ".cursor/skills/nils/SKILL.md",
        "keywords": (
            "proaktiv", "kunden portal down", "wartung kunde", "service wächter",
            "ausfall kunde", "monitoring kunde",
        ),
        "cursor": "Watchdog/Health für Kundenportale. Fix + kurze Meldung.",
    },
    "radar": {
        "label": "Radar / Trend-Scout",
        "wf": 14,
        "skill": "docs/agency/trend-scout.md",
        "keywords": (
            "radar", "trend", "scout tools", "neue api", "opensource", "open source",
            "oss", "huggingface", "neues tool", "markt beobachten", "wissen",
            "install kandidat", "was ist neu", "forum", "selfhosted",
        ),
        "cursor": "Radar-Report + Install-Queue. Nichts installieren ohne Christians OK.",
    },
    "shipcheck": {
        "label": "Freigabe-Check",
        "wf": 15,
        "skill": "docs/agency/shipcheck.md",
        "keywords": (
            "shipcheck", "freigabe", "link prüfen", "link pruefen", "url check",
            "dashboard prüfen", "dashboard pruefen", "toten link", "smoke link",
            "darf ich schicken", "check link", "vor freigabe", "link testen",
        ),
        "cursor": "agency_shipcheck: Links/Dashboards HTTP-Smoke. Nur bei ship=true an Christian.",
    },
}

# Router selbst ist Workflow 1 – kein Agent, orchestriert nur
ROUTER_WF = 1

ORDER = [
    "stefan",
    "anwalt",
    "nils",
    "radar",
    "shipcheck",
    "service",
    "scout",
    "outreach",
    "crm",
    "finanz",
    "account",
    "texter",
    "design",
    "lektor",
]

SCHEMA: dict[str, Any] = {
    "title": "Webschmiede Agency Router (13 Workflows)",
    "type": "object",
    "required": ["mitarbeiter", "prioritaet", "payload"],
    "properties": {
        "mitarbeiter": {
            "type": "array",
            "items": {"type": "string", "enum": list(AGENTS.keys())},
        },
        "prioritaet": {"type": "string", "enum": ["hoch", "normal", "niedrig"]},
        "payload": {"type": "string"},
        "ziel": {"type": "string"},
        "context": {"type": "string"},
        "force_agent": {"type": "string", "enum": list(AGENTS.keys())},
    },
}

SYSTEM_PROMPT = """Du bist der zentrale Koordinator (Workflow 1) der Webschmiede.
Antworte nur als JSON. Mitarbeiter-IDs:
stefan, scout, outreach, crm, texter, design, lektor, nils, radar, shipcheck, anwalt, finanz, account, service.
Regeln: Text schreiben → texter+lektor. Vertrag+Anschreiben → anwalt+texter+lektor.
Ops/Deploy → nils. Trends/Tools/OSS → radar. Links/Dashboards vor Christian → shipcheck.
Unklar → stefan. Akquise-Suche → scout. Nachfass → crm.
"""

WORKFLOW_REGISTRY: list[dict[str, Any]] = [
    {"wf": 1, "id": "router", "name": "Zentraler Router / Hirn", "status": "live", "impl": "agency_brain dispatch + agency_router + n8n webhook agency-brain"},
    {"wf": 2, "id": "stefan", "name": "Stefan CEO", "status": "live", "impl": "plan + growth + filter + commander"},
    {"wf": 3, "id": "scout", "name": "Markt-Scout", "status": "live", "impl": "/api/agency/scout/campaign + akquise"},
    {"wf": 4, "id": "outreach", "name": "Outreach", "status": "live", "impl": "Scout-Entwuerfe + Freigabe (kein Auto-Send)"},
    {"wf": 5, "id": "crm", "name": "CRM Follow-Up", "status": "live", "impl": "workflow-followups + akquise-reminders"},
    {"wf": 6, "id": "texter", "name": "Premium-Texter", "status": "live", "impl": "Cursor skill texter"},
    {"wf": 7, "id": "design", "name": "Kreativ/Design", "status": "live", "impl": "Cursor skill design"},
    {"wf": 8, "id": "lektor", "name": "Lektor", "status": "live", "impl": "Texter-Skill Lektor-Pass"},
    {"wf": 9, "id": "nils", "name": "Nils Infra", "status": "live", "impl": "skill nils + healthcheck + watchdog"},
    {"wf": 10, "id": "anwalt", "name": "Anwalt", "status": "live", "impl": "skill + /api/agency/anwalt/pipeline (3 Stufen)"},
    {"wf": 11, "id": "finanz", "name": "Finanz/Rechnung", "status": "partial", "impl": "buchhaltung n8n + DocuSeal"},
    {"wf": 12, "id": "account", "name": "Account-Manager", "status": "live", "impl": "inbox-agent"},
    {"wf": 13, "id": "service", "name": "Service-Wächter", "status": "live", "impl": "ops_guardian + nightly/route/resource watchdogs"},
    {"wf": 14, "id": "radar", "name": "Radar / Trend-Scout", "status": "live", "impl": "agency_radar + Wochenreport + Install-Queue (kein Auto-Install)"},
    {"wf": 15, "id": "shipcheck", "name": "Freigabe-Check", "status": "live", "impl": "agency_shipcheck + Rule shipcheck.mdc (Links nur bei ship=true)"},
]


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"\s+", " ", s)


def _score_agents(text: str) -> dict[str, int]:
    t = _norm(text)
    scores = {aid: 0 for aid in AGENTS}
    for aid, meta in AGENTS.items():
        for kw in meta["keywords"]:
            if _norm(kw) in t:
                scores[aid] += 2 if len(kw) > 5 else 1
    if any(x in t for x in ("vertrag", "avv", "agb")) and any(
        x in t for x in ("anschreiben", "mail", "email", "schreib")
    ):
        scores["anwalt"] += 3
        scores["texter"] += 3
    if any(x in t for x in ("schreib", "text", "mail", "anschreiben", "copy", "outreach")):
        scores["texter"] = max(scores["texter"], 2)
        scores["lektor"] = max(scores["lektor"], 2)
    if scores["texter"] > 0 and scores["lektor"] == 0:
        scores["lektor"] = scores["texter"]
    if scores["outreach"] > 0:
        scores["lektor"] = max(scores["lektor"], 1)
    return scores


def _priority(text: str, agents: list[str]) -> str:
    t = _norm(text)
    if any(x in t for x in ("dringend", "sofort", "kritisch", "down", "ausfall", "heute noch")):
        return "hoch"
    if "nils" in agents or "service" in agents:
        if any(x in t for x in ("down", "fehler", "broken", "502", "500")):
            return "hoch"
    if "anwalt" in agents:
        return "hoch"
    return "normal"


def _ziel(text: str, agents: list[str]) -> str:
    labels = [AGENTS[a]["label"] for a in agents]
    if not labels:
        return "Unklar – Stefan"
    short = (text or "").strip().replace("\n", " ")
    if len(short) > 120:
        short = short[:117] + "…"
    return f"{', '.join(labels)}: {short}"


def classify(
    message: str,
    *,
    source: str = "api",
    force_agent: str | None = None,
    tenant_id: str | None = None,
    redact: bool = True,
) -> dict[str, Any]:
    msg = (message or "").strip()
    forced = (force_agent or "").strip().lower() or None
    if forced and forced not in AGENTS:
        forced = None
    tenant = router_sec.normalize_tenant(tenant_id)
    pii_flags = router_sec.detect_pii(msg)
    llm_ok, llm_reason = router_sec.llm_allowed_for_message(msg)

    if not msg and not forced:
        return router_sec.sanitize_result(
            {
                "ok": False,
                "error": "message fehlt",
                "mitarbeiter": ["stefan"],
                "target_agents": ["stefan"],
                "prioritaet": "niedrig",
                "payload": "",
                "ziel": "Leere Nachricht",
                "context": "",
                "cursor_briefings": [],
                "workflows": [2],
                "source": source,
                "tenant_id": tenant,
                "pii_flags": pii_flags,
            },
            redact_payload=redact,
        )

    if forced:
        agents = [forced]
        if forced == "texter":
            agents.append("lektor")
        if forced == "outreach":
            agents = ["outreach", "texter", "lektor"]
        llm_used = False
    else:
        scores = _score_agents(msg)
        ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        agents = [aid for aid, sc in ranked if sc > 0]
        if not agents:
            agents = ["stefan"]
        agents = [a for a in ORDER if a in agents] + [a for a in agents if a not in ORDER]
        llm_used = False
        if llm_ok:
            # Nur redigierte Nachricht an externes LLM
            llm = _classify_llm(router_sec.redact_pii(msg))
            if llm:
                llm_used = True
                llm["tenant_id"] = tenant
                llm["pii_flags"] = pii_flags
                llm["llm_reason"] = llm_reason
                return router_sec.sanitize_result(llm, redact_payload=redact)

    briefings = [
        {
            "agent": a,
            "label": AGENTS[a]["label"],
            "workflow": AGENTS[a]["wf"],
            "skill": AGENTS[a]["skill"],
            "instruction": AGENTS[a]["cursor"],
        }
        for a in agents
    ]
    scores = _score_agents(msg) if msg else {}

    result = {
        "ok": True,
        "mitarbeiter": agents,
        "target_agents": agents,
        "prioritaet": _priority(msg, agents),
        "payload": msg or forced or "",
        "ziel": _ziel(msg or forced or "", agents),
        "context": (msg or "")[:500],
        "cursor_briefings": briefings,
        "workflows": [ROUTER_WF] + [AGENTS[a]["wf"] for a in agents],
        "system_prompt_hint": SYSTEM_PROMPT[:180] + "…",
        "source": source,
        "scores": {k: v for k, v in scores.items() if v},
        "registry": WORKFLOW_REGISTRY,
        "tenant_id": tenant,
        "pii_flags": pii_flags,
        "llm_used": llm_used,
        "llm_reason": llm_reason if not llm_used else "ok",
    }
    return router_sec.sanitize_result(result, redact_payload=redact)


def _classify_llm(message: str) -> dict[str, Any] | None:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    try:
        import urllib.request

        body = json.dumps(
            {
                "model": os.getenv("OPENAI_ROUTER_MODEL", "gpt-4o-mini"),
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                        + "\nErlaubte IDs: "
                        + ",".join(AGENTS.keys()),
                    },
                    {"role": "user", "content": message},
                ],
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        parsed = json.loads(data["choices"][0]["message"]["content"])
        agents = [a for a in parsed.get("mitarbeiter") or parsed.get("target_agents") or [] if a in AGENTS]
        if not agents:
            return None
        if "texter" in agents and "lektor" not in agents:
            agents.append("lektor")
        agents = [a for a in ORDER if a in agents] + [a for a in agents if a not in ORDER]
        briefings = [
            {
                "agent": a,
                "label": AGENTS[a]["label"],
                "workflow": AGENTS[a]["wf"],
                "skill": AGENTS[a]["skill"],
                "instruction": AGENTS[a]["cursor"],
            }
            for a in agents
        ]
        return {
            "ok": True,
            "mitarbeiter": agents,
            "target_agents": agents,
            "prioritaet": parsed.get("prioritaet") or _priority(message, agents),
            "payload": parsed.get("payload") or message,
            "ziel": parsed.get("ziel") or _ziel(message, agents),
            "context": parsed.get("context") or message[:500],
            "cursor_briefings": briefings,
            "workflows": [ROUTER_WF] + [AGENTS[a]["wf"] for a in agents],
            "source": "llm",
            "registry": WORKFLOW_REGISTRY,
        }
    except Exception:
        return None


def cursor_playbook(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return result.get("error") or "Router fehlgeschlagen"
    lines = [
        f"**Router (WF1):** {result.get('ziel')}",
        f"**Priorität:** {result.get('prioritaet')}",
        f"**Mitarbeiter:** {', '.join(result.get('mitarbeiter') or [])}",
        f"**Workflows:** {', '.join(str(w) for w in (result.get('workflows') or []))}",
        "",
        "Reihenfolge:",
    ]
    for i, b in enumerate(result.get("cursor_briefings") or [], 1):
        lines.append(
            f"{i}. **{b['label']}** (WF{b.get('workflow')}) – {b['instruction']} (`{b['skill']}`)"
        )
    lines.append("")
    lines.append("Ergebnisse am Ende zusammenfassen. Kein Spam, keine Käufe ohne OK.")
    return "\n".join(lines)


def registry() -> dict[str, Any]:
    return {
        "ok": True,
        "count": len(WORKFLOW_REGISTRY),
        "workflows": WORKFLOW_REGISTRY,
        "agents": {k: {"label": v["label"], "wf": v["wf"], "skill": v["skill"]} for k, v in AGENTS.items()},
    }

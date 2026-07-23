"""Agency-Hirn: Router klassifiziert, dann Dispatch an Mitarbeiter-APIs (in-process).

Cursor-Chat geht nicht automatisch hier rein – Agent muss /api/agency/brain
oder scripts/agency_brain_cli.py nutzen. Kein Auto-Send an Kunden.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import agency_router as router
import agency_stefan as stefan
import agency_scout as scout
import agency_commander as commander
import dual_infra as dual

try:
    import agency_anwalt as anwalt
except Exception:  # pragma: no cover
    anwalt = None  # type: ignore

try:
    import agency_radar as radar
except Exception:  # pragma: no cover
    radar = None  # type: ignore

try:
    import agency_shipcheck as shipcheck
except Exception:  # pragma: no cover
    shipcheck = None  # type: ignore

BRAIN_VERSION = "1.1"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dispatch_stefan(message: str, route: dict[str, Any]) -> dict[str, Any]:
    t = (message or "").lower()
    if any(x in t for x in ("guru", "reality", "brauch ich", "95%", "helsinki", "speedscal")):
        return {"mode": "filter", **stefan.filter_idea(message)}
    if any(x in t for x in ("wachstum", "funnel", "landing", "growth")):
        return {"mode": "growth", **stefan.growth_plan(message)}
    return {"mode": "plan", **stefan.plan_project(message)}


def _dispatch_scout(message: str, route: dict[str, Any]) -> dict[str, Any]:
    vertical = ""
    low = (message or "").lower()
    for v in ("baustoff", "gastro", "handwerk", "dach", "dental", "friseur", "elektro"):
        if v in low:
            vertical = v
            break
    camp = scout.campaign(vertical=vertical, limit=5, ticket="5000")
    return {
        "ok": camp.get("ok", True),
        "vertical": vertical or None,
        "count": camp.get("count"),
        "strategy": camp.get("strategy"),
        "leads_preview": [
            {
                "name": x.get("name"),
                "score": x.get("score"),
                "subject": (x.get("outreach") or {}).get("subject"),
            }
            for x in (camp.get("leads") or [])[:5]
        ],
        "auto_send": False,
        "hinweis": camp.get("hinweis") or "Nur Entwuerfe. Versand nach Freigabe.",
    }


def _dispatch_outreach(message: str, route: dict[str, Any]) -> dict[str, Any]:
    # Outreach haengt an Scout-Queue
    out = _dispatch_scout(message, route)
    out["role"] = "outreach"
    out["note"] = "Outreach-Texte stecken in Scout-Campaign (Freigabe Pflicht)."
    return out


def _dispatch_nils(message: str, route: dict[str, Any]) -> dict[str, Any]:
    status = dual.dual_status(use_ssh=True)
    return {
        "ok": status.get("ok"),
        "dual": {
            "web": {
                "ok": (status.get("web") or {}).get("ok"),
                "snack_api": (status.get("web") or {}).get("snack_api"),
                "ram_pct": (status.get("web") or {}).get("ram_pct"),
            },
            "auto": {
                "ok": (status.get("auto") or {}).get("ok"),
                "n8n": (status.get("auto") or {}).get("n8n"),
                "ram_pct": (status.get("auto") or {}).get("ram_pct"),
            },
            "alerts": status.get("alerts") or [],
        },
        "pitch_safe": status.get("customer_pitch_safe"),
        "cursor": "Als Nils weiterarbeiten wenn Alerts oder Ops-Frage.",
    }


def _dispatch_service(message: str, route: dict[str, Any]) -> dict[str, Any]:
    base = _dispatch_nils(message, route)
    base["role"] = "service"
    base["note"] = "Service-Waechter: Dual-Health. Kundenportal-Watchdogs laufen separat (nightly)."
    return base


def _dispatch_anwalt(message: str, route: dict[str, Any]) -> dict[str, Any]:
    if anwalt is None:
        return {"ok": False, "error": "agency_anwalt nicht geladen", "cursor": "Skill anwalt"}
    if hasattr(anwalt, "pipeline_3_stufen"):
        full = anwalt.pipeline_3_stufen(brief=message)
        return {
            "ok": True,
            "mode": "pipeline",
            "ampel": full.get("ampel"),
            "firma": full.get("firma"),
            "findings": (full.get("findings") or [])[:12],
            "protokoll": (full.get("protokoll") or "")[:2000],
            "rechtskraft": False,
            "note": "Volltext via /api/agency/anwalt/pipeline",
        }
    if hasattr(anwalt, "enterprise_pack"):
        return {"ok": True, "mode": "pack", "pack": anwalt.enterprise_pack()}
    return {"ok": True, "cursor": "Skill anwalt /api/agency/anwalt/pipeline", "brief": message[:400]}


def _dispatch_commander(message: str, route: dict[str, Any]) -> dict[str, Any]:
    brief = commander.daily_briefing(scout_limit=5, ticket="5000")
    return {
        "ok": brief.get("ok", True),
        "todos_christian": brief.get("todos_christian") or brief.get("todos") or [],
        "markdown_excerpt": (brief.get("markdown") or "")[:1500],
        "auto_send": False,
    }


def _dispatch_radar(message: str, route: dict[str, Any]) -> dict[str, Any]:
    if radar is None:
        return {"ok": False, "error": "agency_radar fehlt"}
    t = (message or "").lower()
    if any(x in t for x in ("status", "queue", "queue zeigen")):
        return radar.status()
    live = "offline" not in t and "ohne live" not in t
    # Vollreport kann etwas dauern (HTTP)
    return radar.build_report(live=live)


def _dispatch_shipcheck(message: str, route: dict[str, Any]) -> dict[str, Any]:
    if shipcheck is None:
        return {"ok": False, "error": "agency_shipcheck fehlt"}
    t = (message or "").lower()
    for key in ("agency-setup", "b2b", "health", "yassine", "whatsapp-webhook"):
        if key in t and "http" not in t:
            return shipcheck.check_dashboard(key)
    return shipcheck.gate_before_share(message)


def _dispatch_cursor_only(agent: str) -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    meta = router.AGENTS.get(agent) or {}

    def _fn(message: str, route: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "mode": "cursor_skill",
            "agent": agent,
            "label": meta.get("label"),
            "skill": meta.get("skill"),
            "instruction": meta.get("cursor"),
            "payload": message[:2000],
            "note": "Dieser Mitarbeiter laeuft in Cursor (Skill), nicht als Server-Job.",
        }

    return _fn


DISPATCHERS: dict[str, Callable[[str, dict[str, Any]], dict[str, Any]]] = {
    "stefan": _dispatch_stefan,
    "scout": _dispatch_scout,
    "outreach": _dispatch_outreach,
    "nils": _dispatch_nils,
    "service": _dispatch_service,
    "anwalt": _dispatch_anwalt,
    "crm": _dispatch_cursor_only("crm"),
    "texter": _dispatch_cursor_only("texter"),
    "design": _dispatch_cursor_only("design"),
    "lektor": _dispatch_cursor_only("lektor"),
    "finanz": _dispatch_cursor_only("finanz"),
    "account": _dispatch_cursor_only("account"),
    "radar": _dispatch_radar,
    "shipcheck": _dispatch_shipcheck,
}


def process(
    message: str,
    *,
    source: str = "api",
    force_agent: str | None = None,
    tenant_id: str = "AGENCY",
    dispatch: bool = True,
    include_commander: bool = False,
    max_agents: int = 4,
    fast: bool = False,
) -> dict[str, Any]:
    """Klassifizieren und optional Mitarbeiter ausfuehren."""
    route = router.classify(
        message,
        source=source,
        force_agent=force_agent,
        tenant_id=tenant_id,
        redact=True,
    )
    playbook = router.cursor_playbook(route)
    agents = list(route.get("mitarbeiter") or route.get("target_agents") or [])[: max(1, max_agents)]

    results: dict[str, Any] = {}
    errors: list[str] = []
    if dispatch and route.get("ok"):
        # Stefan zuerst wenn dabei
        ordered = [a for a in router.ORDER if a in agents] + [a for a in agents if a not in router.ORDER]
        for aid in ordered:
            # Cursor-Hook: Dual-SSH nur bei echten Ops-Keywords (sonst zu langsam)
            if fast and aid in ("nils", "service"):
                ops = any(
                    x in (message or "").lower()
                    for x in ("server", "deploy", "dual", "down", "n8n", "watchdog", "ssl", "nginx")
                )
                if not ops:
                    results[aid] = {
                        "ok": True,
                        "mode": "fast",
                        "note": "Ops-Check uebersprungen (fast). Bei Bedarf Dual-Status nachziehen.",
                        "topology": dual.topology(),
                    }
                    continue
            fn = DISPATCHERS.get(aid)
            if not fn:
                results[aid] = {"ok": False, "error": "kein dispatcher"}
                continue
            try:
                results[aid] = fn(message, route)
            except Exception as exc:
                results[aid] = {"ok": False, "error": str(exc)[:240]}
                errors.append(f"{aid}: {exc}"[:200])
        want_cmd = include_commander or any(
            x in (message or "").lower() for x in ("briefing", "tagesplan", "wochenplan", "commander")
        )
        if want_cmd:
            try:
                results["commander"] = _dispatch_commander(message, route)
            except Exception as exc:
                results["commander"] = {"ok": False, "error": str(exc)[:200]}

    # Auto-Gate: URLs im Text → immer Shipcheck, auch wenn nicht geroutet
    gate: dict[str, Any] | None = None
    msg_low = (message or "").lower()
    if dispatch and shipcheck is not None and ("http://" in msg_low or "https://" in msg_low):
        if "shipcheck" not in results:
            try:
                gate = shipcheck.gate_before_share(message)
                results["shipcheck"] = gate
                if "shipcheck" not in agents:
                    agents = list(agents) + ["shipcheck"]
            except Exception as exc:
                results["shipcheck"] = {"ok": False, "ship": False, "error": str(exc)[:200]}
                errors.append(f"shipcheck: {exc}"[:200])
        else:
            gate = results.get("shipcheck") if isinstance(results.get("shipcheck"), dict) else None

    sharp = bool(route.get("ok")) and (not dispatch or bool(results))
    if gate and gate.get("skipped") is False and not gate.get("ship"):
        sharp = False
    summary_lines = [
        f"Hirn {BRAIN_VERSION} · {_now()}",
        f"Ziel: {route.get('ziel')}",
        f"Prio: {route.get('prioritaet')}",
        f"Mitarbeiter: {', '.join(agents) or '–'}",
        f"Dispatch: {'an' if dispatch else 'aus (nur Routing)'}",
    ]
    if errors:
        summary_lines.append("Fehler: " + "; ".join(errors))
    for aid, res in results.items():
        if aid == "stefan" and res.get("ok"):
            summary_lines.append(f"- Stefan ({res.get('mode')}): ok")
        elif aid == "scout":
            summary_lines.append(f"- Scout: {res.get('count') or 0} Leads (Entwuerfe)")
        elif aid == "nils":
            summary_lines.append(f"- Nils Dual: {'ok' if res.get('ok') else 'alarm'}")
        elif aid == "commander":
            todos = res.get("todos_christian") or []
            summary_lines.append(f"- Commander: {len(todos)} Todos fuer dich")
        elif aid == "radar":
            summary_lines.append(
                f"- Radar: Report {res.get('path') or 'ok'} · Queue {len(res.get('pending_installs') or [])}"
            )
        elif aid == "shipcheck":
            summary_lines.append(
                f"- Shipcheck: {res.get('summary') or ('FREIGABE OK' if res.get('ship') else 'NICHT SCHICKEN')}"
            )
        elif isinstance(res, dict) and res.get("mode") == "cursor_skill":
            summary_lines.append(f"- {aid}: Cursor-Skill ({res.get('skill')})")
        elif isinstance(res, dict) and res.get("ok") is False:
            summary_lines.append(f"- {aid}: FEHLER {res.get('error')}")

    return {
        "ok": sharp and not errors,
        "sharp": sharp,
        "brain_version": BRAIN_VERSION,
        "as_of": _now(),
        "route": route,
        "playbook": playbook,
        "dispatched": dispatch,
        "agents": agents,
        "results": results,
        "errors": errors,
        "ship": None if gate is None else bool(gate.get("ship")),
        "summary": "\n".join(summary_lines),
        "honest": (
            "Cursor-Chat wird nicht magisch mitgelesen. "
            "Scharf = dieses Hirn-API/CLI + n8n-Webhooks auf den Server-APIs. "
            "Kein Auto-Spam an Kunden. Links nur bei ship=true."
        ),
    }


def markdown(data: dict[str, Any] | None = None, message: str = "") -> str:
    data = data or process(message)
    lines = [
        "# Agency-Hirn",
        data.get("summary") or "",
        "",
        "## Playbook",
        data.get("playbook") or "",
        "",
        "## Ehrlichkeit",
        data.get("honest") or "",
    ]
    return "\n".join(lines)

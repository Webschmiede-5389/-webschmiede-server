#!/usr/bin/env python3
"""Erzeugt n8n-Stub-Workflows für das 13er Agency-System."""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "infra" / "n8n" / "agency-system"

WORKFLOWS = [
    {
        "id": "01",
        "slug": "router",
        "name": "Agency 01 – Router (Gehirn)",
        "path": "agency-01-router",
        "note": "Delegiert an Flask /api/agency/router. Produktiv: infra/n8n/workflow-agency-router.json",
        "url": "https://digitalehandwerkskunst.de/api/agency/router",
    },
    {
        "id": "02",
        "slug": "stefan",
        "name": "Agency 02 – Stefan Schlachtplan",
        "path": "agency-02-stefan",
        "note": "POST brief+firma → /api/agency/stefan/plan. Kein Auto-Send.",
        "url": "https://digitalehandwerkskunst.de/api/agency/stefan/plan",
        "method": "POST",
    },
    {
        "id": "03",
        "slug": "scout",
        "name": "Agency 03 – Markt-Scout",
        "path": "agency-03-scout",
        "note": "Akquise-Engine lokal: python -m akquise / agency_akquise. Webhook startet Queue-Hinweis.",
        "url": "https://digitalehandwerkskunst.de/api/agency/akquise/queue",
        "method": "GET",
    },
    {
        "id": "04",
        "slug": "outreach",
        "name": "Agency 04 – Outreach",
        "path": "agency-04-outreach",
        "note": "Texte nur nach Freigabe. Nutzt Router→texter+lektor. Kein Spam-Auto-Send.",
        "url": "https://digitalehandwerkskunst.de/api/agency/router",
        "body_agent": "outreach",
    },
    {
        "id": "05",
        "slug": "crm",
        "name": "Agency 05 – CRM Follow-Up",
        "path": "agency-05-crm",
        "note": "Bestehend: workflow-followups.json + workflow-akquise-reminders.json",
        "url": "https://digitalehandwerkskunst.de/api/cron/followups",
        "method": "POST",
        "cron": "0 10 * * *",
    },
    {
        "id": "06",
        "slug": "texter",
        "name": "Agency 06 – Premium-Texter",
        "path": "agency-06-texter",
        "note": "Cursor Skill texter. n8n: Klassifizierung + Playbook.",
        "url": "https://digitalehandwerkskunst.de/api/agency/router",
        "body_agent": "texter",
    },
    {
        "id": "07",
        "slug": "design",
        "name": "Agency 07 – Kreativ/Design",
        "path": "agency-07-design",
        "note": "Cursor Skill design. Bild-API nur nach Christians OK.",
        "url": "https://digitalehandwerkskunst.de/api/agency/router",
        "body_agent": "design",
    },
    {
        "id": "08",
        "slug": "lektor",
        "name": "Agency 08 – Lektor",
        "path": "agency-08-lektor",
        "note": "Immer nach Texter. Skill texter (Lektor-Pass).",
        "url": "https://digitalehandwerkskunst.de/api/agency/router",
        "body_agent": "lektor",
    },
    {
        "id": "09",
        "slug": "nils",
        "name": "Agency 09 – Nils Infra",
        "path": "agency-09-nils",
        "note": "Bestehend: workflow-healthcheck + nightly_watchdog. Skill nils.",
        "url": "https://digitalehandwerkskunst.de/api/health",
        "method": "GET",
        "cron": "*/15 * * * *",
    },
    {
        "id": "10",
        "slug": "anwalt",
        "name": "Agency 10 – Anwalt",
        "path": "agency-10-anwalt",
        "note": "Cursor Skill anwalt + Checkliste. Vorprüfung, kein Ersatz Anwalt.",
        "url": "https://digitalehandwerkskunst.de/api/agency/router",
        "body_agent": "anwalt",
    },
    {
        "id": "11",
        "slug": "finanz",
        "name": "Agency 11 – Finanz/Rechnung",
        "path": "agency-11-finanz",
        "note": "Bestehend: workflow-buchhaltung-monat, meta-rechnungen, DocuSeal Angebote.",
        "url": "https://digitalehandwerkskunst.de/api/agency/router",
        "body_agent": "finanz",
    },
    {
        "id": "12",
        "slug": "account",
        "name": "Agency 12 – Account-Manager",
        "path": "agency-12-account",
        "note": "Bestehend: workflow-inbox-agent + inbox-digest.",
        "url": "https://digitalehandwerkskunst.de/api/agency/inbox/stats",
        "method": "GET",
    },
    {
        "id": "13",
        "slug": "service",
        "name": "Agency 13 – Service-Wächter",
        "path": "agency-13-service",
        "note": "Bestehend: nightly_watchdog + resource_watchdog + healthcheck.",
        "url": "https://digitalehandwerkskunst.de/api/cron/nightly-watchdog",
        "method": "POST",
        "cron": "30 3 * * *",
    },
]


def make_workflow(wf: dict) -> dict:
    method = wf.get("method", "POST")
    nodes = []
    connections = {}
    x = 0

    if wf.get("cron"):
        nodes.append(
            {
                "parameters": {
                    "rule": {"interval": [{"field": "cronExpression", "expression": wf["cron"]}]}
                },
                "id": f"{wf['id']}-cron",
                "name": "Zeitplan",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.2,
                "position": [x, 0],
            }
        )
        start = "Zeitplan"
        x += 220
    else:
        nodes.append(
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": wf["path"],
                    "responseMode": "responseNode",
                    "options": {},
                },
                "id": f"{wf['id']}-wh",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [x, 0],
                "webhookId": wf["path"],
            }
        )
        start = "Webhook"
        x += 220

    http_params: dict = {
        "method": method,
        "url": wf["url"],
        "sendHeaders": True,
        "headerParameters": {
            "parameters": [
                {"name": "Content-Type", "value": "application/json"},
                {"name": "X-Cron-Secret", "value": "={{$env.CRON_SECRET}}"},
                {"name": "X-Agency-Password", "value": "={{$env.AGENCY_ADMIN_PASSWORD}}"},
            ]
        },
        "options": {"timeout": 60000},
    }
    if method == "POST":
        http_params["sendBody"] = True
        http_params["specifyBody"] = "json"
        if wf.get("body_agent"):
            http_params["jsonBody"] = (
                "={{ JSON.stringify({ message: ($json.body && ($json.body.message || $json.body.text)) "
                f"|| $json.message || 'Starte {wf['slug']}', force_agent: '{wf['body_agent']}' }})"
            )
        else:
            http_params["jsonBody"] = "={{ JSON.stringify($json.body || $json || {}) }}"

    nodes.append(
        {
            "parameters": http_params,
            "id": f"{wf['id']}-http",
            "name": "Agency API",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [x, 0],
        }
    )
    connections[start] = {"main": [[{"node": "Agency API", "type": "main", "index": 0}]]}
    x += 220

    nodes.append(
        {
            "parameters": {
                "jsCode": (
                    f"const j=$input.first().json;\n"
                    f"return [{{ json: {{ ok: true, workflow: '{wf['slug']}', "
                    f"note: {json.dumps(wf['note'])}, result: j }} }}];"
                )
            },
            "id": f"{wf['id']}-pack",
            "name": "Ergebnis",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [x, 0],
        }
    )
    connections["Agency API"] = {"main": [[{"node": "Ergebnis", "type": "main", "index": 0}]]}
    x += 220

    if not wf.get("cron"):
        nodes.append(
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ $json }}",
                    "options": {},
                },
                "id": f"{wf['id']}-resp",
                "name": "Antwort",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [x, 0],
            }
        )
        connections["Ergebnis"] = {"main": [[{"node": "Antwort", "type": "main", "index": 0}]]}

    return {
        "name": wf["name"],
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "meta": {"notes": wf["note"]},
        "tags": [{"name": "agency"}, {"name": "system-13"}, {"name": wf["slug"]}],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for wf in WORKFLOWS:
        data = make_workflow(wf)
        path = OUT / f"{wf['id']}-{wf['slug']}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        index.append(
            {
                "id": wf["id"],
                "slug": wf["slug"],
                "name": wf["name"],
                "file": path.name,
                "note": wf["note"],
            }
        )
        print("wrote", path.name)
    (OUT / "INDEX.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print("INDEX.json", len(index), "workflows ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

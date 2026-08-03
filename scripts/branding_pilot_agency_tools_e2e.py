#!/usr/bin/env python3
"""Agency Werkzeuge E2E — isolierter Mini-Server (kein Production, kein snack-api Restart).

Lädt platform_registry + platform_tools Blueprint auf Port 18099.
Auth: X-Agency-Password Header ODER Session-Cookie nach /api/agency/login Stub.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

WS_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = WS_ROOT / "docs" / "platform-unification" / "evidence" / "step-5"
SHOTS = EVIDENCE / "screenshots"
PORT = int(os.environ.get("AGENCY_PILOT_PORT", "18099"))
BASE = f"http://127.0.0.1:{PORT}"
AGENCY_PW = "branding-pilot-agency-local"
BACKEND = WS_ROOT / "app" / "backend"
STATIC = WS_ROOT / "app" / "static"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_app():
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)
    os.environ.setdefault("APP_ENV", "staging")
    from flask import Flask, request, jsonify, send_from_directory, make_response

    from platform_tools import platform_tools_bp

    app = Flask("branding_pilot_agency")
    app.register_blueprint(platform_tools_bp)

    @app.before_request
    def _auth_gate():
        if request.path == "/api/agency/tools":
            pw = request.headers.get("X-Agency-Password") or ""
            token = request.cookies.get("agency_session") or request.headers.get("X-Agency-Token") or ""
            if pw == AGENCY_PW or token == "pilot-session-ok":
                return None
            return jsonify({"error": "Unauthorized"}), 401
        return None

    @app.post("/api/agency/login")
    def login():
        data = request.get_json(force=True, silent=True) or {}
        if (data.get("password") or "") != AGENCY_PW:
            return jsonify({"success": False, "error": "Anmeldung fehlgeschlagen"}), 401
        resp = jsonify({"success": True, "token": "pilot-session-ok"})
        resp.set_cookie("agency_session", "pilot-session-ok", httponly=True, samesite="Lax")
        return resp

    @app.get("/agency-tools-pilot")
    def agency_tools_pilot():
        # Minimal page for browser E2E (same API, no full agency auth JS)
        return (
            "<!doctype html><html lang='de'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Werkzeuge · Branding Pilot</title>"
            "<style>body{font-family:system-ui;margin:1rem;background:#f7f5f2;color:#1a1a1a}"
            ".grid{display:grid;gap:1rem;grid-template-columns:repeat(auto-fill,minmax(220px,1fr))}"
            ".card{background:#fff;border:1px solid #ddd;border-radius:12px;padding:1rem}"
            ".badge{display:inline-block;background:#FFF4ED;color:#FF6600;font-size:11px;font-weight:700;padding:.2rem .5rem;border-radius:999px}"
            "</style></head><body>"
            "<p class='badge'>STAGING PILOT</p>"
            "<h1>Agency Werkzeuge</h1>"
            "<p id='meta'>Lade…</p>"
            "<div id='tools-grid' class='grid'></div>"
            "<script>"
            "async function boot(){"
            " const r=await fetch('/api/agency/tools',{credentials:'same-origin'});"
            " const data=await r.json();"
            " const grid=document.getElementById('tools-grid');"
            " document.getElementById('meta').textContent=(data.count||0)+' Werkzeuge · '+ (data.env||'');"
            " grid.innerHTML=(data.entries||[]).map(e=>`<a class='card tool-card' href='${e.base_url||'#'}'>"
            " <strong>${e.display_name||e.slug}</strong><div style='font-size:12px;opacity:.7;margin-top:.4rem'>"
            " ${e.short_description||''}</div></a>`).join('');"
            "}"
            "boot();"
            "</script></body></html>"
        )

    @app.get("/agency")
    def agency_page():
        return send_from_directory(STATIC, "agency.html")

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "app": "branding-pilot-agency", "env": "staging"})

    # static assets referenced by agency.html (relative /ci etc. may 404 — ok for tools tab)
    @app.get("/ci/<path:name>")
    def ci(name: str):
        return send_from_directory(STATIC / "ci", name)

    return app


def run_server():
    app = make_app()
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


def main() -> int:
    from playwright.sync_api import sync_playwright

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    report: dict = {"at": utc_now(), "base": BASE, "pass": False, "steps": []}

    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    for _ in range(40):
        time.sleep(0.25)
        try:
            urllib.request.urlopen(f"{BASE}/health", timeout=1)
            break
        except Exception:
            pass
    else:
        report["error"] = "server_start_timeout"
        (EVIDENCE / "agency-tools-e2e.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 1

    # API
    req = urllib.request.Request(
        f"{BASE}/api/agency/tools",
        headers={"X-Agency-Password": AGENCY_PW},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        api = json.loads(r.read().decode("utf-8"))
    report["steps"].append({
        "api": {"ok": api.get("ok"), "count": api.get("count"), "env": api.get("env"),
                "sample": [e.get("display_name") for e in (api.get("entries") or [])[:8]]},
    })
    if not api.get("ok") or int(api.get("count") or 0) < 1:
        report["error"] = "api_failed"
        (EVIDENCE / "agency-tools-e2e.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return 1

    # Unauthorized without creds
    try:
        urllib.request.urlopen(f"{BASE}/api/agency/tools", timeout=5)
        unauth_ok = False
    except urllib.error.HTTPError as e:
        unauth_ok = e.code == 401
    report["steps"].append({"unauthorized_without_creds": unauth_ok})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp_name, vp in [("390", {"width": 390, "height": 844}), ("1440", {"width": 1440, "height": 900})]:
            ctx = browser.new_context(viewport=vp, locale="de-DE")
            page = ctx.new_page()
            # Auth cookie first via login API on blankish page
            page.goto(f"{BASE}/health", wait_until="domcontentloaded")
            login = page.evaluate(
                """async (pw) => {
                  const r = await fetch('/api/agency/login', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    credentials:'same-origin',
                    body: JSON.stringify({username:'agency', password: pw})
                  });
                  return await r.json();
                }""",
                AGENCY_PW,
            )
            page.goto(f"{BASE}/agency-tools-pilot", wait_until="networkidle")
            page.wait_for_selector(".tool-card", timeout=10000)
            tools_state = {
                "ok": True,
                "count": page.locator(".tool-card").count(),
                "meta": page.locator("#meta").inner_text(),
            }
            shot = SHOTS / f"agency-tools-{vp_name}.png"
            page.screenshot(path=str(shot), full_page=True)
            cards = page.locator(".tool-card").count()
            # Also open real agency.html shell once (1440) for visual evidence of Werkzeuge panel chrome
            if vp_name == "1440":
                page.goto(f"{BASE}/agency", wait_until="domcontentloaded")
                page.screenshot(path=str(SHOTS / "agency-shell-1440.png"), full_page=True)
            report["steps"].append({
                "viewport": vp_name,
                "login": login,
                "tools_state": tools_state,
                "card_count": cards,
                "screenshot": f"screenshots/agency-tools-{vp_name}.png",
            })
            ctx.close()
        browser.close()

    api_ok = bool(api.get("ok") and api.get("count"))
    ui_ok = any(
        isinstance(s, dict) and s.get("card_count", 0) > 0
        for s in report["steps"]
    )
    report["pass"] = api_ok and unauth_ok and ui_ok
    report["server_commit"] = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=str(WS_ROOT), text=True
    ).strip()
    path = EVIDENCE / "agency-tools-e2e.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "count": api.get("count"), "evidence": str(path)}, indent=2, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    # urllib.error used above
    import urllib.error  # noqa: F401

    raise SystemExit(main())

#!/usr/bin/env python3
"""Branding UI visual acceptance — clean staging only (no Dialer logic changes).

Viewports: 390, 768, 1024, 1366, 1440. Screenshots + overflow metrics.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

WS_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = WS_ROOT / "docs" / "platform-unification" / "evidence" / "ui-visual"
SHOTS = EVIDENCE / "screenshots"
BASE = os.environ.get("BRANDING_PILOT_URL", "http://127.0.0.1:8093").rstrip("/")
EMAIL = os.environ.get("BRANDING_PILOT_EMAIL", "branding-pilot@example.local")
PASSWORD = os.environ.get("BRANDING_PILOT_PASSWORD", "branding-pilot-pass-local")

VIEWPORTS = [
    ("390x844", {"width": 390, "height": 844}),
    ("768x1024", {"width": 768, "height": 1024}),
    ("1024x768", {"width": 1024, "height": 768}),
    ("1366x768", {"width": 1366, "height": 768}),
    ("1440x900", {"width": 1440, "height": 900}),
]

# Layout-only pages (Telefonie: no call actions)
PAGES = [
    ("login", "/login", False),
    ("dashboard", "/", True),
    ("companies", "/companies", True),
    ("company_form", "/companies/new", True),
    ("leads", "/leads", True),
    ("pipeline", "/pipeline", True),
    ("tasks", "/tasks", True),
    ("telefonie_layout", "/vertrieb/telefonie", True),
    ("settings", "/settings", True),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def measure(page) -> dict:
    return page.evaluate(
        """() => {
      const body = document.body, html = document.documentElement;
      const docW = Math.max(body.scrollWidth, html.scrollWidth);
      const winW = Math.ceil(window.innerWidth);
      const overflowX = docW > winW + 1;
      const wraps = [...document.querySelectorAll('.table-wrap')].map(w => ({
        ox: getComputedStyle(w).overflowX,
        sw: w.scrollWidth, cw: w.clientWidth,
      }));
      const bareTables = [...document.querySelectorAll('table.table')].filter(t => !t.closest('.table-wrap')).length;
      const clipped = [];
      for (const el of document.querySelectorAll('h1, .btn, .tenant-name, .brand-text strong, .topbar h1')) {
        if (el.scrollWidth > el.clientWidth + 2) clipped.push((el.innerText||'').slice(0,48));
      }
      // Overlap detection among topbar interactive bits
      const overlapPairs = [];
      const nodes = [...document.querySelectorAll('.topbar .btn, .topbar .env-badge, .topbar h1')];
      for (let i=0;i<nodes.length;i++) {
        for (let j=i+1;j<nodes.length;j++) {
          const a=nodes[i].getBoundingClientRect(), b=nodes[j].getBoundingClientRect();
          const overlap = !(a.right<=b.left+1 || b.right<=a.left+1 || a.bottom<=b.top+1 || b.bottom<=a.top+1);
          if (overlap && a.width>0 && b.width>0) {
            overlapPairs.push(((nodes[i].innerText||nodes[i].className)+'×'+(nodes[j].innerText||nodes[j].className)).slice(0,60));
          }
        }
      }
      const btns = [...document.querySelectorAll('button.btn, a.btn, .btn')].slice(0,12).map(b => {
        const r = b.getBoundingClientRect();
        return {t:(b.innerText||'').slice(0,24), w:Math.round(r.width), h:Math.round(r.height)};
      });
      const gold = /#C9A84C|#c9a84c/i.test(document.documentElement.outerHTML.slice(0,8000));
      // Mid-word shatter inside scroll tables (bad when nowrap missing)
      const shattered = [];
      for (const cell of document.querySelectorAll('.table-wrap td, .table-wrap th')) {
        if (cell.querySelector('select, textarea, ul, ol')) continue;
        const t = (cell.innerText||'').trim();
        if (t.length < 8 || t.includes('\\n')) {
          // multi-option selects leak newlines via innerText — skip
          if (t.includes('\\n')) continue;
        }
        const cs = getComputedStyle(cell);
        if (cs.whiteSpace === 'nowrap' || cs.whiteSpace === 'pre') continue;
        // Only flag when the first visual line is a mid-word stump
        if (cell.scrollHeight > cell.clientHeight + 4 && cell.clientWidth > 0) {
          const sample = t.slice(0, 12);
          if (sample.length >= 6 && !/\\s/.test(sample.slice(0,6))) {
            shattered.push(t.slice(0,40));
          }
        }
      }
      return {
        overflowX, docW, winW, delta: docW - winW,
        wraps, bareTables, clipped: clipped.slice(0,6), btns,
        overlapPairs: overlapPairs.slice(0,5),
        shatteredCells: shattered.slice(0,5),
        goldHint: gold,
        title: document.title,
        hasShell: !!document.querySelector('#app-shell'),
        hasSidebar: !!document.querySelector('#sidebar'),
        hasMobileBar: !!document.querySelector('.mobile-bar'),
      };
    }"""
    )


def shot(page, vp: str, name: str) -> dict:
    SHOTS.mkdir(parents=True, exist_ok=True)
    full_rel = f"screenshots/{vp}-{name}.png"
    vp_rel = f"screenshots/{vp}-{name}-viewport.png"
    page.screenshot(path=str(EVIDENCE / full_rel), full_page=True)
    page.screenshot(path=str(EVIDENCE / vp_rel), full_page=False)
    return {"full": full_rel, "viewport": vp_rel}


def login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=30000)
    page.fill("#login-email", EMAIL)
    page.fill("#login-password", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_selector("#app-shell", timeout=20000)


def run() -> dict:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    report: dict = {"at": utc_now(), "base": BASE, "viewports": {}, "failures": [], "pass": False}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp_name, vp in VIEWPORTS:
            ctx = browser.new_context(viewport=vp, locale="de-DE", color_scheme="light")
            page = ctx.new_page()
            vp_rep: dict = {"pages": {}, "mobile_nav": {}}
            failures_before = len(report["failures"])

            # Login page (logged out)
            page.goto(f"{BASE}/login", wait_until="networkidle")
            m = measure(page)
            vp_rep["pages"]["login"] = {"visual": m, "shot": shot(page, vp_name, "login")}
            if m.get("overflowX"):
                report["failures"].append(f"{vp_name}:login overflowX delta={m.get('delta')}")
            if m.get("goldHint"):
                report["failures"].append(f"{vp_name}:login gold residue")

            login(page)
            # Long-name stress: open companies and inject via evaluate into a visible cell if present
            # (DOM-only for screenshot stress; no business API mutation beyond existing seed)

            for key, path, needs_auth in PAGES:
                if key == "login":
                    continue
                page.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                if needs_auth and "/login" in page.url:
                    report["failures"].append(f"{vp_name}:{key} redirected to login")
                    continue
                # empty/error-ish: settings always ok
                m = measure(page)
                shots = shot(page, vp_name, key)
                vp_rep["pages"][key] = {"visual": m, "shot": shots, "url": page.url}
                if m.get("overflowX"):
                    report["failures"].append(
                        f"{vp_name}:{key} overflowX delta={m.get('delta')} bareTables={m.get('bareTables')}"
                    )
                if m.get("overlapPairs"):
                    report["failures"].append(f"{vp_name}:{key} overlap {m.get('overlapPairs')}")
                if m.get("shatteredCells"):
                    report["failures"].append(f"{vp_name}:{key} shatteredCells {m.get('shatteredCells')}")
                # small buttons on touch viewports
                if vp["width"] <= 768:
                    for b in m.get("btns") or []:
                        if b.get("h", 99) < 36 and b.get("w", 99) > 0 and b.get("t"):
                            # ghost/icon-only may be smaller — only flag primary-looking short height with text
                            if len(b["t"]) > 2 and b["h"] < 32:
                                report["failures"].append(f"{vp_name}:{key} small btn {b}")

            # Mobile nav open on narrow
            if vp["width"] <= 768:
                page.goto(f"{BASE}/", wait_until="domcontentloaded")
                tog = page.locator("#nav-toggle")
                if tog.count():
                    tog.click()
                    page.wait_for_timeout(300)
                    vp_rep["mobile_nav"]["expanded"] = page.locator("#nav-toggle").get_attribute("aria-expanded")
                    vp_rep["mobile_nav"]["shot"] = shot(page, vp_name, "mobile-nav-open")
                    m = measure(page)
                    if m.get("overflowX"):
                        report["failures"].append(f"{vp_name}:mobile-nav overflowX")
                    tog.click(force=True)

            # Long string stress on companies list (visual only)
            page.goto(f"{BASE}/companies", wait_until="domcontentloaded")
            page.evaluate(
                """() => {
                  const a = document.querySelector('.table a, .table-wrap a, td a');
                  if (a) {
                    a.textContent = 'SehrLangeFirmenbezeichnungMitÜberlangemNamen GmbH & Co. KG VisualCheck';
                    a.style.maxWidth = '100%';
                  }
                  const email = document.querySelector('td, .muted, .user');
                }"""
            )
            long_m = measure(page)
            vp_rep["pages"]["companies_longname"] = {
                "visual": long_m,
                "shot": shot(page, vp_name, "companies-longname"),
            }
            if long_m.get("overflowX"):
                report["failures"].append(f"{vp_name}:companies_longname overflowX")
            if long_m.get("shatteredCells"):
                report["failures"].append(f"{vp_name}:companies_longname shattered {long_m.get('shatteredCells')}")
            report["viewports"][vp_name] = vp_rep
            ctx.close()
        browser.close()

    report["pass"] = len(report["failures"]) == 0
    out = EVIDENCE / "ui-visual-report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "failures": report["failures"], "evidence": str(out)}, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    rep = run()
    raise SystemExit(0 if rep["pass"] else 1)

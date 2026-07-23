"""Webschmiede Akquise Engine · Apify-ähnlich, branchenunabhängig."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
import csv

import requests

from discover import discover_overpass
from enrichment import crawl_website, empty_signals, score_from_signals
from intent import derive_intent
from places import fetch_nearby_places, load_api_key, merge_places_into_leads, enrich_leads_places
from meta_ads import enrich_leads_ads
from register import enrich_leads_register
from competition import rank_leads_locally
from diff import apply_diff_to_report
from directories import enrich_from_directories

AKQUISE_DIR = Path(__file__).resolve().parent
ROOT = AKQUISE_DIR.parent
VERTICALS_DIR = AKQUISE_DIR / "verticals"
REPORT_DIR = ROOT / "docs" / "akquise" / "reports"
WEB_REPORT = ROOT / "app" / "static" / "akquise-report.html"


def list_verticals() -> list[str]:
    return sorted(p.stem for p in VERTICALS_DIR.glob("*.json"))


def load_settings() -> dict:
    settings_path = AKQUISE_DIR / "settings.json"
    legacy = AKQUISE_DIR / "config.json"
    if settings_path.exists():
        return json.loads(settings_path.read_text(encoding="utf-8"))
    return json.loads(legacy.read_text(encoding="utf-8"))


def load_vertical(vertical_id: str) -> dict:
    path = VERTICALS_DIR / f"{vertical_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Vertical nicht gefunden: {vertical_id} (in akquise/verticals/)")
    return json.loads(path.read_text(encoding="utf-8"))


def merge_config(vertical_id: str) -> dict:
    settings = load_settings()
    vertical = load_vertical(vertical_id)
    cfg = {**settings, **vertical}
    cfg["vertical"] = vertical_id
    return cfg


def crawl_leads(leads: list[dict], cfg: dict, workers: int) -> int:
    to_crawl = [l for l in leads if l.get("website")]
    done = 0

    def job(lead: dict):
        sess = requests.Session()
        return lead, crawl_website(lead, cfg, sess)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(job, l): l for l in to_crawl}
        for fut in as_completed(futures):
            lead, sig = fut.result()
            lead["signals"] = sig
            if sig.get("email_found") and not lead.get("email"):
                lead["email"] = sig["email_found"][0]
            done += 1
    for lead in leads:
        if not lead.get("signals"):
            lead["signals"] = empty_signals(has_website=bool(lead.get("website")))
    return done


def enrich_google(leads: list[dict], cfg: dict, radius_km: float) -> int:
    if not cfg.get("google_places", {}).get("enabled"):
        return 0
    api_key = load_api_key()
    if not api_key:
        print("  Google Places: kein API-Key (deploy.secrets.local)")
        return 0
    gp_cfg = cfg.get("google_places", {})
    centers = cfg.get("centers") or ([cfg["center"]] if cfg.get("center") else [])
    merged = 0
    place_type = cfg.get("google_places_type", "restaurant")
    for center in centers:
        places = fetch_nearby_places(
            center["lat"],
            center["lon"],
            int(radius_km * 1000),
            api_key,
            place_type=place_type,
        )
        merged += merge_places_into_leads(leads, places)
    extra = 0
    if gp_cfg.get("find_place", True) or gp_cfg.get("details", True):
        extra = enrich_leads_places(
            leads,
            api_key,
            details=bool(gp_cfg.get("details", True)),
            workers=cfg.get("crawl", {}).get("max_workers", 4),
        )
    return merged + extra


def run_pipeline(
    vertical_id: str,
    *,
    radius_km: float | None = None,
    no_crawl: bool = False,
    workers: int | None = None,
) -> dict:
    cfg = merge_config(vertical_id)
    radius = radius_km or cfg.get("radius_km", 25)
    workers = workers or cfg.get("crawl", {}).get("max_workers", 8)

    leads = discover_overpass(cfg, radius)
    # Klassische Branchenbücher (Gelbe Seiten) – oft kleine Betriebe ohne OSM
    cities = []
    for c in cfg.get("centers") or [cfg.get("center") or {}]:
        name = (c.get("name") or "").strip()
        if name:
            cities.append(name)
    if not cities:
        cities = ["Mechernich", "Euskirchen"]
    dir_added = 0
    if cfg.get("directories", {}).get("enabled", True):
        try:
            dir_added = enrich_from_directories(leads, vertical_id, cities)
            print(f"  Branchenbuch: +{dir_added} Leads")
        except Exception as exc:
            print(f"  Branchenbuch Fehler: {exc}")
    places_merged = enrich_google(leads, cfg, radius)
    crawled = 0 if no_crawl else crawl_leads(leads, cfg, workers)
    ads_checked = enrich_leads_ads(leads, cfg, max_checks=cfg.get("meta_ads", {}).get("max_checks", 35))
    register_checked = enrich_leads_register(leads, cfg, max_checks=cfg.get("register", {}).get("max_checks", 20))

    for lead in leads:
        score, priority, angles = score_from_signals(lead, lead["signals"], cfg)
        lead["score"] = score
        lead["priority"] = priority
        lead["pitch_angles"] = angles
        lead["pitch_angle"] = angles[0] if angles else ""

    local_ranked = rank_leads_locally(leads)

    for lead in leads:
        lead["intent"] = derive_intent(lead, lead["signals"], cfg)

    # Sort: zuerst anrufbare Leads (A/B), dann Score
    prio_order = {"call": 0, "nurture": 1, "skip": 2, "email": 1}
    budget_order = {"A": 0, "B": 1, "C": 2, "D": 3}

    def sort_key(x: dict) -> tuple:
        intent = x.get("intent") or {}
        open_order = {"offen": 0, "neutral": 1, "tradition": 2, "resistent": 3}
        return (
            prio_order.get(intent.get("contact_priority", "nurture"), 9),
            budget_order.get(intent.get("budget_tier", "D"), 9),
            open_order.get(intent.get("openness_tier", "neutral"), 9),
            -x.get("score", 0),
        )

    leads.sort(key=sort_key)
    today = date.today().isoformat()
    report = {
        "date": today,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "vertical": vertical_id,
        "vertical_name": cfg.get("name", vertical_id),
        "center": (
            " + ".join(c.get("name", "") for c in (cfg.get("centers") or []))
            if len(cfg.get("centers") or []) > 1
            else cfg["center"]["name"]
        ),
        "centers": [c.get("name") for c in (cfg.get("centers") or [cfg.get("center") or {}])],
        "radius_km": radius,
        "total": len(leads),
        "crawled": crawled,
        "places_merged": places_merged,
        "directory_added": dir_added,
        "ads_checked": ads_checked,
        "register_checked": register_checked,
        "local_ranked": local_ranked,
        "high": sum(1 for l in leads if l["priority"] == "high"),
        "medium": sum(1 for l in leads if l["priority"] == "medium"),
        "call_ready": sum(1 for l in leads if (l.get("intent") or {}).get("contact_priority") == "call"),
        "budget_a": sum(1 for l in leads if (l.get("intent") or {}).get("budget_tier") == "A"),
        "buy_ready_count": sum(1 for l in leads if (l.get("intent") or {}).get("buy_ready")),
        "leads": leads,
    }
    return apply_diff_to_report(report)


def export_csv(report: dict, *, tiers: str = "AB") -> Path:
    """CSV für CRM, default nur Budget A+B mit contact_priority call."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    allowed = set(tiers.upper())
    vid = report["vertical"]
    csv_path = REPORT_DIR / f"{report['date']}-{vid}-call-list.csv"
    rows = []
    for lead in report["leads"]:
        intent = lead.get("intent") or {}
        bt = intent.get("budget_tier", "")
        if bt not in allowed:
            continue
        if intent.get("contact_priority") != "call":
            continue
        rows.append({
            "name": lead.get("name", ""),
            "phone": lead.get("phone", ""),
            "email": intent.get("contact_email", ""),
            "address": lead.get("address", ""),
            "amenity": lead.get("amenity", ""),
            "budget_tier": bt,
            "openness": intent.get("openness_label", ""),
            "revenue_est": intent.get("revenue_label", ""),
            "problems": intent.get("problems_summary", ""),
            "buy_signals": intent.get("buy_summary", ""),
            "addon": intent.get("addon_pitch", ""),
            "roi": intent.get("roi_label", ""),
            "call_script": (intent.get("call_script_text") or "")[:240],
            "stack": intent.get("stack_summary", ""),
            "offer": intent.get("offer_name", ""),
            "automations": " | ".join(intent.get("automations") or []),
            "local_rank": intent.get("local_rank_label", ""),
            "triggers": " | ".join(lead.get("triggers") or []),
            "meta_ads": "ja" if (lead.get("signals") or {}).get("runs_facebook_ads") else "",
            "successor_hint": intent.get("successor_hint", ""),
            "pitch": lead.get("pitch_angle", ""),
        })
    if rows:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    else:
        csv_path.write_text("name,phone,email\n", encoding="utf-8-sig")
    return csv_path


def save_report(report: dict) -> tuple[Path, Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    vid = report.get("vertical") or "gastro"
    report.setdefault("vertical", vid)
    report.setdefault("vertical_name", report.get("vertical_name") or ("Gastronomie" if vid == "gastro" else vid))
    json_path = REPORT_DIR / f"{report['date']}-{vid}.json"
    html_path = REPORT_DIR / f"{report['date']}-{vid}.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html = render_html(report)
    html_path.write_text(html, encoding="utf-8")
    try:
        WEB_REPORT.parent.mkdir(parents=True, exist_ok=True)
        WEB_REPORT.write_text(html, encoding="utf-8")
    except OSError:
        pass
    csv_path = export_csv(report)
    return json_path, html_path, csv_path


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def signal_summary(sig: dict) -> str:
    parts = []
    if sig.get("delivery_platforms"):
        parts.append("Lieferdienst")
    if sig.get("job_signals"):
        parts.append("Jobs")
    if sig.get("contact_person"):
        parts.append("Impressum")
    if sig.get("only_social_site"):
        parts.append("nur Social")
    if not sig.get("has_website"):
        parts.append("keine URL")
    return " · ".join(parts) or "–"


def budget_badge(intent: dict) -> str:
    tier = intent.get("budget_tier", "?")
    colors = {"A": "#2ecc71", "B": "#C9A84C", "C": "#888", "D": "#555"}
    bg = colors.get(tier, "#444")
    label = intent.get("budget_label", tier)
    pri = intent.get("contact_priority", "")
    if pri == "call":
        label = f"{tier} · Anrufen"
    elif pri == "skip":
        label = f"{tier} · Später"
    return f'<span class="badge" style="background:{bg}">{esc(label)}</span>'


def render_html(report: dict) -> str:
    rows = ""
    for i, lead in enumerate(report["leads"], 1):
        prio = lead["priority"]
        badge = {"high": "#C9A84C", "medium": "#888", "low": "#444"}[prio]
        sig = lead.get("signals") or {}
        intent = lead.get("intent") or {}
        gp = lead.get("google_places") or {}
        gmaps = f"{gp.get('rating','')}★ ({gp.get('user_ratings_total',0)})" if gp.get("rating") else "–"
        contact_lines = [x for x in [intent.get("contact_name") or intent.get("who"), intent.get("contact_email"), intent.get("contact_phone")] if x]
        contact_cell = "<br>".join(esc(x) for x in contact_lines) if contact_lines else "–"

        stack_cell = esc(intent.get("stack_summary") or "–")
        spend = intent.get("monthly_spend_est") or ""
        if spend:
            stack_cell += f'<br><span class="muted">{esc(spend)}</span>'

        problems = intent.get("problems") or []
        prob_html = "<br>".join(
            f"• {esc(p.get('label',''))} → <span class='muted'>{esc(p.get('solution','')[:70])}</span>"
            for p in problems[:3]
        ) or "–"
        auto = intent.get("automations") or []
        if auto:
            prob_html += "<br><span class='auto'>" + esc(" · ".join(auto[:2])) + "</span>"

        rev_cell = esc(intent.get("revenue_label") or "–")
        if intent.get("revenue_uplift"):
            rev_cell += f"<br><span class='muted'>{esc(intent.get('revenue_uplift',''))}</span>"

        open_cell = (
            f"<strong>{esc(intent.get('openness_label',''))}</strong>"
            f"<br><span class='muted'>{esc(intent.get('local_rank_label') or '')}</span>"
            f"<br><span class='muted'>{esc(intent.get('openness', {}).get('reason_summary', ''))}</span>"
        )
        if intent.get("successor_hint"):
            open_cell += f"<br><span class='offer'>{esc(intent.get('successor_hint',''))}</span>"
        triggers = lead.get("triggers") or intent.get("triggers") or []
        if triggers:
            open_cell += "<br><span class='trigger'>⚡ " + esc(triggers[0]) + "</span>"

        intent_cell = (
            f"<strong>{esc(intent.get('label',''))}</strong>"
            f"<br><span class='offer'>{esc(intent.get('offer_name',''))}, {esc(intent.get('offer_setup',''))}</span>"
            f"<br>{esc(intent.get('counter_pitch','')[:180])}"
        )
        if intent.get("buy_summary"):
            intent_cell += f"<br><span class='buy'>Kauf: {esc(intent.get('buy_summary',''))}</span>"
        if intent.get("addon_pitch"):
            intent_cell += f"<br><span class='addon'>Add-on: {esc(intent.get('addon_pitch','')[:140])}</span>"
        if intent.get("roi_label"):
            intent_cell += f"<br><span class='roi'>ROI: {esc(intent.get('roi_label',''))}</span>"

        rows += f"""
        <tr class="{prio} tier-{intent.get('budget_tier','')} open-{intent.get('openness_tier','')}{' buy-ready' if intent.get('buy_ready') else ''}">
          <td>{i}</td>
          <td><strong>{esc(lead['name'])}</strong><br><span class="muted">{esc(lead.get('address','')[:40])}</span></td>
          <td>{budget_badge(intent)}</td>
          <td class="rev">{rev_cell}</td>
          <td class="open">{open_cell}</td>
          <td class="prob">{prob_html}</td>
          <td class="stack">{stack_cell}</td>
          <td class="contact">{contact_cell}</td>
          <td class="intent">{intent_cell}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="de"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Akquise {esc(report['vertical_name'])}, {report['date']}</title>
<link href="https://fonts.bunny.net/css?family=inter:400;600;700&display=swap" rel="stylesheet">
<style>
body{{background:#0e0b08;color:#fff;font-family:Inter,sans-serif;margin:0;padding:20px;font-size:13px}}
h1{{color:#C9A84C;font-size:1.4rem}} .meta{{color:#888;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse}} th,td{{border-bottom:1px solid #2a2a2a;padding:8px 6px;text-align:left;vertical-align:top}}
th{{color:#888;position:sticky;top:0;background:#0e0b08;z-index:1}} tr.high{{background:rgba(201,168,76,.06)}}
tr.tier-A{{background:rgba(46,204,113,.04)}} tr.tier-D{{opacity:.65}}
.muted{{color:#666;font-size:11px}} .badge{{color:#000;padding:2px 7px;border-radius:99px;font-size:10px;font-weight:700;white-space:nowrap}}
.stack{{max-width:150px;font-size:11px;color:#aaa;line-height:1.4}}
.rev{{max-width:110px;font-size:11px;color:#ccc}}
.open{{max-width:140px;font-size:11px;line-height:1.4}}
.prob{{max-width:260px;font-size:11px;line-height:1.45;color:#bbb}}
.prob .auto{{color:#7a9;font-size:10px}}
.contact{{max-width:110px;font-size:11px;color:#ccc}}
.intent{{max-width:220px;font-size:11px;line-height:1.45}} .intent strong{{color:#C9A84C}}
.offer{{color:#9a8;font-size:10px}} .trigger{{color:#C9A84C;font-size:10px}}
.buy{{color:#2ecc71;font-size:10px;font-weight:600}} .addon{{color:#7ab;font-size:10px}}
.roi{{color:#C9A84C;font-size:10px}}
tr.open-resistent{{opacity:.55}} tr.buy-ready{{box-shadow:inset 3px 0 0 #2ecc71}}
.summary{{display:flex;gap:12px;margin:16px 0;flex-wrap:wrap}} .card{{background:#15120d;border:1px solid #2a2a2a;border-radius:10px;padding:12px 16px}}
.card b{{display:block;font-size:22px;color:#C9A84C}}
.legend{{font-size:11px;color:#666;margin-bottom:12px}}
</style></head><body>
<h1>Akquise Engine · {esc(report['vertical_name'])}</h1>
<p class="meta">{report['generated_at']} · {esc(report['center'])} · {report['radius_km']} km ·
{report['total']} Leads · {report.get('call_ready',0)} Anrufen · {report.get('buy_ready_count',0)} Kauf-Signal · {report.get('trigger_count', report.get('diff',{}).get('trigger_count',0))} Trigger</p>
<p class="legend"><strong>A/B + Anrufen</strong> · <strong>Kauf</strong> = Lieferando/Ads/Jobs-Lücke · <strong>Add-on</strong> = Tool bleibt, wir docken an</p>
<div class="summary">
  <div class="card"><b>{report.get('call_ready',0)}</b>Anrufbereit</div>
  <div class="card"><b>{report.get('buy_ready_count',0)}</b>Kauf-Signal</div>
  <div class="card"><b>{report.get('budget_a',0)}</b>Budget A</div>
  <div class="card"><b>{report['total']}</b>Gesamt</div>
</div>
<table><thead><tr>
<th>#</th><th>Betrieb</th><th>Budget</th><th>Umsatz (est.)</th><th>Offenheit</th><th>Probleme → Lösung</th><th>Stack</th><th>Kontakt</th><th>Angebot</th>
</tr></thead><tbody>{rows}</tbody></table>
<p style="color:#666;margin-top:20px;font-size:12px">Webschmiede Akquise Engine, Umsatz/Offenheit = Heuristiken aus öffentlichen Daten. CSV: reports/DATUM-VERTICAL-call-list.csv</p>
</body></html>"""

"""Kunden-Onboarding: Links + Go-Live-Checkliste aus kunden/*.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

import client_brand

KUNDEN_DIR = Path(os.getenv("KUNDEN_DIR", Path(__file__).resolve().parents[1] / "kunden"))


def _load_kunde(kid: str) -> dict | None:
    kid = kid.upper()
    if not KUNDEN_DIR.is_dir():
        return None
    for p in KUNDEN_DIR.glob("*.json"):
        if p.name.startswith(kid):
            return json.loads(p.read_text(encoding="utf-8"))
    return None


def _base_urls(k: dict) -> dict:
    u = k.get("urls") or {}
    base = (u.get("live_hauptseite") or u.get("test_hauptseite") or "").rstrip("/")
    bestellen = u.get("live_bestellen") or u.get("test_bestellen") or (f"{base}/bestellen" if base else "")
    admin = u.get("test_admin") or (f"{base}/admin" if base else "")
    handout = (
        f"{base}/uebergabe-handbuch?k={k.get('id', '')}&dl=1"
        if base
        else ""
    )
    tischaufsteller = (
        f"{base}/ci/tischaufsteller.html?k={k.get('id', '')}"
        if base
        else ""
    )
    onboarding = u.get("onboarding_url") or (f"{base}/onboarding?k={k.get('id', '')}" if base else "")
    demo = u.get("demo_url") or ""
    return {
        "base": base,
        "bestellen": bestellen,
        "admin": admin,
        "handout": handout,
        "tischaufsteller": tischaufsteller,
        "onboarding": onboarding,
        "demo": demo,
        "domain_live": u.get("domain") or "",
        "subdomain": u.get("subdomain") or "",
    }


def _env_flags() -> dict:
    return {
        "sms_enabled": os.getenv("SMS_ENABLED", "false").lower() in ("1", "true", "yes"),
        "sms_key": bool(os.getenv("SMS_API_KEY")),
        "owner_phone": bool(os.getenv("OWNER_PHONE")),
        "google_review": bool(os.getenv("GOOGLE_REVIEW_URL")),
        "google_review_url": (os.getenv("GOOGLE_REVIEW_URL") or "").strip(),
        "n8n_orders": bool(os.getenv("N8N_ORDER_WEBHOOK")),
        "public_base": os.getenv("PUBLIC_BASE_URL", "").rstrip("/"),
    }


def build_onboarding(kid: str) -> dict | None:
    k = _load_kunde(kid)
    if not k:
        return None

    urls = _base_urls(k)
    env = _env_flags()
    brand = client_brand.resolve_brand(k)
    is_gastro = client_brand.is_gastro(k.get("branche"))
    stripe = k.get("stripe") or {}
    billing = k.get("billing") or {}
    stripe_ok = stripe.get("status") in ("aktiv", "live", "connected") or bool(billing.get("paid_at"))
    domain_ok = bool(urls["domain_live"])

    links = [
        {"id": "home", "label": "Startseite", "desc": "Ihr Web-Auftritt für Gäste", "url": urls["base"], "icon": "fa-house"},
        {"id": "order", "label": "Bestellportal", "desc": "Hier bestellen Ihre Gäste", "url": urls["bestellen"], "icon": "fa-bag-shopping", "highlight": True},
        {"id": "admin", "label": "Admin-Dashboard", "desc": "Bestellungen, Speisekarte, Aktionen", "url": urls["admin"], "icon": "fa-gauge-high"},
        {
            "id": "handout",
            "label": "Übergabe-Handbuch (PDF)",
            "desc": "Zum Ausdrucken · Anleitung für den Schreibtisch",
            "url": urls["handout"],
            "icon": "fa-file-pdf",
            "download": True,
        },
    ]
    if is_gastro and urls.get("tischaufsteller"):
        links.append(
            {
                "id": "tischqr",
                "label": "Tischaufsteller mit QR",
                "desc": "A5 (148×210 mm) · Tisch beidseitig Bestellen · Theke Google · PDF + Maße",
                "url": urls["tischaufsteller"],
                "icon": "fa-qrcode",
                "download": True,
            }
        )
    links.extend(
        [
            {"id": "legal1", "label": "Datenschutz", "desc": "DSGVO-Seite", "url": f"{urls['base']}/datenschutz" if urls["base"] else "", "icon": "fa-shield"},
            {"id": "legal2", "label": "Impressum", "desc": "Pflichtangaben", "url": f"{urls['base']}/impressum" if urls["base"] else "", "icon": "fa-scale-balanced"},
        ]
    )
    links = [x for x in links if x.get("url")]

    customer_tasks = [
        {
            "id": "test_order",
            "label": "Testbestellung durchführen",
            "desc": "Einmal Abholung testen. Sie sehen die Order im Admin.",
            "done": False,
            "action_url": urls["bestellen"],
            "owner": "kunde",
        },
        {
            "id": "admin_tour",
            "label": "Admin einmal öffnen",
            "desc": "Tabs Bestellungen, Speisekarte, Aktionen ansehen.",
            "done": False,
            "action_url": urls["admin"],
            "owner": "kunde",
        },
        {
            "id": "domain",
            "label": "Eigene Domain wählen",
            "desc": "Unten Vorschläge prüfen oder Wunschdomain eintragen. Erst nach Ihrer Auswahl richten wir alles ein.",
            "done": domain_ok or bool((k.get("domain") or {}).get("selected")),
            "owner": "gemeinsam",
            "help": "Klick auf eine freie Domain speichert die Wahl. Kauf nur nach Freigabe bzw. bei .de manuell.",
        },
    ]
    if is_gastro:
        customer_tasks.append(
            {
                "id": "tischqr",
                "label": "Tischaufsteller drucken",
                "desc": "QR am Tisch (Bestellen) und an der Theke (Google). Format A5: 148×210 mm, beidseitiger Acryl-Aufsteller.",
                "done": False,
                "action_url": urls.get("tischaufsteller") or "",
                "owner": "gemeinsam",
                "help": "Farbig drucken, laminieren oder in Aufsteller-Hülle. 5 %-Aktion parallel im Admin anlegen.",
            }
        )
    customer_tasks.extend(
        [
        {
            "id": "stripe",
            "label": "Stripe · Online-Zahlung",
            "desc": "Gäste zahlen per Karte/Apple Pay (Geld auf Ihr Konto).",
            "done": stripe_ok,
            "owner": "gemeinsam",
            "help": "Stripe Express Konto, ca. 15 Min. Wir helfen beim Anlegen.",
            "link": "https://dashboard.stripe.com/register",
            "link_label": "Stripe öffnen",
        },
        {
            "id": "sms",
            "label": "SMS bei neuer Bestellung",
            "desc": "Handy klingelt bei jeder Order (seven.io).",
            "done": env["sms_enabled"] and env["sms_key"] and env["owner_phone"],
            "owner": "webschmiede",
            "help": "Ihre Handynummer + seven.io. Wir schalten das ein.",
        },
        {
            "id": "review",
            "label": "Google Unternehmensprofil anbinden",
            "desc": "Bewertungslink eintragen und WebSchmiede als Manager einladen. Kein Passwort an uns.",
            "done": bool((k.get("google") or {}).get("review_url"))
            or bool((k.get("google") or {}).get("manager_invited"))
            or bool((k.get("google") or {}).get("oauth_connected"))
            or env["google_review"],
            "owner": "gemeinsam",
            "help": "Im Onboarding unter „Google Unternehmensprofil“. Später Auto-Antworten auf Bewertungen.",
        },
        {
            "id": "photos",
            "label": "Eigene Speisefotos",
            "desc": "Professionellere Bilder im Portal.",
            "done": False,
            "owner": "kunde",
        },
        ]
    )

    webschmiede_done = [
        {"label": "Website & Bestellportal", "done": True},
        {"label": "Admin-Dashboard", "done": True},
        {"label": "CRM & Kundenhistorie", "done": True},
        {"label": "DSGVO (Datenschutz, Impressum)", "done": True},
        {"label": "Server DE (Hetzner)", "done": True},
        {"label": f"Test-URL ({urls['subdomain'] or 'Subdomain'})", "done": bool(urls["base"])},
        {"label": "SMS-Benachrichtigung", "done": env["sms_enabled"] and env["sms_key"]},
        {"label": "Eigene Domain live", "done": domain_ok},
        {"label": "Stripe Online-Zahlung", "done": stripe_ok},
    ]

    done = sum(1 for t in customer_tasks if t["done"]) + sum(1 for w in webschmiede_done if w["done"])
    total = len(customer_tasks) + len(webschmiede_done)

    branche = (k.get("branche") or "restaurant").lower()
    is_gastro_ui = client_brand.is_gastro(branche)

    order_label = "Bestellportal" if is_gastro_ui else "Kundenportal"
    menu_label = "Speisekarte" if is_gastro_ui else "Leistungen"

    handbook = {
        "title": f"Betriebs-Handbuch · {k.get('name', '')}",
        "subtitle": "Kurzanleitung für den Alltag am Schreibtisch",
        "intro": (
            f"Hallo {k.get('inhaber') or 'zusammen'}. "
            "Legen Sie dieses Heft neben den Rechner. "
            "Hier steht der komplette Ablauf: Bestellung, Nachrichten an den Gast, Follow-up, Google und was das für Ihren Umsatz bedeutet."
        ),
        "pdf_filename": f"Handbuch-{k.get('id', 'Kunde')}-{k.get('slug') or k.get('name', 'WebSchmiede')}.pdf",
        "guest_pages": [
            {
                "label": "Startseite",
                "benefit": "Auftritt für Gäste: Infos, Kontakt, Einstieg zum Bestellen. Auch als App speicherbar.",
                "url": urls["base"],
            },
            {
                "label": order_label,
                "benefit": (
                    "Gäste bestellen online: Abholung oder Lieferung, Wunschzeit, Zahlung"
                    if is_gastro_ui
                    else "Anfragen online, ohne Telefon-Chaos"
                ),
                "url": urls["bestellen"],
            },
            {
                "label": "Datenschutz & Impressum",
                "benefit": "Rechtstexte auf Ihrer Seite, ohne Tracking",
                "url": f"{urls['base']}/datenschutz" if urls["base"] else "",
            },
        ],
        "order_pipeline": (
            [
                {"label": "Gast bestellt"},
                {"label": "Sie sehen es"},
                {"label": "Küche / Status"},
                {"label": "Gast wird informiert"},
                {"label": "Fertig + Follow-up"},
            ]
            if is_gastro_ui
            else [
                {"label": "Anfrage kommt"},
                {"label": "Sie sehen es"},
                {"label": "Antwort / Termin"},
                {"label": "Kunde informiert"},
                {"label": "Nachfassen"},
            ]
        ),
        "daily_flow": (
            [
                {
                    "title": "Gast bestellt (Handy oder PC)",
                    "text": (
                        "Über Startseite oder Tisch-QR. Warenkorb, Abholung oder Lieferung, Wunschzeit, Zahlung "
                        "(Bar, Karte oder Online). Bestellung landet sofort bei Ihnen."
                    ),
                },
                {
                    "title": "Sie bekommen Bescheid",
                    "text": (
                        "Im Admin erscheint die Order oben, oft mit Ton. Parallel kann eine SMS auf Ihr Handy gehen "
                        "(wenn SMS aktiv ist): Nummer, Positionen, Betrag, Abholung oder Lieferung."
                    ),
                },
                {
                    "title": "Gast bekommt Bestätigung",
                    "text": (
                        "E-Mail und/oder SMS: Bestellung eingegangen, Bestellnummer, Art, Wunschzeit, Zahlung. "
                        "Der Gast weiß: Es ist angekommen, ohne anzurufen."
                    ),
                },
                {
                    "title": "Status setzen (Sie steuern)",
                    "text": (
                        "Im Admin: Neu → Zubereitung → Abholbereit oder Unterwegs → Fertig. "
                        "Jeder Statuswechsel kann dem Gast eine kurze Nachricht schicken."
                    ),
                },
                {
                    "title": "Optional: Bon drucken",
                    "text": "Button Drucken, wenn die Küche den Bon braucht.",
                },
                {
                    "title": "Feierabend",
                    "text": "Online/Offline-Schalter auf Offline, wenn Sie keine Bestellungen mehr wollen.",
                },
            ]
            if is_gastro_ui
            else [
                {
                    "title": "Anfrage kommt rein",
                    "text": "Im Admin erscheint der neue Auftrag. Sie sehen Name, Kontakt und Anliegen.",
                },
                {
                    "title": "Status setzen",
                    "text": "Schritten, in Arbeit, erledigt. So behalten Sie den Überblick.",
                },
                {
                    "title": "Feierabend",
                    "text": "Portal offline schalten, wenn Sie keine Anfragen mehr wollen.",
                },
            ]
        ),
        "guest_messages": (
            [
                {
                    "when": "Sofort nach Bestellung",
                    "channel": "E-Mail an den Gast",
                    "text": "Bestellung eingegangen, Bestellnummer, Artikel, Gesamtpreis, Abholung/Lieferung, Wunschzeit, Zahlung.",
                },
                {
                    "when": "Sofort nach Bestellung",
                    "channel": "SMS an den Gast (wenn aktiv)",
                    "text": "Kurze Bestätigung mit Bestellnummer. Willkommenstext bei Neukunden.",
                },
                {
                    "when": "Sofort nach Bestellung",
                    "channel": "SMS an Sie (Inhaber)",
                    "text": "Neue Bestellung mit Name, Telefon, Positionen und Betrag. Sie müssen nicht ständig am Bildschirm hängen.",
                },
                {
                    "when": "Status: Zubereitung",
                    "channel": "E-Mail / SMS an den Gast",
                    "text": "Dein Essen wird zubereitet. Noch kurz Geduld.",
                },
                {
                    "when": "Status: Abholbereit",
                    "channel": "E-Mail / SMS an den Gast",
                    "text": "Bestellung wartet. Adresse des Ladens.",
                },
                {
                    "when": "Status: Unterwegs",
                    "channel": "E-Mail / SMS an den Gast",
                    "text": "Essen ist auf dem Weg. Ungefähre Ankunft.",
                },
                {
                    "when": "Status: Fertig",
                    "channel": "E-Mail / SMS an den Gast",
                    "text": "Danke. Wir freuen uns auf den nächsten Besuch.",
                },
                {
                    "when": "Einige Tage später",
                    "channel": "SMS Follow-up (wenn Google-Link aktiv)",
                    "text": "Kurze Bitte um Bewertung mit Link zu Ihrem Google-Profil.",
                },
            ]
            if is_gastro_ui
            else []
        ),
        "followup": (
            [
                {
                    "title": "Kontakt landet in Ihrer Kartei",
                    "text": (
                        "Jede Bestellung speichert Telefon und Historie. "
                        "Sie bauen eigene Stammkunden auf, ohne Lieferando-Portal dazwischen."
                    ),
                },
                {
                    "title": "Google-Bewertung nach dem Essen",
                    "text": (
                        "Wenn der Google-Link hinterlegt ist, geht nach „Fertig“ automatisch (oder manuell) "
                        "eine höfliche SMS mit Bewertungslink raus. Zusätzlich: QR an der Theke."
                    ),
                },
                {
                    "title": "Später: Wieder kommen lassen",
                    "text": (
                        "Follow-up und Aktionen (z. B. 5 % erste Online-Bestellung, Mittagsdeal) "
                        "holen Gäste zurück. Das steuern Sie im Admin unter Aktionen."
                    ),
                },
                {
                    "title": "Tisch-QR im Laden",
                    "text": (
                        "Am Tisch: QR zum Bestellen. An der Theke: QR für Google. "
                        "Aufsteller und Maße liegen im Onboarding unter „Tischaufsteller mit QR“."
                    ),
                },
            ]
            if is_gastro_ui
            else [
                {
                    "title": "Kontakte bleiben bei Ihnen",
                    "text": "Anfragen und Kunden landen in Ihrer eigenen Kartei, nicht bei einem Portal.",
                }
            ]
        ),
        "google": (
            {
                "intro": (
                    "Google ist für lokale Gäste oft der erste Blick. "
                    "Gute Bewertungen und aktuelle Infos entscheiden mit, ob jemand anruft, vorbeikommt oder woanders isst."
                ),
                "points": [
                    {
                        "title": "Unternehmensprofil",
                        "text": (
                            "Öffnungszeiten, Fotos, Adresse, Speisekarte-Hinweis. "
                            "Wir helfen beim Saubermachen. Der Review-Link kommt ins System."
                        ),
                    },
                    {
                        "title": "Sterne und Texte",
                        "text": (
                            "Je mehr echte 4–5-Sterne-Bewertungen, desto vertrauenswürdiger wirken Sie. "
                            "Google zeigt lokale Betriebe bevorzugt, wenn Profil aktiv und Bewertungen frisch sind."
                        ),
                    },
                    {
                        "title": "Einfluss aufs Ranking (einfach erklärt)",
                        "text": (
                            "Google schaut u. a. auf: Vollständigkeit des Profils, Aktualität, Bewertungen, "
                            "wie oft Leute klicken und anrufen, und ob die Website und Bestellung klar erreichbar sind. "
                            "Ein eigenes Bestellportal auf Ihrer Domain wirkt professioneller als nur ein Lieferportal-Link."
                        ),
                    },
                    {
                        "title": "Zugang für WebSchmiede",
                        "text": (
                            "Kein Passwort an uns. Entweder Manager-Einladung an unsere Agency-Mail "
                            "oder später „Mit Google verbinden“ (OAuth). Dann können wir Bewertungen "
                            "beantworten und später Automation mit sinnvollen Keywords schalten."
                        ),
                    },
                    {
                        "title": "Was Sie konkret tun",
                        "text": (
                            "Theken-QR nutzen. Im Onboarding Bewertungslink eintragen und Manager einladen. "
                            "Auf Kritik kurz und sachlich antworten lassen (wir helfen)."
                        ),
                    },
                ],
            }
            if is_gastro_ui
            else {
                "intro": "Ein gepflegtes Google-Unternehmensprofil hilft lokalen Kunden, Sie zu finden.",
                "points": [
                    {
                        "title": "Bewertungen",
                        "text": "Nach guter Arbeit höflich um eine Bewertung bitten. Link können wir hinterlegen.",
                    }
                ],
            }
        ),
        "value": (
            {
                "intro": (
                    "Das hier ist kein Lieferando-Ersatz-Aufkleber. "
                    "Es ist Ihr eigenes System: Marke, Bestellung, Kundenkartei und Automation unter Ihrer Kontrolle."
                ),
                "points": [
                    {
                        "title": "Weniger Provision, mehr Marge",
                        "text": (
                            "Online-Bestellungen laufen über Sie. Keine 30 %-Portalgebühr auf jede Tüte. "
                            "Das merken Sie am Monatsende."
                        ),
                    },
                    {
                        "title": "Telefon wird ruhiger",
                        "text": (
                            "Stammgäste und Tischgäste bestellen digital. "
                            "Das Team tippt weniger mit und kocht mehr."
                        ),
                    },
                    {
                        "title": "Kunden gehören Ihnen",
                        "text": (
                            "Handy und Historie bleiben in Ihrer Kartei. "
                            "Sie können Aktionen schicken, ohne dass ein Portal dazwischen sitzt."
                        ),
                    },
                    {
                        "title": "Klarer Unterschied zum Nachbarn",
                        "text": (
                            "Eigene Website, eigene App-Startseite, QR am Tisch, Bestätigung per SMS/Mail, "
                            "Google-Bewertungen danach. Das wirkt wie ein moderner Betrieb, nicht wie „nur WhatsApp und Zettel“."
                        ),
                    },
                    {
                        "title": "Mehr Umsatz durch Wiederkehr",
                        "text": (
                            "Erste Bestellung mit kleinem Rabatt, später Erinnerung und Bewertung. "
                            "Wer einmal digital bestellt hat, kommt leichter wieder."
                        ),
                    },
                ],
            }
            if is_gastro_ui
            else {
                "intro": "Ihr System hält Anfragen und Kunden bei Ihnen, ohne fremdes Portal dazwischen.",
                "points": [
                    {
                        "title": "Weniger Chaos",
                        "text": "Anfragen landen strukturiert, nicht nur im Messenger-Strom.",
                    }
                ],
            }
        ),
        "admin_tabs": [
            {"label": "Bestellungen", "desc": "Neue Aufträge, Status, Ton, Druck"},
            {"label": "Kunden", "desc": "Automatische Kartei und Historie"},
            {"label": "Aktionen", "desc": "Zeitlich begrenzte Angebote für Gäste"},
            {"label": menu_label, "desc": "Preise, Texte, Verfügbarkeit, Bilder"},
            {"label": "Drucker", "desc": "Küchenbon per Browser oder Netzwerk"},
            {"label": "Tagesbericht", "desc": "Umsatz, Anzahl, Top-Gerichte"},
        ],
        "howto": [
            {
                "task": "Bestellungen pausieren",
                "how": "Schalter Online/Offline oben rechts im Admin.",
            },
            {
                "task": "Wartezeit anpassen",
                "how": "Minuten unter dem Header ändern und speichern.",
            },
            {
                "task": f"Artikel ausverkauft ({menu_label})",
                "how": f"Tab {menu_label}, Verfügbarkeit aus. Sofort live im Portal.",
            },
            {
                "task": "Preis oder Text ändern",
                "how": f"Tab {menu_label}, anpassen, Speichern.",
            },
            {
                "task": "Aktion starten",
                "how": "Tab Aktionen, einstellen, Starten. Countdown erscheint im Portal.",
            },
            {
                "task": "Tagesumsatz sehen",
                "how": "Button Tagesbericht im Header.",
            },
            {
                "task": "Tischaufsteller drucken",
                "how": "Onboarding → Tischaufsteller mit QR. A5, 148×210 mm, beidseitiger Acryl-Aufsteller.",
            },
        ] if is_gastro_ui else [
            {
                "task": "Anfragen pausieren",
                "how": "Schalter Online/Offline im Admin.",
            },
        ],
        "cheat_sheet": [
            {"q": "Wo bestellen Gäste?", "a": urls["bestellen"] or "–"},
            {"q": "Wo arbeite ich?", "a": urls["admin"] or "–"},
            {"q": "Passwort Admin?", "a": "Separat übergeben, nicht in diesem PDF"},
            {"q": "Tisch-QR / Google-QR?", "a": "Onboarding → Tischaufsteller mit QR"},
            {"q": "Support WebSchmiede?", "a": "+49 177 8011350 · info@digitalehandwerkskunst.de"},
        ],
        "access": [
            {"label": "Admin-Dashboard", "value": urls["admin"] or "–"},
            {"label": "Admin-Passwort", "value": "Separat übergeben (nicht in diesem Handbuch)"},
            {"label": order_label, "value": urls["bestellen"] or "–"},
            {
                "label": "Tischaufsteller",
                "value": urls.get("tischaufsteller") or "–",
            },
            {"label": "Support", "value": "+49 177 8011350 · info@digitalehandwerkskunst.de"},
        ],
        "tips": [
            "Lassen Sie den Admin auf einem Tablet oder zweiten Bildschirm offen.",
            "Testen Sie einmal selbst eine Bestellung, bevor Gäste kommen. Schauen Sie, welche Mails und SMS ankommen.",
            "Ausverkaufte Gerichte sofort im Admin abschalten, sonst bestellt jemand etwas, das weg ist.",
            "Tisch-QR nur Bestellen. Google-QR an die Theke. So bleibt der Ablauf klar.",
            "Bei Problemen: Screenshot an Christian schicken, wir schauen drauf.",
        ],
    }

    try:
        import domain_onboarding as domain_svc

        domain_block = domain_svc.domain_payload_for_onboarding(kid)
    except Exception as e:
        domain_block = {"ok": False, "error": str(e)[:120], "options": [], "selected": "", "status": "open"}

    try:
        import google_onboarding as google_svc

        google_business = google_svc.payload_for_onboarding(k, env.get("google_review_url") or "")
    except Exception as e:
        google_business = {"ok": False, "error": str(e)[:120], "status": "open"}

    return {
        "id": k.get("id"),
        "name": k.get("name"),
        "inhaber": k.get("inhaber"),
        "status": k.get("status"),
        "branche": k.get("branche"),
        "kontakt": k.get("kontakt"),
        "urls": urls,
        "links": links,
        "tasks": customer_tasks,
        "delivered": webschmiede_done,
        "handbook": handbook,
        "domain": domain_block,
        "brand": brand,
        "is_gastro": is_gastro,
        "google_review_url": env.get("google_review_url") or (k.get("google") or {}).get("review_url") or "",
        "google_business": google_business,
        "whatsapp": k.get("whatsapp") or {},
        "open_points": k.get("offene_punkte") or [],
        "progress": {"done": done, "total": total, "percent": round(100 * done / total) if total else 0},
        "support": {
            "agency": "Webschmiede · Digitale Handwerkskunst",
            "hint": "Admin-Passwort bekommen Sie separat, nicht über dieses Portal.",
        },
    }

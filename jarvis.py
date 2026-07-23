"""
JARVIS – Agentur-Verwaltung
============================
Befehle:
  python jarvis.py kunden               → alle Kunden anzeigen
  python jarvis.py kunde SHY001         → Kundendetails anzeigen
  python jarvis.py neu                  → neuen Kunden anlegen (+ n8n automatisch)
  python jarvis.py next-id handwerk     → nächste Kunden-ID vorschlagen
  python jarvis.py n8n SHY001           → n8n-Workflows für Kunde provisionieren
  python jarvis.py onboard SHY001       → Onboarding-E-Mail an Kunden senden
  python jarvis.py deploy SHY001        → Kunde auf Server deployen
  python jarvis.py subdomain SHY001 yassine [--ssl]  → Kunden-Subdomain (nginx + SSL)
  python jarvis.py checkout SHY001 pro               → Stripe-Zahlungslink
  python jarvis.py status               → Server-Status aller Kunden

  Aktions-Verwaltung:
  python jarvis.py promo                → aktive Aktion anzeigen
  python jarvis.py promo stop           → Aktion deaktivieren
  python jarvis.py promo pizza cola     → Pizza bestellen → Cola gratis (bis 21 Uhr)
  python jarvis.py promo burger pommes 18:00  → Burger → Pommes gratis bis 18:00

  Onboarding:
  python jarvis.py onboard SHY001 --dry-run
  python jarvis.py onboard SHY001 --upload-handout --support-email du@webschmiede.de

  Go-Live (Paket A+B):
  python scripts/go_live.py SHY001 check
  python scripts/go_live.py SHY001 run --support-email du@webschmiede.de --owner-phone +49... --sms-key KEY
"""
import json, os, sys, paramiko, datetime
from agency_config import load_secrets, ssh_connect
from kunden_ids import (
    prefix_for_branche,
    suggest_next_id_for_branche,
    suggest_next_id,
    n8n_order_webhook,
    validate_kunde_id,
    list_prefixes,
)
try:
    import requests as req
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

_secrets = load_secrets()
SERVER_IP  = _secrets["SERVER_HOST"]
SERVER_USER = _secrets["SERVER_USER"]
SERVER_PW  = _secrets["SERVER_PASSWORD"]
KUNDEN_DIR = os.path.join(os.path.dirname(__file__), 'kunden')

# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def ssh(cmd, timeout=30):
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=15, banner_timeout=15)
    _, out, err = c.exec_command(cmd, timeout=timeout)
    result = out.read().decode('utf-8', errors='replace')
    c.close()
    return result.strip()

def lade_kunden():
    kunden = []
    if not os.path.exists(KUNDEN_DIR):
        return kunden
    for f in sorted(os.listdir(KUNDEN_DIR)):
        if f.endswith('.json'):
            with open(os.path.join(KUNDEN_DIR, f), encoding='utf-8') as fp:
                kunden.append(json.load(fp))
    return kunden

def speichere_kunde(k):
    fname = f"{k['id']}_{k['slug']}.json"
    with open(os.path.join(KUNDEN_DIR, fname), 'w', encoding='utf-8') as f:
        json.dump(k, f, ensure_ascii=False, indent=2)

# ── Befehle ────────────────────────────────────────────────────────────────────

def cmd_kunden():
    kunden = lade_kunden()
    if not kunden:
        print("Noch keine Kunden angelegt.")
        return
    print(f"\n{'ID':<10} {'Name':<30} {'Status':<12} {'Domain'}")
    print('-' * 70)
    for k in kunden:
        domain = k['urls'].get('domain') or k['urls'].get('test_bestellen','')
        print(f"{k['id']:<10} {k['name']:<30} {k['status']:<12} {domain}")
    print(f"\nGesamt: {len(kunden)} Kunden\n")

def cmd_kunde(kid):
    kunden = lade_kunden()
    k = next((x for x in kunden if x['id'] == kid.upper()), None)
    if not k:
        print(f"Kunde '{kid}' nicht gefunden.")
        return
    print(f"\n{'='*50}")
    print(f"  {k['name']} ({k['id']})")
    print(f"{'='*50}")
    print(f"  Inhaber:   {k['inhaber']}")
    print(f"  Status:    {k['status']}")
    print(f"  Erstellt:  {k['erstellt']}")
    print(f"\n  TEST-LINKS:")
    print(f"    Hauptseite: {k['urls']['test_hauptseite']}")
    print(f"    Bestellen:  {k['urls']['test_bestellen']}")
    if k['urls'].get('test_admin'):
        print(f"    Admin:      {k['urls']['test_admin']}")
    if k['urls'].get('onboarding_url'):
        print(f"    Onboarding: {k['urls']['onboarding_url']}")
    if k['urls'].get('domain'):
        print(f"\n  LIVE-LINKS:")
        print(f"    Hauptseite: {k['urls']['live_hauptseite']}")
        print(f"    Bestellen:  {k['urls']['live_bestellen']}")
    print(f"\n  OFFENE PUNKTE:")
    for p in k.get('offene_punkte', []):
        print(f"    - {p}")
    print()

def cmd_neu():
    print("\n=== NEUEN KUNDEN ANLEGEN ===\n")
    print("Branchen-Prefixe:")
    for p in list_prefixes():
        print(f"  {p['prefix']} = {p['label']} ({p['beispiel']})")
    print()
    branche = input("Branche (restaurant/handwerk/beauty/...): ").strip().lower() or "restaurant"
    prefix = prefix_for_branche(branche)
    vorschlag = suggest_next_id_for_branche(KUNDEN_DIR, branche)
    kid = input(f"Kunden-ID [{vorschlag}]: ").strip().upper() or vorschlag
    if not validate_kunde_id(kid):
        print(f"Abbruch: '{kid}' ist ungueltig (Format z.B. {prefix}001)")
        return
    name = input("Firmenname: ").strip()
    inhaber = input("Inhaber (Vor- und Nachname): ").strip()
    slug = input("Slug (z.B. pizzeria-roma-koeln): ").strip().lower()
    telefon = input("Telefon: ").strip()
    email = input("E-Mail: ").strip()
    adresse = input("Adresse: ").strip()
    buchhaltung = input("Buchhaltungs-E-Mail (optional): ").strip()

    k = {
        "id": kid,
        "name": name,
        "inhaber": inhaber,
        "slug": slug,
        "branche": branche,
        "erstellt": datetime.date.today().isoformat(),
        "status": "lead",
        "kontakt": {"telefon": telefon, "email": email, "adresse": adresse},
        "urls": {
            "test_hauptseite": f"http://{SERVER_IP}/",
            "test_bestellen": f"http://{SERVER_IP}/bestellen",
            "domain": "", "live_hauptseite": "", "live_bestellen": ""
        },
        "server": {
            "ip": SERVER_IP,
            "ordner": f"/var/www/{slug}",
            "service": "snack-api",
            "port": "8000"
        },
        "crm": {"provider": "webschmiede", "sms_provider": "seven.io", "sms_enabled": False},
        "sms": {
            "enabled": False,
            "provider": "seven.io",
            "phone_number": "",
            "sender_id": "",
            "owner_phone": telefon,
            "notes": "",
        },
        "whatsapp": {
            "enabled": False,
            "phone_number_id": "",
            "business_phone": "",
            "allowed_phones": [],
            "permissions": ["menu_price", "menu_text", "menu_image", "menu_available"],
            "blocked": ["code", "domain", "admin_password", "delete_items"],
        },
        "voice": {
            "enabled": False,
            "provider": "",
            "agent_id": "",
            "phone_number": "",
            "knowledge_pack": "handwerk" if branche in ("handwerk", "dach", "dental", "friseur") else (
                "gastro" if branche in ("restaurant", "gastro") else "general"
            ),
            "billing": {"plan": "none", "included_minutes": 0, "overage_per_min_eur": 0},
        },
        "knowledge": {
            "pack": "handwerk" if branche in ("handwerk", "dach", "dental", "friseur") else (
                "gastro" if branche in ("restaurant", "gastro") else "general"
            ),
            "locale": "de-DE",
            "overrides": {},
            "voice": {"enabled": False, "provider": "", "voice_id": ""},
        },
        "n8n": {"order_webhook": n8n_order_webhook(kid)},
        "buchhaltung": {"bookkeeper_email": buchhaltung},
        "integrations": {
            "buchhaltung": "",
            "lexware": {
                "enabled": False,
                "sync_contacts": True,
                "sync_invoices": False,
                "api_key_env": f"LEXWARE_API_KEY_{kid}",
            },
        },
        "stripe": {"status": "ausstehend", "payment_link": ""},
        "offene_punkte": [
            "Angebot senden & Freigabe einholen",
            "Subdomain/DNS einrichten",
            f"n8n-Workflows für {kid} anlegen",
            "Domain registrieren",
            "Stripe-Account erstellen"
        ]
    }

    os.makedirs(KUNDEN_DIR, exist_ok=True)
    speichere_kunde(k)
    print(f"\nKunde '{name}' ({kid}) gespeichert!")
    print(f"Datei: kunden/{kid}_{slug}.json")
    print("\n n8n-Workflows werden angelegt …")
    cmd_n8n(kid)


def cmd_n8n(kid: str):
    import subprocess
    script = os.path.join(os.path.dirname(__file__), "scripts", "provision_kunde_n8n.py")
    r = subprocess.run([sys.executable, script, kid.upper()], check=False)
    if r.returncode != 0:
        print(f"\nHinweis: n8n-Provisionierung fehlgeschlagen (Code {r.returncode}).")
        print(f"Später: python jarvis.py n8n {kid.upper()}")
    else:
        print(f"\nn8n-Workflows für {kid.upper()} bereit.\n")


def cmd_next_id(branche: str):
    b = (branche or "restaurant").strip().lower()
    prefix = prefix_for_branche(b)
    nid = suggest_next_id_for_branche(KUNDEN_DIR, b)
    print(f"\nBranche: {b}")
    print(f"Prefix:  {prefix}")
    print(f"Naechste ID: {nid}\n")

def cmd_status():
    print(f"\nServer {SERVER_IP} – Status:\n")
    result = ssh(
        'for s in $(systemctl list-units --type=service --state=active --no-pager --no-legend | grep -api | awk \'{print $1}\'); do '
        'echo "$s: $(systemctl is-active $s)"; done; '
        'echo "---"; '
        'df -h / | tail -1; '
        'free -m | grep Mem'
    )
    print(result or "Keine aktiven API-Services")

# ── Aktions-Verwaltung ─────────────────────────────────────────────────────────

API_BASE      = f"http://{SERVER_IP}/api"
ADMIN_PW_FILE = os.path.join(os.path.dirname(__file__), 'app', 'backend', '.env')

def get_admin_pw():
    try:
        for line in open(ADMIN_PW_FILE):
            if line.startswith('ADMIN_PASSWORD='):
                return line.split('=',1)[1].strip()
    except Exception:
        pass
    return 'snackhouse2026'

TRIGGER_MAP = {
    'pizza':      {'val':'pizza',      'label':'Pizza'},
    'burger':     {'val':'burger',     'label':'Burger'},
    'schnitzel':  {'val':'schnitzel',  'label':'Schnitzel'},
    'drehspiess': {'val':'drehspiess', 'label':'Drehspieß'},
    'pasta':      {'val':'nudeln',     'label':'Pasta'},
    'nudeln':     {'val':'nudeln',     'label':'Nudeln'},
    'salat':      {'val':'salate',     'label':'Salat'},
    'fingerfood': {'val':'fingerfood', 'label':'Fingerfood'},
}

FREE_ITEM_MAP = {
    'cola':    {'id':'g1','name':'Cola 0,33 L',   'variant':'Cola 0,33 L'},
    'fanta':   {'id':'g1','name':'Fanta 0,33 L',  'variant':'Fanta 0,33 L'},
    'sprite':  {'id':'g1','name':'Sprite 0,33 L', 'variant':'Sprite 0,33 L'},
    'wasser':  {'id':'g2','name':'Wasser Still',  'variant':'Still'},
    'ayran':   {'id':'g3','name':'Ayran',         'variant':''},
    'pommes':  {'id':'f85','name':'Pommes klein', 'variant':'Pommes klein'},
}

def cmd_promo(args):
    if not REQUESTS_OK:
        print("pip install requests")
        return

    pw      = get_admin_pw()
    headers = {'X-Admin-Password': pw, 'Content-Type': 'application/json'}

    # Kein Argument → aktive Aktion anzeigen
    if not args:
        r = req.get(f"{API_BASE}/promo/active", timeout=8)
        data = r.json()
        if data.get('active'):
            p = data['promo']
            print(f"\n{'='*45}")
            print(f"  *** AKTIVE AKTION ***")
            print(f"  {p.get('title','')}")
            print(f"  {p.get('description','')}")
            print(f"  Trigger: {p.get('trigger_value','')} -> Gratis: {p.get('free_item_name','')}")
            print(f"  Gueltig bis: {p.get('valid_until','unbegrenzt')}")
            print(f"{'='*45}\n")
        else:
            print("\n  Keine Aktion aktiv.\n")
        return

    # stop → deaktivieren
    if args[0] == 'stop':
        r = req.delete(f"{API_BASE}/admin/promo", headers=headers, timeout=8)
        if r.ok:
            print("\n  OK - Aktion deaktiviert.\n")
        else:
            print(f"\n  Fehler: {r.text}\n")
        return

    # promo <trigger> <gratis-artikel> [bis-uhrzeit]
    trigger_key  = args[0].lower()
    free_key     = args[1].lower() if len(args) > 1 else 'cola'
    time_str     = args[2] if len(args) > 2 else '21:00'

    trigger = TRIGGER_MAP.get(trigger_key)
    free    = FREE_ITEM_MAP.get(free_key)

    if not trigger:
        print(f"\n  Unbekannter Trigger '{trigger_key}'. Möglich: {', '.join(TRIGGER_MAP.keys())}\n")
        return
    if not free:
        print(f"\n  Unbekannter Gratis-Artikel '{free_key}'. Möglich: {', '.join(FREE_ITEM_MAP.keys())}\n")
        return

    today = datetime.date.today().isoformat()
    valid_until = f"{today}T{time_str}"
    title = f"{trigger['label']} bestellen + {free['name']} gratis!"
    desc  = f"Heute bis {time_str} Uhr: {trigger['label']} bestellen und {free['name']} gratis dazu!"

    r = req.post(f"{API_BASE}/admin/promo", headers=headers, json={
        'title':           title,
        'description':     desc,
        'triggerType':     'category',
        'triggerValue':    trigger['val'],
        'freeItemName':    free['name'],
        'freeItemId':      free['id'],
        'freeItemVariant': free['variant'],
        'validUntil':      valid_until,
    }, timeout=8)

    if r.ok:
        print("\n  *** AKTION AKTIVIERT! ***")
        print(f"  {title}")
        print(f"  Gueltig bis: {time_str} Uhr heute")
        print(f"  -> Sofort live auf der Website!\n")
    else:
        print(f"\n  Fehler: {r.text}\n")


def cmd_onboard(kid, extra_args):
    import subprocess
    script = os.path.join(os.path.dirname(__file__), "scripts", "send_onboarding_email.py")
    cmd = [sys.executable, script, kid.upper()] + extra_args
    print(f"\n  Onboarding-E-Mail für {kid.upper()} …\n")
    subprocess.run(cmd, check=False)


def cmd_subdomain(kid, extra_args):
    """Kunden-Subdomain einrichten (nginx + optional SSL). DNS: Wildcard * oder A-Record."""
    import subprocess
    script = os.path.join(os.path.dirname(__file__), "scripts", "setup_client_subdomain.py")
    ssl = "--ssl" in extra_args
    subs = [a for a in extra_args if a != "--ssl"]
    if not subs:
        print("Usage: python jarvis.py subdomain SHY001 yassine [--ssl]")
        return
    cmd = [sys.executable, script, kid.upper(), subs[0]]
    if ssl:
        cmd.append("--ssl")
    subprocess.run(cmd, check=False)


def cmd_checkout(kid, extra_args):
    """Stripe Checkout-Link für Kunden (Setup + Abo)."""
    import subprocess
    pkg = extra_args[0] if extra_args else "pro"
    script = os.path.join(os.path.dirname(__file__), "scripts", "create_checkout.py")
    subprocess.run([sys.executable, script, kid.upper(), pkg], check=False)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args or args[0] == 'kunden':
        cmd_kunden()
    elif args[0] == 'kunde' and len(args) > 1:
        cmd_kunde(args[1])
    elif args[0] == 'neu':
        cmd_neu()
    elif args[0] == 'next-id':
        cmd_next_id(args[1] if len(args) > 1 else "restaurant")
    elif args[0] == 'n8n' and len(args) > 1:
        cmd_n8n(args[1])
    elif args[0] == 'onboard' and len(args) > 1:
        cmd_onboard(args[1], args[2:])
    elif args[0] == 'status':
        cmd_status()
    elif args[0] == 'promo':
        cmd_promo(args[1:])
    elif args[0] == 'subdomain' and len(args) > 2:
        cmd_subdomain(args[1], args[2:])
    elif args[0] == 'checkout' and len(args) > 1:
        cmd_checkout(args[1], args[2:])
    else:
        print(__doc__)

if __name__ == '__main__':
    main()

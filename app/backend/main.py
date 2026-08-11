from flask import Flask, request, jsonify, g, after_this_request, Response
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
import requests as req
import os, sqlite3, json, smtplib, datetime, secrets, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from functools import wraps
from collections import defaultdict
import time as _time

from order_validation import validate_order_prices
from loyalty import status_for_phone, validate_loyalty_items, apply_after_order
import seminars as seminar_svc
import agency_secrets as agency_secret_svc
import onboarding as onboarding_svc
import domain_onboarding as domain_onboarding_svc
import google_onboarding as google_onboarding_svc
import stripe_billing as stripe_billing_svc
import inbox_agent as inbox_svc
import agency_cockpit as agency_cockpit_svc
import agency_chat as agency_chat_svc
import agency_router as agency_router_svc
import agency_router_security as agency_router_sec
import dual_infra as dual_infra_svc
import agency_stefan as agency_stefan_svc
import agency_anwalt as agency_anwalt_svc
import agency_scout as agency_scout_svc
import agency_commander as agency_commander_svc
import agency_leads as agency_leads_svc
import meta_leads as meta_leads_svc
import agency_akquise as agency_akquise_svc
import jobs as jobs_svc
import integrations as integrations_svc
import shop_status as shop_status_svc
import order_portal as order_portal_svc
import agency_metrics as agency_metrics_svc
import agency_ops as agency_ops_svc
import messaging as messaging_svc
import push_notifications as push_svc
import whatsapp_embedded as wa_embedded_svc
import whatsapp_tenant as wa_tenant_svc
import whatsapp_webhook as wa_webhook_svc
import nils_ops as nils_ops_svc
import nils_whatsapp_ops as nils_wa_ops_svc
import telegram_ops as telegram_ops_svc
import agency_workorders as workorders_svc
import b2b_portal as b2b_portal_svc
import b2b_baustoff as b2b_baustoff_svc
import buchhaltung_onboarding as buchhaltung_onb_svc
import sales_pipeline as sales_pipeline_svc
import sales_companion as sales_companion_svc
import agency_brain as agency_brain_svc
import agency_radar as agency_radar_svc
import agency_shipcheck as agency_shipcheck_svc
import ops_guardian as ops_guardian_svc
import jay_voice as jay_voice_svc
import auth_users as auth_svc
import customer_auth as ca_svc
import student_offers as so_svc
import analytics_events as ae_svc
import operational_alerts as oa_svc
import order_priority as prio_svc
import hmac as _hmac

load_dotenv()

PORTAL_MODE = (os.getenv("PORTAL_MODE", "gastro") or "gastro").strip().lower()

app = Flask(__name__)
# Nginx + Cloudflare: 1 Proxy-Hop vertrauen, damit request.remote_addr die echte Client-IP enthält
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# ── CORS: nur eigene Domain erlaubt ──────────────────────────────────────────
def _cors_origins():
    origins = [
        "https://digitalehandwerkskunst.de",
        "https://www.digitalehandwerkskunst.de",
        "https://yassine.digitalehandwerkskunst.de",
        "https://muster.digitalehandwerkskunst.de",
        "http://167.233.150.230",
        "https://167.233.150.230",
        "https://snackhouse-mechernich.de",
        "https://www.snackhouse-mechernich.de",
    ]
    for part in os.getenv("CORS_ORIGINS", "").split(","):
        o = part.strip()
        if o and o not in origins:
            origins.append(o)
    base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if base and base not in origins:
        origins.append(base)
    return origins


CORS(app, origins=_cors_origins(), supports_credentials=False)

# ── Phase A Blueprint ─────────────────────────────────────────────────────────
import phase_a_blueprint as _phase_a_mod
from phase_a_blueprint import phase_a_bp as _phase_a_bp

# Direkter Verweis auf dieses Modul, damit der Blueprint unter gunicorn (wo main
# kein __main__ ist) trotzdem get_db, _settings_map usw. findet.
import sys as _sys
_phase_a_mod._main = _sys.modules[__name__]

app.register_blueprint(_phase_a_bp)

# Design System showcase / AppShell prototype — gated to local|staging|test (404 in production)
try:
    from design_system import design_system_bp as _design_system_bp
    app.register_blueprint(_design_system_bp)
except ImportError:
    pass

GHL_TOKEN       = os.getenv("GHL_TOKEN", "")
GHL_LOC_ID      = os.getenv("GHL_LOC_ID", "")
GHL_PIPELINE_ID = os.getenv("GHL_PIPELINE_ID", "")
GHL_STAGE_NEW   = os.getenv("GHL_STAGE_NEW", "")
GHL_BASE        = "https://services.leadconnectorhq.com"
GHL_HEADERS     = {
    "Authorization": f"Bearer {GHL_TOKEN}",
    "Version": "2021-07-28",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD", "").strip()
AGENCY_ADMIN_PASSWORD = os.getenv("AGENCY_ADMIN_PASSWORD", ADMIN_PASSWORD)
# Legacy: Passwort im Header für n8n/Scripts. UI nutzt Session-Token.
AGENCY_ALLOW_PASSWORD_HEADER = os.getenv("AGENCY_ALLOW_PASSWORD_HEADER", "1").strip().lower() in (
    "1", "true", "yes",
)
# Legacy: Passwort im Header nur wenn explizit erlaubt (unsicher)
ADMIN_ALLOW_PASSWORD_HEADER = os.getenv("ADMIN_ALLOW_PASSWORD_HEADER", "0").lower() in (
    "1",
    "true",
    "yes",
)
AGENCY_OWNER_EMAIL = os.getenv("AGENCY_OWNER_EMAIL", "")
N8N_SEMINAR_WEBHOOK = os.getenv("N8N_SEMINAR_WEBHOOK", "")
SMTP_HOST       = os.getenv("SMTP_HOST", "")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER       = os.getenv("SMTP_USER", "")
SMTP_PASS       = os.getenv("SMTP_PASS", "")
SMTP_FROM       = os.getenv("SMTP_FROM", "bestellung@snackhouse-mechernich.de")
DB_PATH         = os.path.join(os.path.dirname(__file__), "orders.db")

# ── CRM / SMS (GHL-Ersatz) ───────────────────────────────────────────────────
GHL_ENABLED     = os.getenv("GHL_ENABLED", "false").lower() in ("1", "true", "yes")
SMS_ENABLED     = os.getenv("SMS_ENABLED", "false").lower() in ("1", "true", "yes")
SMS_API_KEY     = os.getenv("SMS_API_KEY", "")
SMS_SENDER      = os.getenv("SMS_SENDER", "SnackHouse")
OWNER_PHONE     = os.getenv("OWNER_PHONE", "")
SHOP_NAME       = os.getenv("SHOP_NAME", "Snack House Yassine")
SHOP_PHONE      = os.getenv("SHOP_PHONE", "024433088966")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://yassine.digitalehandwerkskunst.de").rstrip("/")
ORDER_PORTAL_URL = os.getenv("ORDER_PORTAL_URL", f"{PUBLIC_BASE_URL}/bestellen").rstrip("/")
CALCOM_URL = os.getenv("CALCOM_URL", f"{PUBLIC_BASE_URL}/cal").rstrip("/")
CALCOM_API_KEY = os.getenv("CALCOM_API_KEY", "")
CRON_SECRET     = os.getenv("CRON_SECRET", "")
GOOGLE_REVIEW_URL = os.getenv("GOOGLE_REVIEW_URL", "")
N8N_ORDER_WEBHOOK = os.getenv("N8N_ORDER_WEBHOOK", "")
KUNDE_ID          = (os.getenv("KUNDE_ID", "") or "").strip().upper()
WHATSAPP_VERIFY_TOKEN = (os.getenv("WHATSAPP_VERIFY_TOKEN") or "").strip()
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
KUNDEN_DIR      = os.getenv("KUNDEN_DIR", os.path.join(os.path.dirname(__file__), "..", "kunden"))
JARVIS_UPLOAD_DIR = os.getenv("JARVIS_UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "..", "uploads", "menu"))
os.environ.setdefault("KUNDEN_DIR", KUNDEN_DIR)
os.environ.setdefault("JARVIS_UPLOAD_DIR", JARVIS_UPLOAD_DIR)

# ── Session-Tokens (SQLite via auth_users – Worker-/Restart-sicher) ───────────
SESSION_TTL = int(os.getenv("AUTH_SESSION_TTL", str(12 * 3600)))


def create_session(kind: str = "admin", user_id: int | None = None) -> str:
    return auth_svc.create_session(get_db(), kind=kind, user_id=user_id, ttl=SESSION_TTL)


def is_valid_session(token: str, *, kinds: tuple[str, ...] | None = None) -> bool:
    sess = auth_svc.get_session(get_db(), token)
    if not sess:
        return False
    if kinds and sess.get("kind") not in kinds:
        return False
    g.auth_session = sess
    g.auth_user_id = sess.get("user_id")
    return True


def _set_auth_cookie(resp, name: str, token: str):
    resp.set_cookie(
        name,
        token,
        max_age=SESSION_TTL,
        httponly=True,
        secure=True,
        samesite="Strict",
        path="/",
    )
    return resp


# ── Rate Limiting (einfach, in-memory) ────────────────────────────────────────
_rate: dict[str, list] = defaultdict(list)

def rate_limit(key: str, max_calls: int, window_s: int) -> bool:
    """Gibt True zurück wenn das Limit überschritten ist."""
    now = _time.time()
    calls = [t for t in _rate[key] if now - t < window_s]
    _rate[key] = calls
    if len(calls) >= max_calls:
        return True
    _rate[key].append(now)
    return False


def get_real_ip() -> str:
    """Echte Client-IP: CF-Connecting-IP > X-Real-IP > remote_addr."""
    return (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Real-IP")
        or request.remote_addr
        or "unknown"
    )

# ── Security-Response-Header ──────────────────────────────────────────────────
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"]  = "nosniff"
    response.headers["X-Frame-Options"]          = "DENY"
    response.headers["Referrer-Policy"]           = "no-referrer"
    response.headers["Permissions-Policy"]        = "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    response.headers["Cache-Control"]             = "no-store"
    response.headers.pop("Server", None)
    return response

# ── Input-Validierung ─────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}$")
_PHONE_RE = re.compile(r"^[\d\s\+\-\(\)]{5,20}$")

def validate_order(data: dict) -> str | None:
    """Gibt Fehlermeldung zurück oder None wenn alles ok."""
    if not data.get("firstName","").strip():
        return "Vorname fehlt"
    if len(data.get("firstName","")) > 50:
        return "Vorname zu lang"
    if len(data.get("lastName","")) > 50:
        return "Nachname zu lang"
    phone = data.get("phone","").strip()
    if not phone:
        return "Telefonnummer fehlt"
    if not _PHONE_RE.match(phone):
        return "Ungültige Telefonnummer"
    email = data.get("email","").strip()
    if email and not _EMAIL_RE.match(email):
        return "Ungültige E-Mail-Adresse"
    if data.get("deliveryType") not in ("lieferung","abholung"):
        return "Ungültige Bestellart"
    if data.get("payMethod") not in ("cash","card","stripe"):
        return "Ungültige Zahlungsart"
    items = data.get("items",[])
    if not items or len(items) > 50:
        return "Warenkorb ungültig"
    total = data.get("total", 0)
    if not isinstance(total, (int, float)) or total < 0 or total > 5000:
        return "Ungültiger Gesamtbetrag"
    address = data.get("address","")
    if len(address) > 200:
        return "Adresse zu lang"
    notes = data.get("notes","")
    if len(notes) > 500:
        return "Notizen zu lang"
    return None

def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    p = re.sub(r"[\s\-\(\)]", "", phone.strip())
    if p.startswith("00"):
        p = "+" + p[2:]
    elif p.startswith("0"):
        p = "+49" + p[1:]
    elif p.startswith("49") and not p.startswith("+"):
        p = "+" + p
    elif not p.startswith("+"):
        p = "+49" + p
    return p

# ── Datenbank ─────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE,
                created_at   TEXT DEFAULT (datetime('now')),
                first_name   TEXT,
                last_name    TEXT,
                phone        TEXT,
                email        TEXT,
                address      TEXT,
                delivery_type TEXT,
                pay_method   TEXT,
                items        TEXT,
                total        REAL,
                wunschzeit   TEXT,
                notes        TEXT,
                status       TEXT DEFAULT 'neu',
                promo_applied TEXT
            )
        """)
        # Promo-Spalte nachrüsten falls DB alt ist
        try:
            db.execute("ALTER TABLE orders ADD COLUMN promo_applied TEXT")
        except Exception:
            pass
        # Settings-Tabelle (online/offline, Wartezeit, etc.)
        db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Standardwerte falls noch nicht vorhanden
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('online','1')")
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('wait_pickup','20')")
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('wait_delivery','40')")
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('offline_msg','Wir sind gleich zurück!')")

        # Artikel-Verfügbarkeit (item_id → 0=aus, 1=an)
        db.execute("""
            CREATE TABLE IF NOT EXISTS menu_overrides (
                item_id    TEXT PRIMARY KEY,
                available  INTEGER DEFAULT 1,
                note       TEXT,
                price      REAL,
                name       TEXT,
                desc       TEXT,
                image_url  TEXT
            )
        """)
        for col, typ in (("price", "REAL"), ("name", "TEXT"), ("desc", "TEXT"), ("image_url", "TEXT")):
            try:
                db.execute(f"ALTER TABLE menu_overrides ADD COLUMN {col} {typ}")
            except Exception:
                pass

        db.execute("""
            CREATE TABLE IF NOT EXISTS bot_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                client_id  TEXT,
                phone      TEXT,
                channel    TEXT,
                direction  TEXT,
                body       TEXT,
                result     TEXT,
                meta       TEXT
            )
        """)

        push_svc.init_push_table(db)

        db.execute("""
            CREATE TABLE IF NOT EXISTS agency_chat (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                kunde_id   TEXT,
                role       TEXT,
                body       TEXT,
                meta       TEXT
            )
        """)

        nils_ops_svc.ensure_tables(db)
        b2b_portal_svc.ensure_tables(db)
        buchhaltung_onb_svc.ensure_tables(db)
        sales_pipeline_svc.ensure_tables(db)
        b2b_baustoff_svc.ensure_order_tables(db)
        agency_router_sec.ensure_tables(db)

        db.execute("""
            CREATE TABLE IF NOT EXISTS promos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT DEFAULT (datetime('now')),
                title       TEXT,
                description TEXT,
                trigger_type  TEXT,
                trigger_value TEXT,
                free_item_name TEXT,
                free_item_id   TEXT,
                free_item_variant TEXT,
                valid_until TEXT,
                active      INTEGER DEFAULT 1
            )
        """)

        # ── CRM: Kontakte (GHL-Ersatz) ─────────────────────────────────────
        db.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                phone         TEXT UNIQUE NOT NULL,
                email         TEXT,
                first_name    TEXT,
                last_name     TEXT,
                total_orders  INTEGER DEFAULT 0,
                total_spent   REAL DEFAULT 0,
                last_order_at TEXT,
                tags          TEXT DEFAULT '[]',
                notes         TEXT,
                created_at    TEXT DEFAULT (datetime('now')),
                review_requested INTEGER DEFAULT 0,
                loyalty_stamps   INTEGER DEFAULT 0
            )
        """)
        try:
            db.execute("ALTER TABLE contacts ADD COLUMN review_requested INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            db.execute("ALTER TABLE contacts ADD COLUMN loyalty_stamps INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            db.execute("ALTER TABLE orders ADD COLUMN completed_at TEXT")
        except Exception:
            pass
        try:
            db.execute("ALTER TABLE orders ADD COLUMN review_sent INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            db.execute("ALTER TABLE orders ADD COLUMN loyalty_reward INTEGER DEFAULT 0")
        except Exception:
            pass
        db.execute("""
            CREATE TABLE IF NOT EXISTS integration_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                provider   TEXT NOT NULL,
                action     TEXT NOT NULL,
                ref        TEXT,
                status     TEXT NOT NULL,
                detail     TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('winback_days','30')")
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('review_days','3')")
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('google_review_url','')")
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('loyalty_enabled','1')")
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('loyalty_stamps_needed','10')")
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('loyalty_reward_item_id','g3')")
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('loyalty_reward_name','Ayran 0,4 L')")
        db.execute("""
            CREATE TABLE IF NOT EXISTS message_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at    TEXT DEFAULT (datetime('now')),
                contact_phone TEXT,
                channel       TEXT,
                template      TEXT,
                body          TEXT,
                status        TEXT,
                order_number  TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS inbox_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at   TEXT DEFAULT (datetime('now')),
                updated_at    TEXT,
                message_id    TEXT UNIQUE,
                from_email    TEXT,
                from_name     TEXT,
                subject       TEXT,
                body_preview  TEXT,
                status        TEXT NOT NULL,
                category      TEXT,
                faq_id        TEXT,
                confidence    REAL,
                action_taken  TEXT,
                reply_sent    INTEGER DEFAULT 0,
                reply_subject TEXT,
                notes         TEXT
            )
        """)
        try:
            db.execute("CREATE INDEX IF NOT EXISTS idx_inbox_received ON inbox_log(received_at)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_inbox_status ON inbox_log(status)")
        except Exception:
            pass
        try:
            db.execute("ALTER TABLE orders ADD COLUMN contact_id INTEGER")
        except Exception:
            pass

        # Bestehende Bestellungen → Kontakte migrieren (einmalig)
        db.execute("""
            INSERT OR IGNORE INTO contacts (phone, email, first_name, last_name, total_orders, total_spent, last_order_at)
            SELECT phone, MAX(email), MAX(first_name), MAX(last_name), COUNT(*), SUM(total), MAX(created_at)
            FROM orders WHERE phone IS NOT NULL AND phone != ''
            GROUP BY phone
        """)

        seminar_svc.init_schema(db)
        agency_metrics_svc.ensure_schema(db)
        auth_svc.ensure_schema(db)
        ca_svc.ensure_schema(db)
        so_svc.init_schema(db)
        ae_svc.init_schema(db)
        oa_svc.init_schema(db)
        # Orders-Tabelle um Verzögerungs-Felder erweitern
        for col, typ in [
            ("delay_minutes", "INTEGER"),
            ("expected_ready_at", "TEXT"),
            ("delay_reason", "TEXT"),
            ("production_started_at", "TEXT"),
            # Unveränderlicher Original-Wunschtermin (niemals aktualisieren nach Erstellung)
            ("original_requested_ready_at", "TEXT"),
        ]:
            try:
                db.execute(f"ALTER TABLE orders ADD COLUMN {col} {typ}")
            except Exception:
                pass
        db.commit()
        try:
            expected_agency = agency_secret_svc.resolve_agency_admin_password(AGENCY_ADMIN_PASSWORD)
            auth_svc.seed_bootstrap_users(
                db,
                agency_password=expected_agency or "",
                admin_password=ADMIN_PASSWORD or "",
                agency_email=os.getenv("AGENCY_OWNER_EMAIL", ""),
            )
        except Exception:
            pass
        db.commit()

init_db()

def _pw_match(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    a, b = provided.encode("utf-8"), expected.encode("utf-8")
    if len(a) != len(b):
        return False
    return _hmac.compare_digest(a, b)


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = (
            request.headers.get("X-Admin-Token", "")
            or request.cookies.get("admin_session", "")
        )
        if is_valid_session(token, kinds=("admin", "kunde_admin")):
            return f(*args, **kwargs)
        if ADMIN_ALLOW_PASSWORD_HEADER:
            pw = request.headers.get("X-Admin-Password", "")
            if _pw_match(pw, ADMIN_PASSWORD or ""):
                return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized"}), 401
    return decorated

def require_agency_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = (
            request.headers.get("X-Agency-Token", "")
            or request.cookies.get("agency_session", "")
        )
        if is_valid_session(token, kinds=("agency",)):
            return f(*args, **kwargs)
        if AGENCY_ALLOW_PASSWORD_HEADER:
            pw = request.headers.get("X-Agency-Password", "") or request.headers.get("X-Admin-Password", "")
            expected = agency_secret_svc.resolve_agency_admin_password(AGENCY_ADMIN_PASSWORD)
            if _pw_match(pw, expected or ""):
                return f(*args, **kwargs)
        return jsonify({
            "error": "Unauthorized",
            "hint": "Bitte neu anmelden (Session). Legacy: X-Agency-Password nur noch für Scripts.",
        }), 401
    return decorated


# Werkzeuge API (platform_registry.yaml) — auth-gated, no business-logic change
try:
    from platform_tools import platform_tools_bp as _platform_tools_bp

    app.register_blueprint(_platform_tools_bp)
    app.view_functions["platform_tools.agency_tools_list"] = require_agency_admin(
        app.view_functions["platform_tools.agency_tools_list"]
    )
except ImportError:
    pass

# ── E-Mail ────────────────────────────────────────────────────────────────────

def send_confirmation_email(order):
    if not SMTP_HOST or not SMTP_USER:
        return
    try:
        items_html = "".join(
            f"<tr><td style='padding:4px 0'>{i['qty']}x {i['name']}</td>"
            f"<td style='text-align:right;padding:4px 0'>{i['price']*i['qty']:.2f} €</td></tr>"
            for i in order["items"]
        )
        pay_label = {"cash":"Barzahlung","card":"EC-/Kreditkarte","stripe":"Online (Stripe)"}.get(order["pay_method"], order["pay_method"])
        del_label = "Lieferung" if order["delivery_type"] == "lieferung" else "Abholung"

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;background:#0e0b08;color:#fff;padding:32px;border-radius:12px;">
          <div style="text-align:center;margin-bottom:24px;">
            <h1 style="color:#C9A84C;font-size:22px;margin:0">Snack House Yassine</h1>
            <p style="color:#888;margin:4px 0 0">Dr.-Felix-Gerhardus-Str. 7 · 53894 Mechernich</p>
          </div>
          <div style="background:#1a1a1a;border-radius:8px;padding:20px;margin-bottom:20px;">
            <h2 style="color:#22c55e;margin:0 0 4px;font-size:16px">✓ Bestellung eingegangen!</h2>
            <p style="color:#888;margin:0;font-size:13px">Bestellnummer: <strong style="color:#C9A84C">{order["order_number"]}</strong></p>
          </div>
          <table style="width:100%;border-collapse:collapse;margin-bottom:16px">
            {items_html}
            <tr style="border-top:1px solid #333">
              <td style="padding:8px 0;font-weight:bold">Gesamt</td>
              <td style="text-align:right;font-weight:bold;color:#C9A84C">{order["total"]:.2f} €</td>
            </tr>
          </table>
          <div style="background:#1a1a1a;border-radius:8px;padding:16px;font-size:13px;color:#aaa">
            <p style="margin:0 0 4px"><strong style="color:#fff">Art:</strong> {del_label}</p>
            <p style="margin:0 0 4px"><strong style="color:#fff">Wunschzeit:</strong> {order["wunschzeit"] or "So schnell wie möglich"}</p>
            <p style="margin:0"><strong style="color:#fff">Zahlung:</strong> {pay_label}</p>
          </div>
          {f'<div style="background:rgba(201,168,76,0.1);border:1px solid rgba(201,168,76,0.3);border-radius:8px;padding:12px 16px;margin-top:12px;font-size:13px;color:#C9A84C;">🎉 Aktion angewendet: {order["promo_applied"]}</div>' if order.get("promo_applied") else ''}
          <p style="color:#555;font-size:11px;text-align:center;margin-top:24px">
            Fragen? Tel: 02443-3088966 · Mittwoch Ruhetag
          </p>
        </div>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✓ Bestellung {order['order_number']} – Snack House Yassine"
        msg["From"]    = SMTP_FROM
        msg["To"]      = order["email"]
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_FROM, order["email"], msg.as_string())
    except Exception as e:
        app.logger.warning(f"E-Mail Fehler: {e}")

def send_status_email(order, new_status):
    if not SMTP_HOST or not SMTP_USER or not order["email"]:
        return
    messages = {
        "zubereitung": ("Dein Essen wird zubereitet!", "#f59e0b",
                        "Deine Bestellung wird gerade frisch für dich zubereitet. Noch kurz Geduld!"),
        "unterwegs":   ("Dein Essen ist unterwegs!", "#3b82f6",
                        "Deine Bestellung ist auf dem Weg zu dir. Unser Fahrer ist in ca. 15–25 Minuten bei dir."),
        "abholbereit": ("Deine Bestellung ist abholbereit!", "#3b82f6",
                        "Deine Bestellung wartet auf dich! Snack House Yassine · Dr.-Felix-Gerhardus-Str. 7 · Mechernich"),
        "fertig":      ("Danke für deine Bestellung!", "#22c55e",
                        "Wir hoffen, es hat dir geschmeckt! Wir freuen uns auf deinen nächsten Besuch."),
    }
    if new_status not in messages:
        return
    subject_text, color, body_text = messages[new_status]
    try:
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;background:#0e0b08;color:#fff;padding:32px;border-radius:12px;">
          <h1 style="color:#C9A84C;font-size:20px;margin:0 0 20px">Snack House Yassine</h1>
          <div style="background:#1a1a1a;border-radius:8px;padding:20px;">
            <h2 style="color:{color};margin:0 0 8px;font-size:16px">{subject_text}</h2>
            <p style="color:#aaa;margin:0">{body_text}</p>
            <p style="color:#666;font-size:12px;margin:12px 0 0">Bestellung: {order["order_number"]}</p>
          </div>
        </div>
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Snack House Yassine – {subject_text}"
        msg["From"]    = SMTP_FROM
        msg["To"]      = order["email"]
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_FROM, order["email"], msg.as_string())
    except Exception as e:
        app.logger.warning(f"Status-E-Mail Fehler: {e}")


def _smtp_send(to: str, subject: str, html: str):
    """Hilfs-Funktion: Email via SMTP versenden. Wirft Exception bei Fehler."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_FROM
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_FROM, to, msg.as_string())


def _email_wrapper(shop_name: str, content_html: str) -> str:
    """Snack-House-Branded Email-Hülle. Dunkel, Gold, sauber."""
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0a0806;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0806;padding:32px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#111008;border-radius:16px;overflow:hidden;border:1px solid #2a2318;">
        <!-- HEADER -->
        <tr>
          <td style="background:linear-gradient(135deg,#0f0d0a,#1a1410);padding:28px 32px;border-bottom:1px solid #2a2318;text-align:center;">
            <div style="font-size:22px;font-weight:900;color:#C9A84C;letter-spacing:.02em;">{shop_name}</div>
            <div style="font-size:11px;color:#555;margin-top:4px;letter-spacing:.08em;">Dr.-Felix-Gerhardus-Str. 7 · 53894 Mechernich</div>
          </td>
        </tr>
        <!-- CONTENT -->
        <tr>
          <td style="padding:28px 32px;">
            {content_html}
          </td>
        </tr>
        <!-- FOOTER -->
        <tr>
          <td style="background:#0e0b08;padding:20px 32px;border-top:1px solid #1e1a14;text-align:center;">
            <p style="margin:0;font-size:11px;color:#444;">Fragen? <a href="tel:024433088966" style="color:#C9A84C;text-decoration:none;">02443-3088966</a></p>
            <p style="margin:6px 0 0;font-size:10px;color:#333;">Mittwoch: Ruhetag · Online bestellen: <a href="https://snackhouse-yassine.de/bestellen" style="color:#555;text-decoration:none;">snackhouse-yassine.de</a></p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def send_welcome_email(order: dict):
    """Willkommens-Email für Erstkunden."""
    if not SMTP_HOST or not SMTP_USER or not order.get("email"):
        return
    name = order.get("first_name") or "Gast"
    try:
        content = f"""
            <h2 style="color:#C9A84C;margin:0 0 16px;font-size:20px;">Schoen, dass du da bist! {name}</h2>
            <p style="color:#ccc;font-size:15px;line-height:1.6;margin:0 0 20px;">
              Willkommen bei <strong style="color:#fff;">Snack House Yassine</strong> &mdash; dem Treffpunkt fuer echtes Mechernicher Street Food.<br>
              Deine erste Bestellung ist bei uns eingegangen und wir freuen uns riesig.
            </p>
            <div style="background:#1a1410;border-radius:10px;padding:20px;margin:0 0 20px;border-left:3px solid #C9A84C;">
              <p style="color:#C9A84C;font-weight:700;margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.06em;">Deine Bestellung</p>
              <p style="color:#fff;margin:0;font-size:15px;">Nr. <strong>{order["order_number"]}</strong> &middot; <strong style="color:#C9A84C;">{order["total"]:.2f} &euro;</strong></p>
            </div>
            <div style="background:#0d1a0d;border:1px solid #1a3a1a;border-radius:10px;padding:18px 20px;margin:0 0 20px;">
              <p style="color:#22c55e;font-weight:700;margin:0 0 6px;font-size:13px;">Wusstest du?</p>
              <p style="color:#aaa;margin:0;font-size:13px;line-height:1.5;">
                Mit jedem Kauf sammelst du Treuepunkte. <strong style="color:#C9A84C;">10 Stempel = 1 Gratis-Ayran.</strong><br>
                Einfach beim naechsten Mal Nummer angeben &mdash; wir merken uns das.
              </p>
            </div>
            <p style="color:#888;font-size:13px;margin:0;">
              Guten Hunger &mdash; und bis zum naechsten Mal!<br>
              <span style="color:#C9A84C;font-weight:700;">Dein Snack House Team</span>
            </p>"""
        html = _email_wrapper(SHOP_NAME, content)
        _smtp_send(order["email"], f"Willkommen bei {SHOP_NAME}!", html)
        app.logger.info(f"Welcome-Email: {order['email']}")
    except Exception as e:
        app.logger.warning(f"Welcome-Email Fehler: {e}")


def send_loyalty_email(order: dict, stamps_collected: int, stamps_needed: int = 10):
    """Loyalty-Meilenstein Email (z.B. 8 von 10 Stempeln)."""
    if not SMTP_HOST or not SMTP_USER or not order.get("email"):
        return
    name = order.get("first_name") or "du"
    remaining = stamps_needed - stamps_collected
    try:
        content = f"""
            <h2 style="color:#C9A84C;margin:0 0 16px;font-size:20px;">Noch {remaining} bis zum Gratis-Ayran!</h2>
            <p style="color:#ccc;font-size:15px;line-height:1.6;margin:0 0 20px;">
              Hey {name}! Du bist fast da &mdash; nur noch <strong style="color:#C9A84C;">{remaining} Bestellung(en)</strong> und du bekommst deinen <strong style="color:#fff;">hausgemachten Gratis-Ayran</strong>.
            </p>
            <div style="text-align:center;margin:0 0 24px;">
              <div style="display:inline-block;background:#1a1410;border:2px solid #C9A84C;border-radius:12px;padding:20px 32px;">
                <div style="font-size:36px;font-weight:900;color:#C9A84C;">{stamps_collected} / {stamps_needed}</div>
                <div style="font-size:12px;color:#888;margin-top:4px;">Stempel gesammelt</div>
              </div>
            </div>
            <p style="color:#888;font-size:13px;margin:0 0 20px;text-align:center;">
              Beim naechsten Besuch einfach Telefonnummer angeben &mdash; wir pruefen sofort deinen Stand.
            </p>
            <div style="text-align:center;">
              <a href="https://snackhouse-yassine.de/bestellen" style="display:inline-block;background:linear-gradient(135deg,#C9A84C,#e8c76a);color:#000;font-weight:800;font-size:14px;padding:14px 28px;border-radius:10px;text-decoration:none;letter-spacing:.02em;">Jetzt bestellen</a>
            </div>"""
        html = _email_wrapper(SHOP_NAME, content)
        _smtp_send(order["email"], f"Noch {remaining} bis zum Gratis-Ayran! – {SHOP_NAME}", html)
        app.logger.info(f"Loyalty-Email: {order['email']} ({stamps_collected}/{stamps_needed})")
    except Exception as e:
        app.logger.warning(f"Loyalty-Email Fehler: {e}")


def send_vip_email(contact: dict):
    """VIP-Anerkennungs-Email fuer treue Stammkunden."""
    if not SMTP_HOST or not SMTP_USER or not contact.get("email"):
        return
    name = contact.get("first_name") or "Gast"
    try:
        content = f"""
            <div style="text-align:center;margin:0 0 24px;">
              <div style="font-size:32px;">&#11088;</div>
              <h2 style="color:#C9A84C;margin:8px 0 0;font-size:20px;">Nur fuer unsere besten Kunden</h2>
            </div>
            <p style="color:#ccc;font-size:15px;line-height:1.6;margin:0 0 20px;">
              Hey {name}! Du gehoerst zu den treuesten Gaesten von <strong style="color:#fff;">Snack House Yassine</strong> &mdash; und das wollten wir dir einfach mal sagen.
            </p>
            <div style="background:#1a1410;border-radius:10px;padding:20px;margin:0 0 20px;border:1px solid #C9A84C44;">
              <p style="color:#C9A84C;font-weight:700;margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.06em;">Dein VIP-Status</p>
              <p style="color:#aaa;font-size:13px;margin:0;line-height:1.5;">
                Du hast schon <strong style="color:#fff;">{contact.get('total_orders', 0)} Bestellungen</strong> aufgegeben und insgesamt <strong style="color:#C9A84C;">{contact.get('total_spent', 0):.2f} &euro;</strong> bei uns ausgegeben. Danke!
              </p>
            </div>
            <p style="color:#aaa;font-size:14px;line-height:1.6;margin:0 0 20px;">
              Als kleines Dankeschoen: Sag beim naechsten Besuch einfach <strong style="color:#C9A84C;">"VIP"</strong> &mdash; und wir ueberraschen dich.
            </p>
            <div style="text-align:center;">
              <a href="https://snackhouse-yassine.de/bestellen" style="display:inline-block;background:linear-gradient(135deg,#C9A84C,#e8c76a);color:#000;font-weight:800;font-size:14px;padding:14px 28px;border-radius:10px;text-decoration:none;">Jetzt bestellen</a>
            </div>"""
        html = _email_wrapper(SHOP_NAME, content)
        _smtp_send(contact["email"], f"Du bist VIP! – {SHOP_NAME}", html)
        app.logger.info(f"VIP-Email: {contact['email']}")
    except Exception as e:
        app.logger.warning(f"VIP-Email Fehler: {e}")


def send_review_email(order: dict, review_url: str):
    """Review-Anfrage Email nach abgeschlossener Bestellung."""
    if not SMTP_HOST or not SMTP_USER or not order.get("email"):
        return
    name = order.get("first_name") or "du"
    try:
        content = f"""
            <h2 style="color:#C9A84C;margin:0 0 16px;font-size:20px;">War alles gut, {name}?</h2>
            <p style="color:#ccc;font-size:15px;line-height:1.6;margin:0 0 20px;">
              Wir hoffen, deine Bestellung hat dir geschmeckt! Wenn du einen Moment Zeit hast &mdash; eine kurze Bewertung hilft uns enorm.
            </p>
            <div style="text-align:center;margin:24px 0;">
              <a href="{review_url}" style="display:inline-block;background:linear-gradient(135deg,#C9A84C,#e8c76a);color:#000;font-weight:800;font-size:15px;padding:16px 36px;border-radius:12px;text-decoration:none;letter-spacing:.02em;">&#11088; Jetzt bewerten &mdash; 1 Klick</a>
            </div>
            <p style="color:#555;font-size:12px;text-align:center;margin:0;">
              Kein Aufwand, grosse Wirkung. Du wirst direkt zu Google weitergeleitet.
            </p>
            <div style="margin-top:24px;padding-top:20px;border-top:1px solid #2a2318;">
              <p style="color:#444;font-size:11px;text-align:center;margin:0;">
                Du erhaeltst diese Email, weil du bei {SHOP_NAME} bestellt hast.<br>
                Bestellnummer: {order.get("order_number", "")}
              </p>
            </div>"""
        html = _email_wrapper(SHOP_NAME, content)
        _smtp_send(order["email"], f"War alles gut? Kurze Bewertung fuer {SHOP_NAME}", html)
        app.logger.info(f"Review-Email: {order['email']}")
    except Exception as e:
        app.logger.warning(f"Review-Email Fehler: {e}")


def send_winback_email(contact: dict, days: int = 30):
    """Win-back Email fuer inaktive Kunden (30d oder 60d)."""
    if not SMTP_HOST or not SMTP_USER or not contact.get("email"):
        return
    name = contact.get("first_name") or "du"
    is_60 = days >= 60
    try:
        if is_60:
            subject = f"Letzte Chance: Dein Shawarma wartet – {SHOP_NAME}"
            heading = f"Noch da, {name}?"
            teaser = "Du warst schon eine Weile nicht mehr bei uns &mdash; und wir vermissen dich ehrlich gesagt."
            offer_html = """
              <div style="background:#1a1410;border:1px solid #C9A84C44;border-radius:10px;padding:20px;margin:20px 0;text-align:center;">
                <p style="color:#C9A84C;font-weight:700;font-size:14px;margin:0 0 8px;">Komm zurueck &mdash; wir machen dir ein Angebot</p>
                <p style="color:#aaa;font-size:13px;margin:0;">Sag beim naechsten Mal einfach <strong style="color:#fff;">"ICH BIN ZURUECK"</strong> &mdash; und wir ueberraschen dich.</p>
              </div>"""
        else:
            subject = f"Dein Lieblings-Shawarma vermisst dich – {SHOP_NAME}"
            heading = f"Lange nicht gesehen, {name}!"
            teaser = "Dein Lieblingsessen wartet auf dich. Es ist schon eine Weile her seit deiner letzten Bestellung &mdash; wir wuerden uns freuen, dich wieder zu sehen."
            offer_html = ""

        content = f"""
            <h2 style="color:#C9A84C;margin:0 0 16px;font-size:20px;">{heading}</h2>
            <p style="color:#ccc;font-size:15px;line-height:1.6;margin:0 0 20px;">{teaser}</p>
            {offer_html}
            <div style="background:#0d1a0d;border-left:3px solid #22c55e;border-radius:0 8px 8px 0;padding:16px 20px;margin:0 0 24px;">
              <p style="color:#22c55e;font-weight:700;font-size:13px;margin:0 0 6px;">Was auf dich wartet:</p>
              <ul style="color:#aaa;font-size:13px;margin:0;padding-left:16px;line-height:1.8;">
                <li>Frisch zubereiteter Shawarma nach Hausrezept</li>
                <li>Knusprige Drehspiess-Pizza aus dem echten Ofen</li>
                <li>Hausgemachter Ayran &mdash; 2 &euro;</li>
              </ul>
            </div>
            <div style="text-align:center;">
              <a href="https://snackhouse-yassine.de/bestellen" style="display:inline-block;background:linear-gradient(135deg,#C9A84C,#e8c76a);color:#000;font-weight:800;font-size:14px;padding:14px 32px;border-radius:10px;text-decoration:none;">Jetzt online bestellen</a>
            </div>
            <p style="color:#444;font-size:12px;text-align:center;margin-top:20px;">Abholung oder Lieferung &middot; Mechernich &middot; Di-So ab 11 Uhr</p>"""
        html = _email_wrapper(SHOP_NAME, content)
        _smtp_send(contact["email"], subject, html)
        app.logger.info(f"Winback-{days}d-Email: {contact['email']}")
    except Exception as e:
        app.logger.warning(f"Winback-Email Fehler ({days}d): {e}")


def send_weekly_report_email(db) -> bool:
    """Woechentlicher Umsatz-Report an den Agency-Owner."""
    if not SMTP_HOST or not SMTP_USER:
        return False
    to = AGENCY_OWNER_EMAIL
    if not to:
        return False
    try:
        seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        rows = db.execute(
            "SELECT * FROM orders WHERE created_at >= ? AND status != 'storniert'",
            (seven_days_ago + " 00:00:00",),
        ).fetchall()
        total_revenue = sum(dict(r)["total"] for r in rows)
        order_count = len(rows)
        item_counts: dict = {}
        for r in rows:
            o = dict(r)
            for item in json.loads(o.get("items") or "[]"):
                n = item.get("name", "").split(" [")[0].strip()
                item_counts[n] = item_counts.get(n, 0) + item.get("qty", 1)
        top3 = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        top3_html = "".join(
            f"<li style='color:#ccc;margin-bottom:4px;'><strong style='color:#C9A84C;'>{n}</strong> &mdash; {q}x</li>"
            for n, q in top3
        )
        new_contacts = db.execute(
            "SELECT COUNT(*) FROM contacts WHERE created_at >= ?",
            (seven_days_ago + " 00:00:00",),
        ).fetchone()[0]
        content = f"""
            <h2 style="color:#C9A84C;margin:0 0 4px;font-size:18px;">Wochen-Report</h2>
            <p style="color:#555;font-size:12px;margin:0 0 24px;">Letzte 7 Tage &mdash; {SHOP_NAME}</p>
            <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px;">
              <div style="flex:1;min-width:120px;background:#1a1410;border-radius:10px;padding:16px;text-align:center;border:1px solid #2a2318;">
                <div style="font-size:24px;font-weight:900;color:#C9A84C;">{total_revenue:.0f} &euro;</div>
                <div style="font-size:11px;color:#555;margin-top:4px;">Umsatz</div>
              </div>
              <div style="flex:1;min-width:120px;background:#1a1410;border-radius:10px;padding:16px;text-align:center;border:1px solid #2a2318;">
                <div style="font-size:24px;font-weight:900;color:#fff;">{order_count}</div>
                <div style="font-size:11px;color:#555;margin-top:4px;">Bestellungen</div>
              </div>
              <div style="flex:1;min-width:120px;background:#1a1410;border-radius:10px;padding:16px;text-align:center;border:1px solid #2a2318;">
                <div style="font-size:24px;font-weight:900;color:#22c55e;">{new_contacts}</div>
                <div style="font-size:11px;color:#555;margin-top:4px;">Neue Kunden</div>
              </div>
            </div>
            <p style="color:#C9A84C;font-weight:700;font-size:13px;margin:0 0 8px;">Top-Artikel:</p>
            <ul style="margin:0 0 20px;padding-left:16px;">{top3_html}</ul>
            <p style="color:#444;font-size:12px;margin:0;">
              Fuer mehr Details: <a href="https://snackhouse-yassine.de/admin" style="color:#C9A84C;">Admin-Dashboard</a>
            </p>"""
        html = _email_wrapper(SHOP_NAME, content)
        _smtp_send(to, f"Wochen-Report {SHOP_NAME} – {datetime.datetime.now().strftime('%d.%m.%Y')}", html)
        return True
    except Exception as e:
        app.logger.warning(f"Weekly-Report-Email Fehler: {e}")
        return False


# ── CRM & SMS (Webschmiede – GHL-Ersatz) ─────────────────────────────────────

def log_message(db, phone: str, channel: str, template: str, body: str, status: str, order_number: str = ""):
    db.execute(
        "INSERT INTO message_log (contact_phone, channel, template, body, status, order_number) VALUES (?,?,?,?,?,?)",
        (phone, channel, template, body[:500], status, order_number),
    )

def send_sms(db, to: str, text: str, template: str = "", order_number: str = "") -> bool:
    to = normalize_phone(to)
    if not to or not SMS_ENABLED or not SMS_API_KEY:
        if to and template:
            log_message(db, to, "sms", template, text, "skipped", order_number)
        return False
    try:
        r = req.post(
            "https://gateway.seven.io/api/sms",
            headers={"X-Api-Key": SMS_API_KEY},
            data={"to": to, "text": text[:1600], "from": SMS_SENDER},
            timeout=12,
        )
        ok = r.status_code in (200, 201)
        log_message(db, to, "sms", template, text, "sent" if ok else f"failed:{r.status_code}", order_number)
        if ok:
            agency_metrics_svc.bump_daily(db, "sms_sent", kunde_id=KUNDE_ID or "")
        else:
            agency_metrics_svc.record_event(
                db, category="sms", action=template or "send", status="error",
                kunde_id=KUNDE_ID or "", detail=f"HTTP {r.status_code}",
            )
            agency_metrics_svc.bump_daily(db, "sms_failed", kunde_id=KUNDE_ID or "")
            app.logger.warning(f"SMS Fehler {r.status_code}: {r.text[:200]}")
        return ok
    except Exception as e:
        app.logger.warning(f"SMS Fehler: {e}")
        log_message(db, to, "sms", template, text, "error", order_number)
        agency_metrics_svc.record_event(
            db, category="sms", action=template or "send", status="error",
            kunde_id=KUNDE_ID or "", detail=str(e)[:200],
        )
        agency_metrics_svc.bump_daily(db, "sms_failed", kunde_id=KUNDE_ID or "")
        return False

def upsert_contact(db, order: dict) -> tuple[int | None, bool]:
    phone = normalize_phone(order.get("phone", ""))
    if not phone or len(phone) < 10:
        return None, False

    row = db.execute("SELECT * FROM contacts WHERE phone=?", (phone,)).fetchone()
    is_new = row is None
    tags = []

    if is_new:
        tags = ["neukunde"]
        cur = db.execute(
            """INSERT INTO contacts (phone, email, first_name, last_name, total_orders, total_spent, last_order_at, tags)
               VALUES (?,?,?,?,1,?, datetime('now'), ?)""",
            (phone, order.get("email", ""), order["first_name"], order["last_name"],
             order["total"], json.dumps(tags, ensure_ascii=False)),
        )
        contact_id = cur.lastrowid
    else:
        c = dict(row)
        tags = json.loads(c.get("tags") or "[]")
        if c["total_orders"] == 0 and "neukunde" not in tags:
            tags.append("neukunde")
        dt = order.get("delivery_type", "")
        if dt and dt not in tags:
            tags.append(dt)
        db.execute(
            """UPDATE contacts SET
               email=CASE WHEN ? != '' THEN ? ELSE email END,
               first_name=?, last_name=?,
               total_orders=total_orders+1, total_spent=total_spent+?,
               last_order_at=datetime('now'), tags=?
               WHERE phone=?""",
            (order.get("email", ""), order.get("email", ""),
             order["first_name"], order["last_name"], order["total"],
             json.dumps(tags, ensure_ascii=False), phone),
        )
        contact_id = c["id"]

    return contact_id, is_new

def order_items_text(order: dict, limit: int = 8) -> str:
    lines = [f"{i['qty']}x {i['name']}" for i in order.get("items", [])[:limit]]
    if len(order.get("items", [])) > limit:
        lines.append("…")
    return "\n".join(lines)

def automate_order_created(db, order: dict, is_new: bool):
    pay_label = {"cash": "Bar", "card": "EC-Karte", "stripe": "Online"}.get(order["pay_method"], order["pay_method"])
    del_label = "Lieferung" if order["delivery_type"] == "lieferung" else "Abholung"
    items = order_items_text(order)

    if OWNER_PHONE:
        send_sms(db, OWNER_PHONE, (
            f"NEUE BESTELLUNG!\n"
            f"Nr: {order['order_number']}\n"
            f"{order['first_name']} {order['last_name']}\n"
            f"Tel: {order['phone']}\n"
            f"{del_label} · {pay_label}\n"
            f"Zeit: {order.get('wunschzeit') or 'ASAP'}\n"
            f"────────\n{items}\n────────\n"
            f"GESAMT: {order['total']:.2f} €"
        ), "owner_new_order", order["order_number"])

    if order.get("phone"):
        neu = " Willkommen!" if is_new else ""
        send_sms(db, order["phone"], (
            f"Hallo {order['first_name']}!{neu}\n"
            f"Deine Bestellung bei {SHOP_NAME} ist eingegangen.\n"
            f"Bestellnr: {order['order_number']}\n"
            f"Wir melden uns kurz.\n"
            f"Fragen? {SHOP_PHONE}"
        ), "customer_order_received", order["order_number"])

    # Welcome-Email fuer Erstkunden (Email als primaerer Kanal)
    if is_new and order.get("email"):
        send_welcome_email(order)

    # Loyalty-Meilenstein pruefen (8 von 10 Stempeln)
    if order.get("email") and order.get("phone"):
        try:
            phone_norm = normalize_phone(order["phone"])
            loyalty_row = db.execute(
                "SELECT stamps FROM loyalty WHERE phone=?", (phone_norm,)
            ).fetchone()
            if loyalty_row:
                stamps = loyalty_row["stamps"] if hasattr(loyalty_row, 'keys') else loyalty_row[0]
                if stamps in (8, 9):
                    send_loyalty_email(order, stamps_collected=stamps, stamps_needed=10)
        except Exception:
            pass

    # VIP-Check: >10 Bestellungen ODER >150 EUR Gesamt
    if order.get("email") and order.get("phone"):
        try:
            phone_norm = normalize_phone(order["phone"])
            contact_row = db.execute(
                "SELECT * FROM contacts WHERE phone=?", (phone_norm,)
            ).fetchone()
            if contact_row:
                c = dict(contact_row)
                is_vip = c.get("total_orders", 0) >= 10 or c.get("total_spent", 0) >= 150
                tags = json.loads(c.get("tags") or "[]")
                if is_vip and "vip" not in tags:
                    tags.append("vip")
                    db.execute("UPDATE contacts SET tags=? WHERE phone=?",
                               (json.dumps(tags, ensure_ascii=False), phone_norm))
                    send_vip_email(c)
        except Exception:
            pass

def resolve_n8n_order_webhook() -> str:
    if N8N_ORDER_WEBHOOK:
        return N8N_ORDER_WEBHOOK
    kid = KUNDE_ID
    if not kid:
        return ""
    kdir = KUNDEN_DIR
    if not os.path.isdir(kdir):
        return ""
    for fname in os.listdir(kdir):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(kdir, fname), encoding="utf-8") as f:
                k = json.load(f)
            if (k.get("id") or "").upper() == kid:
                return ((k.get("n8n") or {}).get("order_webhook") or "").strip()
        except Exception:
            continue
    return ""


def notify_order_webhook(order: dict):
    webhook = resolve_n8n_order_webhook()
    if not webhook:
        return
    try:
        base = PUBLIC_BASE_URL
        payload = {
            "order_number": order.get("order_number"),
            "first_name": order.get("first_name"),
            "last_name": order.get("last_name"),
            "phone": order.get("phone"),
            "address": order.get("address"),
            "delivery_type": order.get("delivery_type"),
            "pay_method": order.get("pay_method"),
            "total": order.get("total"),
            "wunschzeit": order.get("wunschzeit"),
            "items": order.get("items", []),
            "admin_url": f"{base.rstrip('/')}/admin",
        }
        req.post(webhook, json=payload, timeout=5)
    except Exception as e:
        app.logger.warning(f"n8n webhook: {e}")

def automate_status_changed(db, order: dict, new_status: str):
    if not order.get("phone"):
        return
    msgs = {
        "zubereitung": f"Hey {order['first_name']}! Deine Bestellung wird gerade frisch zubereitet. – {SHOP_NAME}",
        "unterwegs":   f"Auf dem Weg! Deine Bestellung ist unterwegs (ca. 15–25 Min.). – {SHOP_NAME}",
        "abholbereit": f"Abholbereit! Deine Bestellung wartet auf dich. – {SHOP_NAME}",
        "fertig":      f"Danke {order['first_name']}! Wir hoffen, es hat geschmeckt. Bis bald! – {SHOP_NAME}",
    }
    tpl = f"status_{new_status}"
    if new_status in msgs:
        send_sms(db, order["phone"], msgs[new_status], tpl, order["order_number"])
    try:
        push_svc.notify_status(db, order, new_status)
    except Exception as e:
        app.logger.warning(f"push status: {e}")

    # ── Stempelkarte: Stempel bei 'fertig' vergeben (neue Kunden-Accounts) ────
    if new_status == "fertig":
        cid = order.get("customer_account_id")
        if cid:
            try:
                items = order.get("items") or []
                if isinstance(items, str):
                    import json as _json
                    items = _json.loads(items)
                subtotal = sum(
                    float(it.get("price") or 0) * int(it.get("qty") or 0)
                    for it in items
                    if not it.get("free") and not it.get("loyalty")
                )
                result = ca_svc.earn_stamp(
                    db,
                    int(cid),
                    order.get("order_number", ""),
                    delivery_type=order.get("delivery_type", ""),
                    order_subtotal=subtotal,
                )
                app.logger.info(
                    f"Stempel: order={order.get('order_number')} cid={cid} result={result}"
                )
            except Exception as e:
                app.logger.warning(f"earn_stamp error: {e}")

def get_setting(db, key: str, default: str = "") -> str:
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row and row["value"] is not None else default

def already_sent_template(db, phone: str, template: str, within_days: int = 90) -> bool:
    norm = normalize_phone(phone)
    row = db.execute(
        """SELECT 1 FROM message_log
           WHERE template=? AND status='sent'
           AND contact_phone IN (?, ?)
           AND created_at >= datetime('now', ?)
           LIMIT 1""",
        (template, phone, norm, f"-{within_days} days"),
    ).fetchone()
    return row is not None

def run_followups(db) -> dict:
    """Tägliche Follow-ups: Google-Review (nach X Tagen) + Win-back (30d / 60d inaktiv).
    Primaerer Kanal: Email (wenn verfuegbar). Fallback: SMS."""
    review_days  = int(get_setting(db, "review_days", "2") or "2")
    winback_days = int(get_setting(db, "winback_days", "30") or "30")
    review_url   = get_setting(db, "google_review_url", "") or GOOGLE_REVIEW_URL
    stats = {"reviews_sent": 0, "winbacks_sent": 0, "winbacks_60d": 0, "errors": 0}

    # ── Review: Bestellung abgeschlossen vor X Tagen ───────────────────────
    if review_url:
        rows = db.execute(
            """SELECT o.*, c.email AS contact_email FROM orders o
               LEFT JOIN contacts c ON c.phone = o.phone
               WHERE o.status='fertig' AND o.review_sent=0
               AND (o.phone != '' OR o.email != '')
               AND o.completed_at IS NOT NULL
               AND o.completed_at <= datetime('now', ?)""",
            (f"-{review_days} days",),
        ).fetchall()
        for r in rows:
            o = dict(r)
            email_addr = o.get("email") or o.get("contact_email") or ""
            phone_addr = o.get("phone") or ""
            if already_sent_template(db, phone_addr or email_addr, "review_request", within_days=365):
                db.execute("UPDATE orders SET review_sent=1 WHERE order_number=?", (o["order_number"],))
                continue
            sent = False
            # Email bevorzugen
            if email_addr:
                try:
                    send_review_email(o, review_url)
                    log_message(db, phone_addr or email_addr, "email", "review_request",
                                f"Review-Email an {email_addr}", "sent", o["order_number"])
                    sent = True
                except Exception as e:
                    app.logger.warning(f"Review-Email Fehler: {e}")
            # SMS als Fallback
            if not sent and phone_addr:
                name = o.get("first_name") or "du"
                msg = (
                    f"Hallo {name}! Hat dir deine Bestellung bei {SHOP_NAME} geschmeckt?\n"
                    f"Kurze Bewertung: {review_url}\nDanke! – {SHOP_NAME}"
                )
                sent = send_sms(db, phone_addr, msg, "review_request", o["order_number"])
            if sent:
                db.execute("UPDATE orders SET review_sent=1 WHERE order_number=?", (o["order_number"],))
                stats["reviews_sent"] += 1
            else:
                stats["errors"] += 1
    db.commit()

    # ── Win-back 30 Tage ───────────────────────────────────────────────────
    contacts_30 = db.execute(
        """SELECT * FROM contacts
           WHERE total_orders >= 1 AND last_order_at IS NOT NULL
           AND last_order_at <= datetime('now', ?)
           AND last_order_at > datetime('now', '-60 days')""",
        (f"-{winback_days} days",),
    ).fetchall()
    for c in contacts_30:
        c = dict(c)
        if already_sent_template(db, c["phone"] or c.get("email", ""), "winback_30d", within_days=90):
            continue
        sent = False
        if c.get("email"):
            try:
                send_winback_email(c, days=30)
                log_message(db, c["phone"] or c["email"], "email", "winback_30d",
                            f"Winback-30d-Email an {c['email']}", "sent", "")
                sent = True
            except Exception as e:
                app.logger.warning(f"Winback-30d-Email: {e}")
        if not sent and c.get("phone"):
            name = c.get("first_name") or "du"
            msg = (
                f"Hallo {name}! Wir vermissen dich bei {SHOP_NAME}.\n"
                f"Komm vorbei oder bestelle: {ORDER_PORTAL_URL}\n– {SHOP_PHONE}"
            )
            sent = send_sms(db, c["phone"], msg, "winback_30d", "")
        if sent:
            stats["winbacks_sent"] += 1
        else:
            stats["errors"] += 1

    # ── Win-back 60 Tage (staerkeres Angebot) ─────────────────────────────
    contacts_60 = db.execute(
        """SELECT * FROM contacts
           WHERE total_orders >= 1 AND last_order_at IS NOT NULL
           AND last_order_at <= datetime('now', '-60 days')""",
        (),
    ).fetchall()
    for c in contacts_60:
        c = dict(c)
        if already_sent_template(db, c["phone"] or c.get("email", ""), "winback_60d", within_days=120):
            continue
        sent = False
        if c.get("email"):
            try:
                send_winback_email(c, days=60)
                log_message(db, c["phone"] or c["email"], "email", "winback_60d",
                            f"Winback-60d-Email an {c['email']}", "sent", "")
                sent = True
            except Exception as e:
                app.logger.warning(f"Winback-60d-Email: {e}")
        if not sent and c.get("phone"):
            name = c.get("first_name") or "du"
            msg = (
                f"Letzte Chance, {name}! Meld dich nochmal bei uns.\n"
                f"Sag einfach 'ICH BIN ZURUECK' und wir ueberraschen dich!\n"
                f"{ORDER_PORTAL_URL}"
            )
            sent = send_sms(db, c["phone"], msg, "winback_60d", "")
        if sent:
            stats["winbacks_60d"] += 1
        else:
            stats["errors"] += 1

    db.commit()
    return stats

# ── GHL (optional, standardmäßig AUS) ───────────────────────────────────────

def ghl_sync(order):
    if not GHL_ENABLED or not GHL_TOKEN:
        return
    items_text = "\n".join(f"  {i['qty']}x {i['name']} - {i['price']:.2f} EUR" for i in order["items"])
    pay_label  = {"cash":"Barzahlung","card":"EC-/Kreditkarte","stripe":"Online (Stripe)"}.get(order["pay_method"], order["pay_method"])
    del_label  = "Lieferung" if order["delivery_type"] == "lieferung" else "Abholung"
    tags = ["neukunde", order["delivery_type"],
            "online-zahlung" if order["pay_method"]=="stripe" else "ec-zahlung" if order["pay_method"]=="card" else "barzahlung"]
    try:
        r = req.post(f"{GHL_BASE}/contacts/", headers=GHL_HEADERS, json={
            "locationId": GHL_LOC_ID, "firstName": order["first_name"],
            "lastName": order["last_name"], "phone": order["phone"],
            "email": order.get("email",""), "address1": order.get("address",""),
            "tags": tags,
            "customFields": [
                {"key":"bestellnummer","field_value":order["order_number"]},
                {"key":"bestellart","field_value":del_label},
                {"key":"bestellinhalt","field_value":items_text},
                {"key":"bestellbetrag","field_value":f"{order['total']:.2f}"},
                {"key":"zahlungsart","field_value":pay_label},
                {"key":"wunschzeit","field_value":order.get("wunschzeit","")},
                {"key":"bestellnotizen","field_value":order.get("notes","")},
            ],
        }, timeout=10)
        cd = r.json()
        contact_id = cd.get("contact",{}).get("id") or cd.get("id")
        if contact_id and GHL_PIPELINE_ID:
            req.post(f"{GHL_BASE}/opportunities/", headers=GHL_HEADERS, json={
                "locationId": GHL_LOC_ID, "pipelineId": GHL_PIPELINE_ID,
                "pipelineStageId": GHL_STAGE_NEW, "contactId": contact_id,
                "name": f"Bestellung {order['order_number']} - {order['first_name']} {order['last_name']}",
                "monetaryValue": order["total"], "status": "open",
            }, timeout=10)
    except Exception as e:
        app.logger.warning(f"GHL Fehler: {e}")

# ── Promo-Helfer ──────────────────────────────────────────────────────────────

def get_active_promo():
    db = get_db()
    now = datetime.datetime.now().isoformat()
    row = db.execute(
        "SELECT * FROM promos WHERE active=1 AND (valid_until IS NULL OR valid_until > ?) ORDER BY id DESC LIMIT 1",
        (now,)
    ).fetchone()
    if row:
        p = dict(row)
        # Abgelaufene Aktionen automatisch deaktivieren
        if p.get("valid_until") and p["valid_until"] < now:
            db.execute("UPDATE promos SET active=0 WHERE id=?", (p["id"],))
            db.commit()
            return None
        return p
    return None

# ── API Endpunkte ──────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "snack-house-order-api"})


@app.get("/api/tourmeter/fuel")
def tourmeter_fuel():
    """Öffentlich (rate-limited): aktuelle Spritpreise für TourMeter."""
    ip = request.remote_addr or "unknown"
    if rate_limit(f"tourmeter-fuel:{ip}", max_calls=40, window_s=3600):
        return jsonify({"ok": False, "error": "Zu viele Anfragen, später erneut."}), 429
    try:
        from tourmeter_fuel import DEFAULT_LAT, DEFAULT_LNG, fetch_fuel_prices
    except ImportError:
        from app.backend.tourmeter_fuel import DEFAULT_LAT, DEFAULT_LNG, fetch_fuel_prices  # type: ignore

    def _f(name: str, default: float) -> float:
        try:
            return float(request.args.get(name) or default)
        except (TypeError, ValueError):
            return default

    result = fetch_fuel_prices(
        lat=_f("lat", DEFAULT_LAT),
        lng=_f("lng", DEFAULT_LNG),
        radius_km=_f("rad", 20),
        fuel_type=(request.args.get("type") or "diesel").strip(),
        mode=(request.args.get("mode") or "cheapest").strip(),
    )
    status = 200 if result.get("ok") else (503 if result.get("code") == "missing_key" else 502)
    return jsonify(result), status


# ── Öffentlich: Aktive Aktion abrufen ─────────────────────────────────────────
@app.get("/api/promo/active")
def promo_active():
    promo = get_active_promo()
    if promo:
        return jsonify({"active": True, "promo": promo})
    return jsonify({"active": False})

@app.get("/api/loyalty/status")
def loyalty_status():
    phone = (request.args.get("phone") or "").strip()
    if not phone:
        return jsonify({"error": "Telefonnummer fehlt"}), 400
    ip = request.remote_addr or "unknown"
    if rate_limit(f"loyalty:{ip}", max_calls=30, window_s=300):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    db = get_db()
    norm = normalize_phone(phone)
    st = status_for_phone(db, norm)
    if not st:
        return jsonify({"enabled": False})
    return jsonify(st)

# ── Admin: Aktion erstellen ────────────────────────────────────────────────────
@app.post("/api/admin/promo")
@require_admin
def create_promo():
    data = request.get_json(force=True)
    title             = data.get("title", "")
    description       = data.get("description", "")
    trigger_type      = data.get("triggerType", "category")   # "category" oder "name"
    trigger_value     = data.get("triggerValue", "")          # z.B. "pizza" oder "Margherita"
    free_item_name    = data.get("freeItemName", "")
    free_item_id      = data.get("freeItemId", "")
    free_item_variant = data.get("freeItemVariant", "")
    valid_until       = data.get("validUntil", "")            # ISO-Datetime z.B. "2026-07-14T18:00"

    if not trigger_value or not free_item_name:
        return jsonify({"error": "triggerValue und freeItemName sind Pflicht"}), 400

    db = get_db()
    # Alle alten Aktionen deaktivieren
    db.execute("UPDATE promos SET active=0")
    db.execute("""
        INSERT INTO promos (title, description, trigger_type, trigger_value,
                            free_item_name, free_item_id, free_item_variant, valid_until, active)
        VALUES (?,?,?,?,?,?,?,?,1)
    """, (title, description, trigger_type, trigger_value,
          free_item_name, free_item_id, free_item_variant, valid_until or None))
    db.commit()
    promo = get_active_promo()
    return jsonify({"success": True, "promo": promo})

# ── Admin: Aktive Aktion deaktivieren ─────────────────────────────────────────
@app.delete("/api/admin/promo")
@require_admin
def deactivate_promo():
    db = get_db()
    db.execute("UPDATE promos SET active=0")
    db.commit()
    return jsonify({"success": True})

# ── Admin: Aktion-History abrufen ─────────────────────────────────────────────
@app.get("/api/admin/promos")
@require_admin
def list_promos():
    db = get_db()
    rows = db.execute("SELECT * FROM promos ORDER BY id DESC LIMIT 20").fetchall()
    return jsonify([dict(r) for r in rows])

def _settings_map(db) -> dict:
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def _current_shop_status(db=None):
    """SoT: Tenant-JSON + DB-Settings → ein Status (Europe/Berlin)."""
    if db is None:
        db = get_db()
    settings = _settings_map(db)
    kid = KUNDE_ID or "SHY001"
    kunde = integrations_svc.load_kunde_json(kid)
    return shop_status_svc.compute_shop_status(kunde=kunde, settings=settings)


# ── Öffentlich: Settings abrufen ───────────────────────────────────────────
@app.get("/api/settings")
def get_settings():
    db = get_db()
    s = _settings_map(db)
    ov_rows = db.execute("SELECT * FROM menu_overrides").fetchall()
    overrides = {}
    for r in ov_rows:
        row = dict(r)
        overrides[row["item_id"]] = {
            "available": bool(row.get("available", 1)),
            "note": row.get("note") or "",
            "price": row.get("price"),
            "name": row.get("name"),
            "desc": row.get("desc"),
            "image_url": row.get("image_url"),
        }
    status = _current_shop_status(db)
    return jsonify({
        "online":        s.get("online","1") == "1",
        "wait_pickup":   int(s.get("wait_pickup","20")),
        "wait_delivery": int(s.get("wait_delivery","40")),
        "offline_msg":   s.get("offline_msg","Wir sind gleich zurück!"),
        "overrides":     overrides,
        # Kompatibilitäts-Felder aus SoT (Clients sollen /api/shop-status nutzen)
        "store_open":    status.get("store_open"),
        "accept_orders": status.get("accept_orders"),
        "timezone":      status.get("timezone"),
        "label":         status.get("label"),
    })


@app.get("/api/shop-status")
def get_shop_status():
    """Einzige serverseitige Ampel: Öffnung, Pause, Abholung, Lieferung, Vorbestellung."""
    status = _current_shop_status()
    status["phone"] = SHOP_PHONE
    status["shopName"] = SHOP_NAME
    return jsonify(status)


@app.get("/api/order-options")
def get_order_options():
    """Zeitfenster, Zahlungsarten, Gebühren für Abholung/Lieferung."""
    order_type = (request.args.get("type") or "pickup").strip().lower()
    try:
        subtotal = float(request.args.get("subtotal") or 0)
    except ValueError:
        subtotal = 0.0
    status = _current_shop_status()
    return jsonify(order_portal_svc.build_order_options(status, order_type=order_type, subtotal=subtotal))


@app.post("/api/delivery-check")
def delivery_check():
    data = request.get_json(force=True) or {}
    kid = KUNDE_ID or "SHY001"
    kunde = integrations_svc.load_kunde_json(kid)
    loc = shop_status_svc.load_location_config(kunde)
    result = order_portal_svc.check_delivery_zone(
        plz=data.get("plz") or "",
        city=data.get("city") or "",
        street=data.get("street") or "",
        zones=loc.get("delivery_zones") or [],
    )
    return jsonify(result)


@app.get("/api/order-status/<order_number>")
def public_order_status(order_number: str):
    """Öffentlicher Bestellstatus nur mit Bestellnummer (kein Auth)."""
    nr = (order_number or "").strip()
    if not nr or len(nr) > 40:
        return jsonify({"error": "Ungültige Bestellnummer"}), 400
    db = get_db()
    row = db.execute(
        "SELECT order_number, status, delivery_type, wunschzeit, total, created_at, first_name FROM orders WHERE order_number=?",
        (nr,),
    ).fetchone()
    if not row:
        return jsonify({"error": "Bestellung nicht gefunden"}), 404
    o = dict(row)
    pub = order_portal_svc.public_status(o.get("status"))
    return jsonify({
        "orderNumber": o["order_number"],
        "status": pub,
        "deliveryType": o.get("delivery_type"),
        "wunschzeit": o.get("wunschzeit") or "",
        "total": o.get("total"),
        "createdAt": o.get("created_at"),
        "firstName": (o.get("first_name") or "")[:1] + "…" if o.get("first_name") else "",
        "phone": SHOP_PHONE,
        "shopName": SHOP_NAME,
    })

# ── Admin: Settings speichern ──────────────────────────────────────────────
@app.get("/api/admin/settings")
@require_admin
def get_admin_settings():
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return jsonify({r["key"]: r["value"] for r in rows})

@app.post("/api/admin/settings")
@require_admin
def update_settings():
    data = request.get_json(force=True)
    db   = get_db()
    for key, val in data.items():
        db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, str(val)))
    db.commit()
    return jsonify({"success": True})

# ── Admin: Artikel-Verfügbarkeit ───────────────────────────────────────────
@app.post("/api/admin/send-order-link")
@require_admin
def admin_send_order_link():
    """SMS mit Bestellportal-Link, z. B. während Kunde am Telefon ist."""
    data = request.get_json(force=True) or {}
    phone = (data.get("phone") or "").strip()
    if not phone:
        return jsonify({"error": "Telefonnummer fehlt"}), 400
    norm = normalize_phone(phone)
    if len(re.sub(r"\D", "", norm)) < 10:
        return jsonify({"error": "Ungültige Telefonnummer"}), 400

    ip = request.remote_addr or "unknown"
    if rate_limit(f"sms-link:{ip}", max_calls=20, window_s=3600):
        return jsonify({"error": "Zu viele Anfragen. Bitte kurz warten."}), 429
    if rate_limit(f"sms-link:{norm}", max_calls=3, window_s=3600):
        return jsonify({"error": "An diese Nummer wurde die SMS bereits gesendet. Bitte 1 Stunde warten."}), 429

    if not SMS_ENABLED or not SMS_API_KEY:
        return jsonify({
            "error": "SMS ist noch nicht aktiv. seven.io API-Key und OWNER_PHONE auf dem Server einrichten.",
            "portal_url": ORDER_PORTAL_URL,
        }), 503

    text = (
        f"Hallo! Hier ist {SHOP_NAME}.\n"
        f"Bestelle bequem online (Abholung oder Lieferung):\n"
        f"{ORDER_PORTAL_URL}\n"
        f"Fragen? {SHOP_PHONE}"
    )
    db = get_db()
    ok = send_sms(db, phone, text, "order_link_invite", "")
    db.commit()
    if not ok:
        return jsonify({"error": "SMS konnte nicht gesendet werden. seven.io prüfen."}), 502
    return jsonify({"success": True, "phone": norm, "portal_url": ORDER_PORTAL_URL})

@app.post("/api/admin/menu-override")
@require_admin
def menu_override():
    data      = request.get_json(force=True)
    item_id   = data.get("itemId","")
    available = 1 if data.get("available", True) else 0
    note      = data.get("note","")
    if not item_id:
        return jsonify({"error": "itemId required"}), 400
    db = get_db()
    row = db.execute("SELECT * FROM menu_overrides WHERE item_id=?", (item_id,)).fetchone()
    cur = dict(row) if row else {}
    price = data.get("price", cur.get("price"))
    name  = data.get("name", cur.get("name"))
    desc  = data.get("desc", cur.get("desc"))
    image = data.get("image_url", cur.get("image_url"))
    db.execute(
        """INSERT OR REPLACE INTO menu_overrides
           (item_id, available, note, price, name, desc, image_url)
           VALUES (?,?,?,?,?,?,?)""",
        (item_id, available, note, price, name, desc, image),
    )
    db.commit()
    return jsonify({"success": True})

# ── Admin: Tagesreport ─────────────────────────────────────────────────────
def _parse_report_range() -> tuple[str, str]:
    """from/to query params (YYYY-MM-DD) or year+month or previous calendar month."""
    import bookkeeping as bk

    q_from = request.args.get("from", "").strip()
    q_to = request.args.get("to", "").strip()
    if q_from and q_to:
        return q_from, q_to

    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if year and month:
        return bk._month_bounds(year, month)

    y, m = bk._prev_month()
    return bk._month_bounds(y, m)


@app.get("/api/admin/report/today")
@require_admin
def report_today():
    db    = get_db()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    rows  = db.execute(
        "SELECT * FROM orders WHERE created_at >= ? AND status != 'storniert'",
        (today + " 00:00:00",)
    ).fetchall()
    item_counts = {}
    total_revenue = 0.0
    delivery_count = pickup_count = 0
    for r in rows:
        o = dict(r)
        items = json.loads(o["items"] or "[]")
        total_revenue  += o["total"]
        if o["delivery_type"] == "lieferung": delivery_count += 1
        else: pickup_count += 1
        for item in items:
            name = item.get("name","").split(" [")[0].strip()
            item_counts[name] = item_counts.get(name,0) + item.get("qty",1)
    top_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    return jsonify({
        "date": today, "order_count": len(rows),
        "total_revenue": round(total_revenue,2),
        "delivery_count": delivery_count, "pickup_count": pickup_count,
        "top_items": [{"name":n,"qty":q} for n,q in top_items],
    })


@app.get("/api/admin/report/month")
@require_admin
def report_month():
    db = get_db()
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if PORTAL_MODE == "handwerk":
        return jsonify(jobs_svc.month_report(db, year=year, month=month))
    import bookkeeping as bk
    return jsonify(bk.month_report(db, year=year, month=month))


@app.get("/api/admin/analytics")
@require_admin
def admin_analytics():
    """Umfassendes Analytics-Dashboard fuer das Admin-Panel."""
    db = get_db()
    days = request.args.get("days", 30, type=int)
    if days not in (7, 14, 30, 60, 90):
        days = 30
    since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d") + " 00:00:00"

    # ── Umsatz & Volumen ───────────────────────────────────────────────────
    orders = [dict(r) for r in db.execute(
        "SELECT * FROM orders WHERE created_at >= ? AND status != 'storniert'", (since,)
    ).fetchall()]
    total_revenue = sum(o["total"] for o in orders)
    order_count = len(orders)
    avg_order = round(total_revenue / order_count, 2) if order_count else 0
    delivery_count = sum(1 for o in orders if o.get("delivery_type") == "lieferung")
    pickup_count = order_count - delivery_count

    # ── Vorperiode zum Vergleich ───────────────────────────────────────────
    prev_since = (datetime.datetime.now() - datetime.timedelta(days=days * 2)).strftime("%Y-%m-%d") + " 00:00:00"
    prev_orders = db.execute(
        "SELECT COUNT(*), SUM(total) FROM orders WHERE created_at >= ? AND created_at < ? AND status != 'storniert'",
        (prev_since, since),
    ).fetchone()
    prev_count = prev_orders[0] or 0
    prev_revenue = float(prev_orders[1] or 0)

    # ── Tagesumsatz (letzten 14 Tage) ─────────────────────────────────────
    daily_rows = db.execute(
        """SELECT DATE(created_at) AS day, COUNT(*) AS cnt, SUM(total) AS rev
           FROM orders WHERE created_at >= ? AND status != 'storniert'
           GROUP BY day ORDER BY day""",
        ((datetime.datetime.now() - datetime.timedelta(days=14)).strftime("%Y-%m-%d") + " 00:00:00",),
    ).fetchall()
    daily = [{"day": r["day"], "orders": r["cnt"], "revenue": round(r["rev"] or 0, 2)} for r in daily_rows]

    # ── Peak-Stunden ───────────────────────────────────────────────────────
    hours_rows = db.execute(
        """SELECT CAST(strftime('%H', created_at) AS INTEGER) AS hour, COUNT(*) AS cnt
           FROM orders WHERE created_at >= ? AND status != 'storniert'
           GROUP BY hour ORDER BY cnt DESC""",
        (since,),
    ).fetchall()
    peak_hours = [{"hour": r["hour"], "orders": r["cnt"]} for r in hours_rows[:8]]

    # ── Top-Items ──────────────────────────────────────────────────────────
    item_counts: dict = {}
    item_revenue: dict = {}
    for o in orders:
        for item in json.loads(o.get("items") or "[]"):
            n = item.get("name", "").split(" [")[0].strip()
            q = item.get("qty", 1)
            p = item.get("price", 0)
            item_counts[n] = item_counts.get(n, 0) + q
            item_revenue[n] = item_revenue.get(n, 0) + q * p
    top_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_items_data = [{"name": n, "qty": q, "revenue": round(item_revenue.get(n, 0), 2)} for n, q in top_items]

    # ── Kunden-Segmente ────────────────────────────────────────────────────
    now_iso = datetime.datetime.now().isoformat()
    contacts_all = [dict(r) for r in db.execute("SELECT * FROM contacts").fetchall()]
    segments = {"champion": 0, "loyal": 0, "at_risk": 0, "lost": 0, "new": 0}
    top_customers = []
    at_risk_contacts = []
    for c in contacts_all:
        lo = c.get("last_order_at") or ""
        total_o = c.get("total_orders", 0) or 0
        total_s = float(c.get("total_spent") or 0)
        try:
            days_inactive = (datetime.datetime.now() - datetime.datetime.fromisoformat(lo)).days if lo else 999
        except Exception:
            days_inactive = 999
        if total_o >= 5 and days_inactive <= 14:
            segments["champion"] += 1
        elif 3 <= total_o < 5:
            segments["loyal"] += 1
        elif days_inactive > 60:
            segments["lost"] += 1
        elif days_inactive > 30:
            segments["at_risk"] += 1
            at_risk_contacts.append({"name": f"{c.get('first_name','')} {c.get('last_name','')}".strip(),
                                     "phone": c.get("phone", ""), "days_inactive": days_inactive,
                                     "total_orders": total_o, "total_spent": total_s})
        elif total_o == 1:
            segments["new"] += 1
        top_customers.append({"name": f"{c.get('first_name','')} {c.get('last_name','')}".strip(),
                               "phone": c.get("phone", ""), "total_orders": total_o,
                               "total_spent": total_s, "days_inactive": days_inactive})
    top_customers.sort(key=lambda x: x["total_spent"], reverse=True)
    at_risk_contacts.sort(key=lambda x: x["days_inactive"], reverse=True)

    # ── CLV (Customer Lifetime Value) Durchschnitt ─────────────────────────
    clv = round(sum(c.get("total_spent") or 0 for c in contacts_all) / len(contacts_all), 2) if contacts_all else 0

    # ── Neue vs. wiederkehrende Kunden (im Zeitraum) ───────────────────────
    new_customers = db.execute(
        "SELECT COUNT(*) FROM contacts WHERE created_at >= ?", (since,)
    ).fetchone()[0]

    return jsonify({
        "period_days": days,
        "revenue": {"total": round(total_revenue, 2), "prev": round(prev_revenue, 2),
                    "avg_order": avg_order},
        "orders": {"total": order_count, "prev": prev_count,
                   "delivery": delivery_count, "pickup": pickup_count},
        "customers": {"total": len(contacts_all), "new_in_period": new_customers,
                      "avg_clv": clv},
        "daily": daily,
        "peak_hours": peak_hours,
        "top_items": top_items_data,
        "segments": segments,
        "top_customers": top_customers[:10],
        "at_risk": at_risk_contacts[:10],
    })


@app.post("/api/cron/weekly-report")
def cron_weekly_report():
    """Woechentlicher Umsatz-Report an den Agency-Owner. CRON_SECRET erforderlich."""
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    ok = send_weekly_report_email(db)
    return jsonify({"success": ok})


def send_upsell_email(contact: dict, upsell_type: str, context: dict | None = None):
    """Upsell-Email basierend auf Bestellhistorie."""
    if not SMTP_HOST or not SMTP_USER or not contact.get("email"):
        return False
    name = contact.get("first_name") or "du"
    ctx = context or {}
    try:
        if upsell_type == "try_drehspiess":
            subject = f"Hast du unsere Drehspiess-Pizza schon probiert? – {SHOP_NAME}"
            content = f"""
                <h2 style="color:#C9A84C;margin:0 0 16px;font-size:20px;">Hey {name}, kennst du das schon?</h2>
                <p style="color:#ccc;font-size:15px;line-height:1.6;margin:0 0 20px;">
                  Du bist ein Burger-Fan &mdash; das wissen wir. Aber hast du unsere
                  <strong style="color:#fff;">Drehspiess-Pizza</strong> schon probiert?
                  Frisch belegt, im echten Steinofen. Vielen unserer Burger-Stammkunden ist sie sofort zur neuen Lieblings-Pizza geworden.
                </p>
                <div style="background:#1a1410;border-radius:10px;padding:20px;margin:0 0 24px;border-left:3px solid #C9A84C;">
                  <p style="color:#C9A84C;font-weight:700;font-size:14px;margin:0 0 8px;">Drehspiess-Pizza ab {ctx.get('price','8,90 EUR')}</p>
                  <p style="color:#aaa;font-size:13px;margin:0;">Geheimrezept, hausgemachte Sauce, frische Zutaten. Einmal probiert, immer wieder bestellt.</p>
                </div>
                <div style="text-align:center;">
                  <a href="https://snackhouse-yassine.de/bestellen" style="display:inline-block;background:linear-gradient(135deg,#C9A84C,#e8c76a);color:#000;font-weight:800;font-size:14px;padding:14px 32px;border-radius:10px;text-decoration:none;">Jetzt ausprobieren</a>
                </div>"""
        elif upsell_type == "add_ayran":
            subject = f"Dein Essen + Ayran = perfekte Kombo – {SHOP_NAME}"
            content = f"""
                <h2 style="color:#C9A84C;margin:0 0 16px;font-size:20px;">Noch etwas zum Trinken, {name}?</h2>
                <p style="color:#ccc;font-size:15px;line-height:1.6;margin:0 0 20px;">
                  Unser <strong style="color:#fff;">hausgemachter Ayran</strong> ist die perfekte Begleitung zu Shawarma und Doner.
                  Frisch, cremig, authentisch &mdash; und nur <strong style="color:#C9A84C;">2 EUR</strong>.
                </p>
                <div style="background:#1a1410;border-radius:10px;padding:20px;margin:0 0 24px;text-align:center;">
                  <div style="font-size:36px;margin-bottom:8px;">&#129371;</div>
                  <p style="color:#C9A84C;font-weight:700;font-size:16px;margin:0;">Hausgemachter Ayran &ndash; 2 EUR</p>
                  <p style="color:#555;font-size:12px;margin:8px 0 0;">Einfach bei deiner naechsten Bestellung dazu kommen lassen</p>
                </div>
                <div style="text-align:center;">
                  <a href="https://snackhouse-yassine.de/bestellen" style="display:inline-block;background:linear-gradient(135deg,#C9A84C,#e8c76a);color:#000;font-weight:800;font-size:14px;padding:14px 32px;border-radius:10px;text-decoration:none;">Jetzt bestellen</a>
                </div>"""
        elif upsell_type == "loyalty_reminder":
            stamps = ctx.get("stamps", 0)
            remaining = max(1, 10 - stamps)
            subject = f"Noch {remaining} bis zum Gratis-Ayran! – {SHOP_NAME}"
            content = f"""
                <h2 style="color:#C9A84C;margin:0 0 16px;font-size:20px;">Du bist fast da, {name}!</h2>
                <p style="color:#ccc;font-size:15px;line-height:1.6;margin:0 0 20px;">
                  Noch <strong style="color:#C9A84C;">{remaining} Bestellung(en)</strong> und du bekommst deinen
                  <strong style="color:#fff;">hausgemachten Gratis-Ayran</strong>.
                  Das schaffst du!
                </p>
                <div style="text-align:center;margin:24px 0;">
                  <div style="display:inline-block;background:#1a1410;border:2px solid #C9A84C;border-radius:12px;padding:20px 40px;">
                    <div style="font-size:32px;font-weight:900;color:#C9A84C;">{stamps} / 10</div>
                    <div style="font-size:12px;color:#888;margin-top:4px;">Stempel</div>
                  </div>
                </div>
                <div style="text-align:center;">
                  <a href="https://snackhouse-yassine.de/bestellen" style="display:inline-block;background:linear-gradient(135deg,#C9A84C,#e8c76a);color:#000;font-weight:800;font-size:14px;padding:14px 32px;border-radius:10px;text-decoration:none;">Jetzt bestellen</a>
                </div>"""
        else:
            return False

        html = _email_wrapper(SHOP_NAME, content)
        _smtp_send(contact["email"], subject, html)
        return True
    except Exception as e:
        app.logger.warning(f"Upsell-Email ({upsell_type}) Fehler: {e}")
        return False


def run_upsell_emails(db) -> dict:
    """Sendet Upsell-Emails basierend auf Bestellhistorie.
    - Burger-Stammkunden: Drehspiess-Empfehlung
    - Keine-Getraenk-Kunden: Ayran-Tipp
    - Loyalty-Reminder (8-9 Stempel, inaktiv >7 Tage)
    Aufgerufen via /api/cron/upsell oder manuell.
    """
    stats = {"try_drehspiess": 0, "add_ayran": 0, "loyalty_reminder": 0, "errors": 0}

    contacts = [dict(r) for r in db.execute(
        "SELECT * FROM contacts WHERE email != '' AND total_orders >= 2"
    ).fetchall()]

    for c in contacts:
        if not c.get("email"):
            continue

        # Burger-Stammkunden → Drehspiess probieren?
        if not already_sent_template(db, c["phone"] or c["email"], "upsell_drehspiess", within_days=180):
            phone = c.get("phone") or ""
            orders = db.execute(
                "SELECT items FROM orders WHERE phone=? AND status != 'storniert' ORDER BY created_at DESC LIMIT 10",
                (phone,),
            ).fetchall()
            burger_count = sum(
                1 for o in orders
                for item in json.loads(dict(o).get("items") or "[]")
                if "burger" in item.get("name", "").lower()
            )
            drehspiess_count = sum(
                1 for o in orders
                for item in json.loads(dict(o).get("items") or "[]")
                if "drehspiess" in item.get("name", "").lower() or "pizza" in item.get("name", "").lower()
            )
            if burger_count >= 2 and drehspiess_count == 0:
                if send_upsell_email(c, "try_drehspiess"):
                    log_message(db, c["phone"] or c["email"], "email", "upsell_drehspiess",
                                "Drehspiess-Upsell", "sent", "")
                    stats["try_drehspiess"] += 1
                else:
                    stats["errors"] += 1

        # Keine-Getraenk-Kunden → Ayran vorschlagen
        if not already_sent_template(db, c["phone"] or c["email"], "upsell_ayran", within_days=180):
            phone = c.get("phone") or ""
            orders = db.execute(
                "SELECT items FROM orders WHERE phone=? AND status != 'storniert' ORDER BY created_at DESC LIMIT 15",
                (phone,),
            ).fetchall()
            getraenk_count = sum(
                1 for o in orders
                for item in json.loads(dict(o).get("items") or "[]")
                if any(g in item.get("name", "").lower() for g in ["ayran", "cola", "fanta", "wasser", "getraenk", "drink"])
            )
            if c.get("total_orders", 0) >= 3 and getraenk_count == 0:
                if send_upsell_email(c, "add_ayran"):
                    log_message(db, c["phone"] or c["email"], "email", "upsell_ayran",
                                "Ayran-Upsell", "sent", "")
                    stats["add_ayran"] += 1
                else:
                    stats["errors"] += 1

        # Loyalty-Reminder: 8-9 Stempel, seit >7 Tagen nicht bestellt
        if c.get("phone") and not already_sent_template(db, c["phone"] or c["email"], "upsell_loyalty_reminder", within_days=30):
            loyalty_row = db.execute(
                "SELECT stamps FROM loyalty WHERE phone=?", (c["phone"],)
            ).fetchone()
            if loyalty_row:
                stamps = loyalty_row[0] if not hasattr(loyalty_row, 'keys') else loyalty_row["stamps"]
                try:
                    days_inactive = (
                        datetime.datetime.now() - datetime.datetime.fromisoformat(c.get("last_order_at") or "")
                    ).days if c.get("last_order_at") else 0
                except Exception:
                    days_inactive = 0
                if stamps in (8, 9) and days_inactive >= 7:
                    if send_upsell_email(c, "loyalty_reminder", {"stamps": stamps}):
                        log_message(db, c["phone"] or c["email"], "email", "upsell_loyalty_reminder",
                                    f"Loyalty-Reminder {stamps}/10", "sent", "")
                        stats["loyalty_reminder"] += 1
                    else:
                        stats["errors"] += 1

    db.commit()
    return stats


@app.post("/api/cron/upsell")
def cron_upsell():
    """Upsell-Emails basierend auf Bestellhistorie. CRON_SECRET erforderlich."""
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    stats = run_upsell_emails(db)
    return jsonify({"success": True, **stats})


@app.get("/api/admin/export/orders.csv")
@require_admin
def export_orders_csv():
    import bookkeeping as bk
    import jobs as jobs_mod

    db = get_db()
    date_from, date_to = _parse_report_range()
    stamp = date_from[:7]
    if PORTAL_MODE == "handwerk":
        csv_data = jobs_mod.jobs_csv(db, date_from=date_from, date_to=date_to)
        fname = f"jobs_{stamp}.csv"
    else:
        csv_data = bk.orders_csv(db, date_from=date_from, date_to=date_to)
        fname = f"bestellungen_{stamp}.csv"
    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@app.get("/api/admin/integrations/status")
@require_admin
def admin_integrations_status():
    kid = KUNDE_ID or request.args.get("kunde_id", "").strip().upper()
    if not kid:
        return jsonify({"error": "KUNDE_ID nicht gesetzt"}), 400
    return jsonify(integrations_svc.integration_status(kid))


@app.post("/api/admin/integrations/lexware/test")
@require_admin
def admin_lexware_test():
    from integrations.lexware import test_connection

    kid = KUNDE_ID or (request.get_json(silent=True) or {}).get("kunde_id", "")
    kid = (kid or "").strip().upper()
    if not kid:
        return jsonify({"error": "KUNDE_ID nicht gesetzt"}), 400
    kunde = integrations_svc.load_kunde_json(kid)
    cfg = integrations_svc.integrations_config(kunde)
    return jsonify(test_connection(kunde, cfg))


@app.get("/api/admin/integrations/log")
@require_admin
def admin_integrations_log():
    db = get_db()
    rows = db.execute(
        """SELECT provider, action, ref, status, detail, created_at
           FROM integration_log ORDER BY id DESC LIMIT 50"""
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/admin/meta")
@require_admin
def admin_meta():
    return jsonify({
        "portal_mode": PORTAL_MODE,
        "features": {
            "orders": PORTAL_MODE == "gastro",
            "jobs": PORTAL_MODE == "handwerk",
            "menu": PORTAL_MODE == "gastro",
            "printer": PORTAL_MODE == "gastro",
        },
    })


@app.get("/api/portal/config")
def portal_config_public():
    return jsonify({"portal_mode": PORTAL_MODE})


@app.post("/api/anfrage")
def create_anfrage():
    if PORTAL_MODE != "handwerk":
        return jsonify({"error": "Anfragen nur im Handwerk-Modus"}), 404
    ip = request.remote_addr or "unknown"
    if rate_limit(f"anfrage:{ip}", max_calls=8, window_s=3600):
        return jsonify({"error": "Zu viele Anfragen. Bitte später erneut."}), 429
    data = request.get_json(force=True) or {}
    if (data.get("_hp") or data.get("website") or "").strip():
        return jsonify({"success": True, "ref": ""})
    try:
        job = jobs_svc.create_job(get_db(), data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"success": True, "ref": job.get("ref"), "id": job.get("id")})


@app.get("/api/admin/jobs")
@require_admin
def admin_jobs_list():
    status = request.args.get("status")
    return jsonify({"jobs": jobs_svc.list_jobs(get_db(), status=status)})


@app.post("/api/admin/jobs")
@require_admin
def admin_jobs_create():
    data = request.get_json(force=True) or {}
    data["source"] = "admin"
    try:
        job = jobs_svc.create_job(get_db(), data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(job)


@app.patch("/api/admin/jobs/<int:job_id>")
@require_admin
def admin_jobs_update(job_id: int):
    data = request.get_json(force=True) or {}
    try:
        job = jobs_svc.update_job(get_db(), job_id, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not job:
        return jsonify({"error": "Nicht gefunden"}), 404
    return jsonify(job)


@app.get("/api/admin/jobs/<int:job_id>")
@require_admin
def admin_jobs_get(job_id: int):
    job = jobs_svc.get_job(get_db(), job_id)
    if not job:
        return jsonify({"error": "Nicht gefunden"}), 404
    return jsonify(job)


@app.get("/api/push/config")
def push_config():
    return jsonify(push_svc.config())


@app.get("/api/push/vapid-public-key")
def push_vapid_public():
    cfg = push_svc.config()
    if not cfg["configured"]:
        return jsonify({"configured": False, "error": "Push nicht eingerichtet"}), 503
    return jsonify({"configured": True, "publicKey": cfg["public_key"]})


@app.post("/api/push/subscribe")
def push_subscribe_route():
    if rate_limit("push_subscribe", 30, 60):
        return jsonify({"error": "Rate limit"}), 429
    data = request.get_json(force=True) or {}
    order_number = (data.get("order_number") or data.get("orderNumber") or "").strip()
    subscription = data.get("subscription") or data
    db = get_db()
    result = push_svc.subscribe(db, order_number, subscription)
    if not result.get("ok"):
        return jsonify(result), 400
    db.commit()
    row = db.execute("SELECT * FROM orders WHERE order_number=?", (order_number,)).fetchone()
    if row:
        try:
            push_svc.notify_order_created(db, dict(row))
            db.commit()
        except Exception as e:
            app.logger.warning(f"push welcome: {e}")
    return jsonify({"success": True, **result})


@app.post("/api/order")
def create_order():
    ip  = request.remote_addr or "unknown"
    if rate_limit(f"order:{ip}", max_calls=10, window_s=3600):
        return jsonify({"error": "Zu viele Bestellungen. Bitte warte etwas."}), 429

    data = request.get_json(force=True)

    if (data.get("_hp") or data.get("website") or "").strip():
        return jsonify({"success": True, "orderNumber": data.get("orderNumber", "")})

    err = validate_order(data)
    if err:
        return jsonify({"error": err}), 400

    db = get_db()
    status = _current_shop_status(db)
    status_err = shop_status_svc.assert_orders_accepted(
        status, delivery_type=data.get("deliveryType") or ""
    )
    if status_err:
        return jsonify({"error": status_err, "shop_status": status}), 403

    # Strukturierte Lieferadresse zusammenbauen + Zone prüfen
    if (data.get("deliveryType") or "") == "lieferung":
        street = (data.get("street") or "").strip()
        house = (data.get("houseNumber") or data.get("house_number") or "").strip()
        plz = (data.get("plz") or "").strip()
        city = (data.get("city") or "").strip()
        floor = (data.get("floor") or "").strip()
        doorbell = (data.get("doorbell") or "").strip()
        if street and house and plz and city:
            addr_parts = [f"{street} {house}", f"{plz} {city}"]
            if floor:
                addr_parts.append(f"Etage {floor}")
            if doorbell:
                addr_parts.append(f"Klingel: {doorbell}")
            data["address"] = ", ".join(addr_parts)
        zone = order_portal_svc.check_delivery_zone(
            plz=plz or "",
            city=city or (data.get("address") or ""),
            street=street or (data.get("address") or ""),
            zones=(status.get("delivery_zones") or []),
        )
        if not zone.get("ok"):
            return jsonify({"error": zone.get("message") or "Außerhalb des Liefergebiets"}), 400

    # Zahlungs-Mindestbetrag serverseitig
    try:
        items_sub = sum(
            float(it.get("price") or 0) * int(it.get("qty") or 0)
            for it in (data.get("items") or [])
            if not it.get("free") and not it.get("loyalty")
        )
    except (TypeError, ValueError):
        items_sub = 0.0
    pays = order_portal_svc.payment_options(
        items_sub, status.get("payment") or {}, delivery=(data.get("deliveryType") == "lieferung")
    )
    pay_id = data.get("payMethod")
    pay_meta = next((p for p in pays if p["id"] == pay_id), None)
    if not pay_meta or not pay_meta.get("enabled"):
        return jsonify({
            "error": (pay_meta or {}).get("reason") or "Zahlungsart nicht verfügbar",
        }), 400

    price_err = validate_order_prices(db, data)
    if price_err:
        return jsonify({"error": price_err}), 400

    order = {
        "order_number":  data.get("orderNumber",""),
        "first_name":    data.get("firstName",""),
        "last_name":     data.get("lastName",""),
        "phone":         data.get("phone",""),
        "email":         data.get("email",""),
        "address":       data.get("address",""),
        "delivery_type": data.get("deliveryType","abholung"),
        "pay_method":    data.get("payMethod","cash"),
        "items":         data.get("items",[]),
        "total":         float(data.get("total",0)),
        "wunschzeit":    data.get("wunschzeit",""),
        "notes":         data.get("notes",""),
    }

    # Aktive Promo mitloggen
    promo = get_active_promo()
    promo_label = None
    if promo:
        promo_label = promo.get("title") or promo.get("description") or ""

    # Eingeloggten Kunden ermitteln (optional)
    _ca_token = (
        request.headers.get("X-Customer-Token", "")
        or request.cookies.get("customer_session", "")
    )
    _ca_sess = ca_svc.get_session(db, _ca_token) if _ca_token else None
    _ca_id = int(_ca_sess["customer_id"]) if _ca_sess else None

    # original_requested_ready_at: wird bei Bestellerstellung aus wunschzeit berechnet
    # und danach NIEMALS aktualisiert – dient der historischen Auswertung
    _orig_ready = prio_svc._parse_wunschzeit(order.get("wunschzeit"))
    _orig_ready_iso = _orig_ready.isoformat() if _orig_ready else None

    db.execute("""INSERT OR IGNORE INTO orders
        (order_number,first_name,last_name,phone,email,address,delivery_type,pay_method,
         items,total,wunschzeit,notes,promo_applied,contact_id,customer_account_id,
         original_requested_ready_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (order["order_number"], order["first_name"], order["last_name"],
         order["phone"], order["email"], order["address"],
         order["delivery_type"], order["pay_method"],
         json.dumps(order["items"], ensure_ascii=False),
         order["total"], order["wunschzeit"], order["notes"], promo_label, None, _ca_id,
         _orig_ready_iso)
    )

    contact_id, is_new = upsert_contact(db, order)
    if contact_id:
        db.execute("UPDATE orders SET contact_id=? WHERE order_number=?", (contact_id, order["order_number"]))

    phone_norm = normalize_phone(order["phone"])
    loyalty_info = apply_after_order(db, phone_norm, order["order_number"], order["items"])
    db.commit()

    order["promo_applied"] = promo_label
    agency_metrics_svc.bump_daily(db, "orders", kunde_id=KUNDE_ID or "")
    agency_metrics_svc.record_event(
        db, category="order", action="created", status="ok",
        kunde_id=KUNDE_ID or "", detail=order["order_number"],
    )
    # Analytics Event: Bestellung abgeschlossen
    ae_svc.track_order_completed(db, order, customer_id=_ca_id)
    # Operational Alert auflösen falls Pause-Alert existiert
    oa_svc.resolve_by_order(db, order["order_number"])
    automate_order_created(db, order, is_new)
    notify_order_webhook(order)
    if KUNDE_ID:
        try:
            integrations_svc.sync_order(db, order, kid=KUNDE_ID)
        except Exception as e:
            app.logger.warning(f"integrations sync: {e}")
    ghl_sync(order)
    if order.get("email"):
        send_confirmation_email(order)

    db.commit()

    return jsonify({
        "success": True,
        "orderNumber": order["order_number"],
        "loyalty": loyalty_info,
    })

@app.post("/api/admin/login")
def admin_login():
    ip = request.remote_addr or "unknown"
    key = f"login:{ip}"
    if rate_limit(key, max_calls=5, window_s=60):
        return jsonify({"error": "Zu viele Versuche. Bitte warte 1 Minute."}), 429
    if not ADMIN_PASSWORD and not auth_svc.get_user_by_username(get_db(), "admin"):
        return jsonify({"error": "ADMIN_PASSWORD nicht konfiguriert"}), 503
    data = request.get_json(force=True) or {}
    username = (data.get("username") or "admin").strip()
    password = data.get("password") or ""
    totp = data.get("totp") or data.get("code") or ""
    auth = auth_svc.authenticate(
        get_db(),
        username=username,
        password=password,
        role="kunde_admin",
        legacy_admin_password=ADMIN_PASSWORD or "",
    )
    if not auth.get("ok"):
        return jsonify({"success": False}), 401
    user = auth["user"]
    if user.get("totp_enabled") and not auth_svc.totp_verify(user, totp):
        return jsonify({"success": False, "needs_totp": True, "error": "2FA-Code fehlt oder falsch"}), 401
    token = create_session(kind="kunde_admin", user_id=int(user["id"]))
    resp = jsonify({
        "success": True,
        "token": token,
        "user": auth_svc.public_user(user),
    })
    return _set_auth_cookie(resp, "admin_session", token)


@app.post("/api/agency/login")
def agency_login():
    ip = request.remote_addr or "unknown"
    if rate_limit(f"agency-login:{ip}", max_calls=5, window_s=60):
        return jsonify({"error": "Zu viele Versuche. Bitte warte 1 Minute."}), 429
    data = request.get_json(force=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    totp = data.get("totp") or data.get("code") or ""
    expected = agency_secret_svc.resolve_agency_admin_password(AGENCY_ADMIN_PASSWORD)
    auth = auth_svc.authenticate(
        get_db(),
        username=username,
        password=password,
        role="agency",
        legacy_agency_password=expected or "",
    )
    if not auth.get("ok"):
        return jsonify({"success": False, "error": "Anmeldung fehlgeschlagen"}), 401
    user = auth["user"]
    if user.get("totp_enabled") and not auth_svc.totp_verify(user, totp):
        return jsonify({
            "success": False,
            "needs_totp": True,
            "error": "2FA-Code aus der Authenticator-App eingeben",
        }), 401
    token = create_session(kind="agency", user_id=int(user["id"]))
    resp = jsonify({
        "success": True,
        "token": token,
        "user": auth_svc.public_user(user),
    })
    return _set_auth_cookie(resp, "agency_session", token)


@app.post("/api/agency/logout")
def agency_logout():
    token = (
        request.headers.get("X-Agency-Token", "")
        or request.cookies.get("agency_session", "")
    )
    auth_svc.destroy_session(get_db(), token)
    resp = jsonify({"success": True})
    resp.set_cookie("agency_session", "", max_age=0, httponly=True, secure=True, samesite="Strict", path="/")
    return resp


@app.post("/api/auth/forgot")
def auth_forgot():
    ip = request.remote_addr or "unknown"
    if rate_limit(f"forgot:{ip}", max_calls=3, window_s=300):
        return jsonify({"error": "Zu viele Versuche. Bitte später erneut."}), 429
    data = request.get_json(force=True) or {}
    q = (data.get("username") or data.get("email") or "").strip()
    # Immer gleiche Antwort (kein User-Enumeration)
    generic = {
        "success": True,
        "message": "Wenn ein Konto existiert, wurde eine E-Mail mit Reset-Link gesendet.",
    }
    result = auth_svc.start_password_reset(get_db(), q)
    if not result.get("found"):
        return jsonify(generic)
    if not (result.get("email") or "").strip():
        return jsonify({
            "success": False,
            "error": "Für dieses Konto ist keine E-Mail hinterlegt. Passwort nur über Support/Server zurücksetzbar.",
        }), 400
    agency_base = (
        (os.getenv("AGENCY_PUBLIC_BASE_URL") or "").strip()
        or "https://digitalehandwerkskunst.de"
    ).rstrip("/")
    public_base = (os.getenv("PUBLIC_BASE_URL") or request.host_url or "").rstrip("/")
    # Agency-Reset immer auf Agency-Domain (PUBLIC_BASE_URL zeigt oft auf Kunden-Subdomain)
    if result.get("role") == "agency":
        base = agency_base
        link = f"{base}/agency?reset={result['token']}"
    else:
        base = public_base or agency_base
        link = f"{base}/admin?reset={result['token']}"
    try:
        import agency_mail as agency_mail_svc

        agency_mail_svc.send_html_email(
            to=result["email"],
            subject="Passwort zurücksetzen · Webschmiede",
            text=(
                f"Hallo {result['username']},\n\n"
                f"Passwort zurücksetzen (1 Stunde gültig):\n{link}\n\n"
                "Wenn du das nicht warst, ignoriere die Mail.\n"
            ),
            html=(
                f"<p>Hallo {result['username']},</p>"
                f"<p><a href=\"{link}\">Passwort zurücksetzen</a> "
                f"(1 Stunde gültig).</p>"
                f"<p>Wenn du das nicht warst, ignoriere die Mail.</p>"
            ),
        )
    except Exception as e:
        app.logger.warning("auth forgot mail: %s", e)
        return jsonify({"success": False, "error": "E-Mail konnte nicht gesendet werden. SMTP prüfen."}), 503
    return jsonify(generic)


@app.post("/api/auth/reset")
def auth_reset():
    ip = request.remote_addr or "unknown"
    if rate_limit(f"reset:{ip}", max_calls=5, window_s=300):
        return jsonify({"error": "Zu viele Versuche."}), 429
    data = request.get_json(force=True) or {}
    result = auth_svc.complete_password_reset(
        get_db(),
        data.get("token") or "",
        data.get("password") or data.get("new_password") or "",
    )
    if not result.get("ok"):
        err = result.get("error") or "invalid"
        msg = {
            "expired": "Link abgelaufen. Bitte neu anfordern.",
            "invalid_token": "Link ungültig.",
            "invalid": "Passwort mindestens 10 Zeichen.",
        }.get(err, "Reset fehlgeschlagen.")
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "username": result.get("username")})


@app.get("/api/agency/me")
@require_agency_admin
def agency_me():
    uid = getattr(g, "auth_user_id", None)
    user = auth_svc.get_user_by_id(get_db(), int(uid)) if uid else None
    return jsonify({"ok": True, "user": auth_svc.public_user(user)})


@app.post("/api/agency/2fa/setup")
@require_agency_admin
def agency_2fa_setup():
    uid = getattr(g, "auth_user_id", None)
    if not uid:
        return jsonify({"error": "Session ohne User. Neu anmelden."}), 400
    return jsonify(auth_svc.totp_provision(get_db(), int(uid)))


@app.post("/api/agency/2fa/confirm")
@require_agency_admin
def agency_2fa_confirm():
    uid = getattr(g, "auth_user_id", None)
    if not uid:
        return jsonify({"error": "Session ohne User."}), 400
    data = request.get_json(force=True) or {}
    result = auth_svc.totp_confirm(get_db(), int(uid), data.get("code") or data.get("totp") or "")
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@app.get("/api/admin/orders")
@require_admin
def admin_orders():
    db = get_db()
    s = _settings_map(db)
    wait_pickup = int(s.get("wait_pickup", "20") or 20)

    rows = db.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 200").fetchall()
    orders = []
    for r in rows:
        o = dict(r)
        o["items"] = json.loads(o.get("items") or "[]")
        orders.append(o)

    # Prioritäts-Sortierung: abgeschlossene/stornierte nach unten, Rest nach Dringlichkeit
    sorted_orders = prio_svc.sort_orders(orders, wait_pickup_minutes=wait_pickup)
    return jsonify(sorted_orders)

@app.post("/api/admin/orders/<order_number>/status")
@require_admin
def update_status(order_number):
    data     = request.get_json(force=True)
    new_status = data.get("status","")
    allowed  = ["neu","zubereitung","unterwegs","abholbereit","fertig","storniert"]
    if new_status not in allowed:
        return jsonify({"error": "Ungültiger Status"}), 400

    db = get_db()
    if new_status == "fertig":
        db.execute(
            "UPDATE orders SET status=?, completed_at=COALESCE(completed_at, datetime('now')) WHERE order_number=?",
            (new_status, order_number),
        )
    else:
        db.execute("UPDATE orders SET status=? WHERE order_number=?", (new_status, order_number))
    db.commit()

    row = db.execute("SELECT * FROM orders WHERE order_number=?", (order_number,)).fetchone()
    if row:
        order = dict(row)
        order["items"] = json.loads(order["items"] or "[]")
        cid = order.get("customer_account_id")
        if order.get("email"):
            send_status_email(order, new_status)
        automate_status_changed(db, order, new_status)
        # Analytics + Alerts
        if new_status == "storniert":
            ae_svc.track_order_cancelled(db, order, customer_id=cid)
        if new_status == "zubereitung":
            db.execute("UPDATE orders SET production_started_at=COALESCE(production_started_at, datetime('now')) WHERE order_number=?", (order_number,))
            db.commit()
            oa_svc.resolve_by_order(db, order_number, "unconfirmed_order")
        if new_status in ("fertig", "abholbereit"):
            # Pünktlichkeit bestimmen: War die Fertigstellung rechtzeitig?
            wz = order.get("wunschzeit") or ""
            on_time = True  # Default: als pünktlich werten
            ae_svc.track_order_ready(db, order, on_time=on_time)
            oa_svc.resolve_by_order(db, order_number)

    return jsonify({"success": True, "status": new_status})

@app.get("/api/admin/contacts")
@require_admin
def admin_contacts():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM contacts ORDER BY COALESCE(last_order_at, created_at) DESC LIMIT 300"
    ).fetchall()
    out = []
    for r in rows:
        c = dict(r)
        c["tags"] = json.loads(c.get("tags") or "[]")
        out.append(c)
    return jsonify(out)

@app.get("/api/admin/contacts/<phone>/orders")
@require_admin
def admin_contact_orders(phone):
    db = get_db()
    norm = normalize_phone(phone)
    rows = db.execute(
        """SELECT order_number, created_at, completed_at, total, status, delivery_type,
                  items, promo_applied, review_sent
           FROM orders
           WHERE phone=? OR phone=? OR phone=?
           ORDER BY created_at DESC LIMIT 30""",
        (phone, norm, phone.replace(" ", "")),
    ).fetchall()
    out = []
    for r in rows:
        o = dict(r)
        o["items"] = json.loads(o["items"] or "[]")
        out.append(o)
    return jsonify(out)

@app.post("/api/admin/contacts/<phone>/notes")
@require_admin
def admin_contact_notes(phone):
    data  = request.get_json(force=True)
    notes = (data.get("notes") or "")[:1000]
    db    = get_db()
    norm  = normalize_phone(phone)
    cur   = db.execute(
        "UPDATE contacts SET notes=? WHERE phone=? OR phone=?",
        (notes, phone, norm),
    )
    db.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Kontakt nicht gefunden"}), 404
    return jsonify({"success": True})

@app.post("/api/admin/followups/run")
@require_admin
def admin_run_followups():
    db = get_db()
    stats = run_followups(db)
    return jsonify({"success": True, **stats})

@app.post("/api/cron/followups")
def cron_followups():
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    stats = run_followups(db)
    return jsonify({"success": True, **stats})


@app.post("/api/cron/backup")
def cron_backup():
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    import shutil
    bk_dir = os.path.join(os.path.dirname(__file__), "..", "backups")
    os.makedirs(bk_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    dest = os.path.join(bk_dir, f"orders_{stamp}.db")
    shutil.copy2(DB_PATH, dest)
    return jsonify({"success": True, "file": os.path.basename(dest)})


@app.post("/api/cron/nightly-watchdog")
def cron_nightly_watchdog():
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    from nightly_watchdog import run_watchdog, send_status_email

    payload = request.get_json(silent=True) or {}
    auto_repair = bool(payload.get("auto_repair", True))
    integration_live = bool(payload.get("integration_live", datetime.datetime.now().hour >= 10))
    result = run_watchdog(auto_repair=auto_repair, integration_live=integration_live)
    if result.get("initial_failures") or result.get("actions") or not result.get("ok"):
        result["alert"] = send_status_email(result)
    return jsonify({"success": result["ok"], **result})


@app.post("/api/cron/sales-companion")
def cron_sales_companion():
    """Funnel-Reminders + optional Tagesstand. CRON_SECRET."""
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    if rate_limit("sales_companion_cron", 6, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    payload = request.get_json(silent=True) or {}
    db = get_db()
    try:
        reminders = sales_companion_svc.run_reminders(db)
        digest = None
        if str(payload.get("digest", "1")).lower() not in ("0", "false", "nein"):
            digest = sales_companion_svc.digest(db)
        return jsonify({"ok": True, "reminders": reminders, "digest": digest})
    finally:
        db.close()


@app.get("/api/admin/messages")
@require_admin
def admin_messages():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM message_log ORDER BY id DESC LIMIT 50"
    ).fetchall()
    return jsonify([dict(r) for r in rows])

# ── Jarvis Bot (Test-Webhook + WhatsApp-Vorbereitung) ────────────────────────
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from jarvis import bot as jarvis_bot

os.makedirs(JARVIS_UPLOAD_DIR, exist_ok=True)

@app.route("/uploads/menu/<path:filename>")
def serve_menu_upload(filename):
    safe = os.path.basename(filename)
    path = os.path.join(JARVIS_UPLOAD_DIR, safe)
    if not os.path.isfile(path):
        return jsonify({"error": "not found"}), 404
    from flask import send_file
    return send_file(path)

def _jarvis_auth() -> bool:
    secret = request.headers.get("X-Bot-Secret", "") or request.args.get("secret", "")
    return bool(JARVIS_BOT_SECRET) and secret == JARVIS_BOT_SECRET

def _whatsapp_download_media(media_id: str, access_token: str | None = None) -> tuple[bytes, str] | tuple[None, None]:
    token = (access_token or WHATSAPP_ACCESS_TOKEN or "").strip()
    if not token or not media_id:
        return None, None
    try:
        r1 = req.get(
            f"https://graph.facebook.com/v21.0/{media_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r1.raise_for_status()
        url = r1.json().get("url")
        if not url:
            return None, None
        r2 = req.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        r2.raise_for_status()
        ctype = r2.headers.get("Content-Type", "image/jpeg")
        ext = "jpg" if "jpeg" in ctype else "png" if "png" in ctype else "jpg"
        return r2.content, ext
    except Exception:
        return None, None


def _whatsapp_send_text(to_phone: str, body: str, creds: dict | None = None):
    if creds:
        result = messaging_svc.send_whatsapp_text(
            to_phone,
            body,
            access_token=creds.get("access_token"),
            phone_number_id=creds.get("phone_number_id"),
        )
    else:
        result = messaging_svc.send_whatsapp_text(to_phone, body)
    if not result.get("ok"):
        app.logger.warning(f"WhatsApp send: {result.get('error')}")
    return bool(result.get("ok"))

@app.get("/api/whatsapp/webhook")
def whatsapp_verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    expected = wa_webhook_svc.verify_token_configured()
    if not expected:
        app.logger.error("WhatsApp webhook: WHATSAPP_VERIFY_TOKEN fehlt")
        return jsonify({
            "error": "WHATSAPP_VERIFY_TOKEN ist nicht gesetzt. "
                     "Bitte in der Server-.env konfigurieren (kein Default)."
        }), 503
    if mode == "subscribe" and token == expected:
        return challenge or "", 200
    return "Forbidden", 403

@app.post("/api/whatsapp/webhook")
def whatsapp_incoming():
    raw = request.get_data()
    sig = request.headers.get("X-Hub-Signature-256")
    if not wa_webhook_svc.app_secret() and not wa_webhook_svc.insecure_no_secret_allowed():
        app.logger.error("WhatsApp webhook: META_APP_SECRET fehlt (fail-closed)")
        return jsonify({
            "error": "META_APP_SECRET ist nicht gesetzt. "
                     "Produktion: Secret setzen. "
                     "Nur Dev: WHATSAPP_WEBHOOK_INSECURE_NO_SECRET=1"
        }), 503
    if not wa_webhook_svc.verify_signature(raw, sig):
        app.logger.warning("WhatsApp webhook: Signatur ungültig oder fehlend")
        return "Forbidden", 403
    payload = request.get_json(force=True, silent=True) or {}
    db = get_db()
    nils_wa_ops_svc.ensure_sessions(db)
    replies = []
    for msg in wa_webhook_svc.parse_incoming_messages(payload):
        creds = wa_tenant_svc.resolve_by_phone_number_id(msg.get("phone_number_id") or "")
        client_id = (creds or {}).get("kunde_id") or None
        token = (creds or {}).get("access_token")
        image_bytes, ext = None, "jpg"
        if msg.get("image_id"):
            image_bytes, ext = _whatsapp_download_media(msg["image_id"], token)

        # Agency-Inbox: Owner → Nils Ops, Unbekannt → kurze Absage (kein Gastro-Jarvis)
        agency_inbox = nils_wa_ops_svc.is_agency_inbox(msg.get("phone_number_id") or "")
        if agency_inbox and not client_id:
            if nils_wa_ops_svc.is_owner(msg["phone"]):
                try:
                    ops = nils_wa_ops_svc.handle_owner_message(
                        db,
                        phone=msg["phone"],
                        text=msg.get("text") or "",
                        image_bytes=image_bytes,
                        image_ext=ext or "jpg",
                    )
                    reply = ops.get("reply") or ""
                    if reply:
                        _whatsapp_send_text(msg["phone"], reply, None)
                        replies.append({
                            "phone": msg["phone"],
                            "reply": reply[:200],
                            "kunde_id": "NILS_OPS",
                            "route": ops.get("route"),
                        })
                except Exception as e:
                    app.logger.exception("nils_whatsapp_ops")
                    _whatsapp_send_text(
                        msg["phone"],
                        f"Nils-Fehler: {str(e)[:160]}. Bitte im Cursor nachhaken.",
                        None,
                    )
            else:
                _whatsapp_send_text(msg["phone"], nils_wa_ops_svc.stranger_reply(), None)
                replies.append({
                    "phone": msg["phone"],
                    "reply": "stranger",
                    "kunde_id": "AGENCY",
                    "route": "reject",
                })
            continue

        result = jarvis_bot.handle_message(
            db,
            msg["phone"],
            msg.get("text", ""),
            client_id=client_id,
            image_bytes=image_bytes,
            image_ext=ext or "jpg",
            channel="whatsapp",
        )
        reply = result.get("reply", "")
        if reply:
            _whatsapp_send_text(msg["phone"], reply, creds)
            replies.append({
                "phone": msg["phone"],
                "reply": reply,
                "kunde_id": client_id or "agency",
            })
    db.commit()
    return jsonify({"success": True, "replies": replies})


@app.post("/api/whatsapp/send")
@require_agency_admin
def whatsapp_send_v1():
    """Multi-Tenant: Template oder Text an Empfänger (kunde_id wählt Credentials)."""
    if rate_limit("whatsapp_send_v1", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    kunde_id = (data.get("kunde_id") or data.get("client_id") or "").strip()
    to = (data.get("to") or data.get("recipient_phone") or "").strip()
    if not to:
        return jsonify({"ok": False, "error": "to fehlt"}), 400
    template = (data.get("template") or data.get("template_name") or "").strip()
    text = (data.get("text") or data.get("body") or "").strip()
    result = messaging_svc.send_whatsapp_for_kunde(
        kunde_id,
        to,
        text,
        template_name=template,
        language=(data.get("language") or data.get("language_code") or "de"),
        components=data.get("components"),
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status

@app.post("/api/jarvis/test")
def jarvis_test():
    if not _jarvis_auth():
        return jsonify({"error": "Unauthorized"}), 401
    if rate_limit("jarvis_test", 30, 60):
        return jsonify({"error": "Rate limit"}), 429
    data = request.get_json(force=True) or {}
    phone = (data.get("phone") or "+4900000000").strip()
    text = (data.get("text") or "").strip()
    client_id = (data.get("client_id") or "").strip() or None
    is_agency = request.headers.get("X-Agency") == "1" or data.get("agency") is True
    image_bytes = None
    image_ext = "jpg"
    if data.get("image_base64"):
        import base64
        raw = data["image_base64"]
        if "," in raw:
            raw = raw.split(",", 1)[1]
        image_bytes = base64.b64decode(raw)
        image_ext = data.get("image_ext") or "jpg"
    db = get_db()
    result = jarvis_bot.handle_message(
        db, phone, text, client_id=client_id,
        image_bytes=image_bytes, image_ext=image_ext,
        channel="test", is_agency=is_agency,
    )
    return jsonify(result)

@app.get("/api/admin/bot-log")
@require_admin
def admin_bot_log():
    db = get_db()
    rows = db.execute("SELECT * FROM bot_log ORDER BY id DESC LIMIT 80").fetchall()
    out = []
    for r in rows:
        row = dict(r)
        try:
            row["meta"] = json.loads(row.get("meta") or "{}")
        except json.JSONDecodeError:
            row["meta"] = {}
        out.append(row)
    return jsonify(out)

# ── Webschmiede: Seminare & 1:1-Buchung ───────────────────────────────────────

def _notify_seminar_webhook(payload: dict):
    if not N8N_SEMINAR_WEBHOOK:
        return
    try:
        req.post(N8N_SEMINAR_WEBHOOK, json=payload, timeout=5)
    except Exception as e:
        app.logger.warning(f"seminar webhook: {e}")

def _send_seminar_confirmation(reg: dict, sem: dict):
    try:
        from agency_mail import send_html_email
        from email_templates import email_shell
        subject = f"Anmeldung bestätigt: {sem['title']}"
        body = f"""
        <p>Hallo {reg['name']},</p>
        <p>Ihre Anmeldung ist bestätigt:</p>
        <p style="background:#faf9f7;border:1px solid #eeeeee;border-radius:10px;padding:16px;line-height:1.6;">
          <strong>{sem['title']}</strong><br>
          {sem['event_date']} · {sem.get('event_time', '')}<br>
          {sem.get('location', '')}
        </p>
        <p>Bei Fragen antworten Sie einfach auf diese E-Mail.</p>
        """
        html = email_shell(
            hero_title="Seminar-Anmeldung bestätigt",
            hero_subtitle=sem["title"],
            preheader=f"{sem['title']} am {sem['event_date']}",
            body_html=body,
        )
        send_html_email(
            to=reg["email"],
            subject=subject,
            html=html,
            text=f"Anmeldung bestätigt: {sem['title']} am {sem['event_date']} · {sem.get('location', '')}",
        )
    except Exception as e:
        app.logger.warning(f"Seminar-Mail: {e}")

@app.get("/api/seminars")
def seminars_public_list():
    db = get_db()
    cal = agency_secret_svc.resolve_calcom_config(CALCOM_URL)
    return jsonify({"seminars": seminar_svc.list_public(db), "calcom_url": cal["url"] or CALCOM_URL})

@app.get("/api/seminars/booking")
def seminars_booking_info():
    cal = agency_secret_svc.resolve_calcom_config(CALCOM_URL)
    return jsonify({
        "calcom_url": cal["url"] or CALCOM_URL,
        "api_configured": bool(cal.get("api_key")),
        "hint": "1:1-Erstgespräch über Cal.com · Seminare über /seminare",
    })

@app.post("/api/seminars/<int:seminar_id>/register")
def seminars_register(seminar_id: int):
    ip = request.remote_addr or "unknown"
    if rate_limit(f"seminar-reg:{ip}", max_calls=10, window_s=3600):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(force=True) or {}
    db = get_db()
    result, err = seminar_svc.register(db, seminar_id, data)
    if err:
        return jsonify({"error": err}), 400
    db.commit()
    sem = result["seminar"]
    _send_seminar_confirmation(result, sem)
    _notify_seminar_webhook({
        "type": "seminar_registration",
        "seminar_id": seminar_id,
        "name": result["name"],
        "email": result["email"],
        "title": sem["title"],
        "event_date": sem["event_date"],
    })
    return jsonify({"success": True, "message": "Anmeldung bestätigt! Du erhältst eine E-Mail.", "seminar": sem})

@app.get("/api/agency/seminars")
@require_agency_admin
def agency_seminars_list():
    db = get_db()
    return jsonify(seminar_svc.list_admin(db))

@app.post("/api/agency/seminars")
@require_agency_admin
def agency_seminars_create():
    data = request.get_json(force=True) or {}
    if not data.get("title") or not data.get("event_date"):
        return jsonify({"error": "Titel und Datum erforderlich"}), 400
    db = get_db()
    sid = seminar_svc.create_seminar(db, data)
    db.commit()
    return jsonify({"success": True, "id": sid})

@app.put("/api/agency/seminars/<int:seminar_id>")
@require_agency_admin
def agency_seminars_update(seminar_id: int):
    data = request.get_json(force=True) or {}
    db = get_db()
    if not seminar_svc.update_seminar(db, seminar_id, data):
        return jsonify({"error": "Nicht gefunden"}), 404
    db.commit()
    return jsonify({"success": True})

@app.get("/api/agency/seminars/<int:seminar_id>/registrations")
@require_agency_admin
def agency_seminar_regs(seminar_id: int):
    db = get_db()
    return jsonify(seminar_svc.list_registrations(db, seminar_id))

@app.delete("/api/agency/registrations/<int:reg_id>")
@require_agency_admin
def agency_reg_cancel(reg_id: int):
    db = get_db()
    seminar_svc.cancel_registration(db, reg_id)
    db.commit()
    return jsonify({"success": True})


@app.get("/api/agency/secrets")
@require_agency_admin
def agency_secrets_get():
    return jsonify(agency_secret_svc.get_status())


@app.put("/api/agency/secrets")
@require_agency_admin
def agency_secrets_put():
    if rate_limit("agency_secrets_put", 10, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    updates = {k: v for k, v in data.items() if isinstance(v, str)}
    try:
        result = agency_secret_svc.update_secrets(updates)
    except Exception as exc:
        app.logger.exception("agency_secrets_put")
        return jsonify({"ok": False, "error": f"Server-Fehler beim Speichern: {exc}"[:200]}), 500
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@app.get("/api/agency/integrations/health")
@require_agency_admin
def agency_integrations_health():
    live = request.args.get("live", "").lower() in ("1", "true", "yes")
    return jsonify(agency_secret_svc.check_integrations_health(live=live))


@app.post("/api/agency/secrets/test/<test_id>")
@require_agency_admin
def agency_secrets_test(test_id: str):
    if test_id == "google_places":
        return jsonify(agency_secret_svc.test_google_places())
    if test_id == "smtp":
        data = request.get_json(silent=True) or {}
        return jsonify(agency_secret_svc.test_smtp(data.get("to")))
    if test_id == "stripe":
        return jsonify(agency_secret_svc.test_stripe())
    if test_id == "cloudflare":
        return jsonify(agency_secret_svc.test_cloudflare())
    if test_id == "hetzner":
        return jsonify(agency_secret_svc.test_hetzner())
    if test_id == "sms":
        return jsonify(agency_secret_svc.test_sms())
    if test_id == "whatsapp":
        data = request.get_json(silent=True) or {}
        if data.get("send"):
            # echte Test-Nachricht (braucht 24h-Fenster oder Template)
            to = data.get("to")
            return jsonify(messaging_svc.test_whatsapp(to))
        return jsonify(agency_secret_svc.test_whatsapp_meta())
    if test_id == "telegram":
        return jsonify(agency_secret_svc.test_telegram())
    if test_id == "docuseal":
        return jsonify(agency_secret_svc.test_docuseal())
    if test_id == "ionos":
        return jsonify(agency_secret_svc.test_ionos())
    if test_id == "inwx":
        return jsonify(agency_secret_svc.test_inwx())
    return jsonify({"ok": False, "error": "Unbekannter Test"}), 400


@app.get("/api/agency/messaging/status")
@require_agency_admin
def agency_messaging_status():
    return jsonify(messaging_svc.status())


@app.post("/api/agency/messaging/send")
@require_agency_admin
def agency_messaging_send():
    """Test/Outbound: SMS, WhatsApp-Text oder Template."""
    if rate_limit("agency_messaging_send", 20, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    to = (data.get("to") or "").strip()
    text = (data.get("text") or "").strip()
    channel = (data.get("channel") or "auto").strip().lower()
    template = (data.get("template") or "").strip()
    if not to:
        return jsonify({"ok": False, "error": "to fehlt"}), 400
    db = get_db()
    if template and channel in ("whatsapp", "auto", "wa"):
        kid = (data.get("kunde_id") or data.get("client_id") or "").strip()
        result = messaging_svc.send_whatsapp_for_kunde(
            kid,
            to,
            text,
            template_name=template,
            language=(data.get("language") or "de"),
            components=data.get("components"),
        )
    elif channel in ("sms",):
        result = messaging_svc.send_sms(to, text or "Webschmiede")
    elif channel in ("whatsapp", "wa"):
        kid = (data.get("kunde_id") or data.get("client_id") or "").strip()
        result = messaging_svc.send_whatsapp_for_kunde(kid, to, text or "Webschmiede")
    else:
        result = messaging_svc.send_notify(to, text or "Webschmiede", prefer=channel)
    try:
        log_message(
            db,
            messaging_svc.normalize_phone(to),
            result.get("channel") or channel,
            template or "agency_send",
            text or template,
            "sent" if result.get("ok") else f"failed:{result.get('error', '')[:80]}",
        )
        db.commit()
    except Exception:
        pass
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/onboarding/<kid>")
def onboarding_data(kid: str):
    if rate_limit(f"onboarding_{kid.lower()}", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = onboarding_svc.build_onboarding(kid)
    if not data:
        return jsonify({"error": "Kunde nicht gefunden"}), 404
    return jsonify(data)


@app.get("/api/onboarding/<kid>/domains")
def onboarding_domains(kid: str):
    if rate_limit(f"onboarding_domains_{kid.lower()}", 20, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = domain_onboarding_svc.list_options(kid)
    if not data.get("ok"):
        return jsonify(data), 404
    return jsonify(data)


@app.post("/api/onboarding/<kid>/domains/check")
def onboarding_domain_check(kid: str):
    if rate_limit(f"onboarding_domain_check_{kid.lower()}", 12, 60):
        return jsonify({"error": "Zu viele Anfragen. Bitte kurz warten."}), 429
    body = request.get_json(silent=True) or {}
    domain = (body.get("domain") or "").strip()
    if not domain:
        return jsonify({"ok": False, "error": "Domain fehlt"}), 400
    result = domain_onboarding_svc.check_wish(kid, domain)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/onboarding/<kid>/domains/select")
def onboarding_domain_select(kid: str):
    if rate_limit(f"onboarding_domain_select_{kid.lower()}", 6, 60):
        return jsonify({"error": "Zu viele Anfragen. Bitte kurz warten."}), 429
    body = request.get_json(silent=True) or {}
    domain = (body.get("domain") or "").strip()
    if not domain:
        return jsonify({"ok": False, "error": "Domain fehlt"}), 400
    result = domain_onboarding_svc.select_domain(kid, domain)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/onboarding/<kid>/google")
def onboarding_google_save(kid: str):
    if rate_limit(f"onboarding_google_{kid.lower()}", 10, 60):
        return jsonify({"error": "Zu viele Anfragen. Bitte kurz warten."}), 429
    body = request.get_json(silent=True) or {}
    result = google_onboarding_svc.save_google(kid, body)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/onboarding/<kid>/whatsapp/config")
def onboarding_whatsapp_config(kid: str):
    if rate_limit(f"onboarding_wa_cfg_{kid.lower()}", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    return jsonify(wa_embedded_svc.embedded_config(kid.upper()))


@app.post("/api/onboarding/<kid>/whatsapp/complete")
def onboarding_whatsapp_complete(kid: str):
    if rate_limit(f"onboarding_wa_complete_{kid.lower()}", 8, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    body = request.get_json(silent=True) or {}
    result = wa_embedded_svc.complete_embedded_signup(
        kid.upper(),
        code=(body.get("code") or "").strip(),
        phone_number_id=(body.get("phone_number_id") or body.get("phoneNumberId") or "").strip(),
        waba_id=(body.get("waba_id") or body.get("wabaId") or "").strip(),
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/agency/packages")
@require_agency_admin
def agency_packages_list():
    return jsonify({"packages": stripe_billing_svc.list_packages(), "stripe_ok": stripe_billing_svc.stripe_configured()})


@app.get("/api/agency/kalkulator")
@require_agency_admin
def agency_kalkulator_catalog():
    """Interne B2B-Preisliste (Bausteine, Firmen-Faktoren, Laufzeit) – nicht öffentlich."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "kalkulator-preise.json")
    try:
        with open(path, encoding="utf-8") as f:
            return jsonify(json.load(f))
    except OSError:
        return jsonify({"error": "Kalkulator-Preise nicht gefunden"}), 404


@app.get("/api/angebote")
def angebote_catalog():
    """Öffentlicher Branchen-Katalog · Preise werden auf der Website nicht gerendert."""
    path = os.path.join(os.path.dirname(__file__), "..", "static", "angebote.json")
    try:
        with open(path, encoding="utf-8") as f:
            return jsonify(json.load(f))
    except OSError:
        return jsonify({"error": "Katalog nicht gefunden"}), 404


@app.get("/api/agency/kunden")
@require_agency_admin
def agency_kunden_list():
    return jsonify({"kunden": agency_cockpit_svc.list_kunden_summary()})


@app.get("/api/agency/kunden/<kid>")
@require_agency_admin
def agency_kunde_detail(kid: str):
    data = agency_cockpit_svc.get_kunde_detail(kid.upper())
    if not data:
        return jsonify({"error": "Kunde nicht gefunden"}), 404
    return jsonify(data)


@app.post("/api/agency/kunden")
@require_agency_admin
def agency_kunde_create():
    if rate_limit("agency_kunde_create", 10, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(agency_cockpit_svc.create_kunde(data))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.patch("/api/agency/kunden/<kid>")
@require_agency_admin
def agency_kunde_update(kid: str):
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(agency_cockpit_svc.update_kunde(kid.upper(), data))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.patch("/api/agency/kunden/<kid>/channels")
@require_agency_admin
def agency_kunde_channels(kid: str):
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(agency_cockpit_svc.update_channels(kid.upper(), data))
    except ValueError as e:
        msg = str(e)
        code = 404 if "nicht gefunden" in msg.lower() else 400
        return jsonify({"error": msg}), code


@app.post("/api/agency/kunden/<kid>/send-offer")
@require_agency_admin
def agency_kunde_send_offer(kid: str):
    if rate_limit("agency_send_offer", 15, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(agency_cockpit_svc.send_offer(
            kid.upper(),
            package_id=data.get("package") or "pro",
            note=data.get("note") or "",
            email=data.get("email"),
        ))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500


@app.post("/api/agency/kunden/<kid>/send-onboarding")
@require_agency_admin
def agency_kunde_send_onboarding(kid: str):
    if rate_limit("agency_send_onboarding", 15, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(agency_cockpit_svc.send_onboarding(kid.upper(), email=data.get("email")))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500


@app.get("/api/agency/kunden/next-id")
@require_agency_admin
def agency_kunde_next_id():
    branche = (request.args.get("branche") or "").strip()
    prefix = (request.args.get("prefix") or "").upper().strip()
    if not prefix:
        prefix = agency_cockpit_svc.prefix_for_branche(branche) if branche else "SHY"
    return jsonify({
        "id": agency_cockpit_svc.suggest_next_id(prefix),
        "prefix": prefix,
        "branche": branche or None,
    })


@app.get("/api/agency/kunden/id-prefixes")
@require_agency_admin
def agency_kunde_id_prefixes():
    return jsonify({"prefixes": agency_cockpit_svc.list_id_prefixes()})


@app.get("/api/agency/automations")
@require_agency_admin
def agency_automations_global():
    return jsonify(agency_cockpit_svc.get_global_automations())


@app.get("/api/agency/ops/overview")
@require_agency_admin
def agency_ops_overview():
    db = get_db()
    return jsonify(agency_ops_svc.get_agency_overview(db))


@app.get("/api/agency/ops/kunden/<kid>")
@require_agency_admin
def agency_ops_kunde(kid: str):
    return jsonify(agency_ops_svc.get_client_health(kid.upper()))


@app.get("/api/agency/knowledge/<kid>")
@require_agency_admin
def agency_knowledge(kid: str):
    from integrations import load_kunde_json
    from jarvis.knowledge import resolve_for_kid

    k = load_kunde_json(kid.upper())
    if not k:
        return jsonify({"error": "Kunde nicht gefunden"}), 404
    return jsonify(resolve_for_kid(k))


@app.patch("/api/agency/kunden/<kid>/automations/<auto_id>")
@require_agency_admin
def agency_kunde_automation(kid: str, auto_id: str):
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(agency_cockpit_svc.update_client_automation(
            kid.upper(), auto_id, requested=bool(data.get("requested", True)),
        ))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.post("/api/agency/kunden/<kid>/setup-subdomain")
@require_agency_admin
def agency_kunde_setup_subdomain(kid: str):
    if rate_limit("agency_subdomain", 5, 300):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(agency_cockpit_svc.run_subdomain_setup(kid.upper(), ssl=bool(data.get("ssl"))))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500


@app.post("/api/agency/kunden/<kid>/prepare-site")
@require_agency_admin
def agency_kunde_prepare_site(kid: str):
    if rate_limit("agency_prepare", 10, 300):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    try:
        return jsonify(agency_cockpit_svc.run_prepare_site(kid.upper()))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500


@app.get("/api/agency/chat/history")
@require_agency_admin
def agency_chat_history():
    kid = (request.args.get("kunde_id") or "").upper() or None
    db = get_db()
    return jsonify({"messages": agency_chat_svc.get_history(db, kid)})


@app.post("/api/agency/chat")
@require_agency_admin
def agency_chat():
    if rate_limit("agency_chat", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message and not data.get("confirm"):
        return jsonify({"error": "message fehlt"}), 400
    kid = (data.get("kunde_id") or "").upper() or None
    pending = data.get("pending")
    db = get_db()
    try:
        if message:
            agency_chat_svc.log_message(db, kunde_id=kid, role="user", body=message)
        result = agency_chat_svc.handle_chat(
            message or "ja",
            kunde_id=kid,
            confirm=bool(data.get("confirm")),
            pending=pending,
        )
        agency_chat_svc.log_message(
            db, kunde_id=kid, role="assistant", body=result.get("reply", ""),
            meta={"needs_confirm": result.get("needs_confirm"), "pending": result.get("pending")},
        )
        db.commit()
        return jsonify(result)
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)[:200]}), 500


@app.post("/api/agency/router")
def agency_router():
    """Intent-Router für Cursor/n8n. Auth + Tenant + PII-Redaktion/Audit."""
    if rate_limit("agency_router", 60, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    cron_ok = bool(CRON_SECRET and secret == CRON_SECRET)
    pw = request.headers.get("X-Agency-Password", "") or request.headers.get("X-Admin-Password", "")
    expected = agency_secret_svc.resolve_agency_admin_password(AGENCY_ADMIN_PASSWORD)
    agency_ok = bool(expected and pw == expected)
    if not cron_ok and not agency_ok:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    if isinstance(data.get("body"), dict):
        data = {**data, **data["body"]}
    message = (data.get("message") or data.get("text") or data.get("payload") or "").strip()
    force = (data.get("force_agent") or "").strip() or None
    tenant = (
        data.get("kunde_id")
        or data.get("tenant_id")
        or data.get("tenant")
        or request.headers.get("X-Tenant-Id")
        or "AGENCY"
    )
    # intern: Klartext fuer Klassifikation; Response/Audit redigiert
    redact = str(data.get("redact", "1")).lower() not in ("0", "false", "nein", "off")
    result = agency_router_svc.classify(
        message,
        source="n8n" if cron_ok and not agency_ok else "api",
        force_agent=force,
        tenant_id=str(tenant),
        redact=redact,
    )
    result["playbook"] = agency_router_svc.cursor_playbook(result)
    # Audit nur redigiert
    try:
        db = get_db()
        audit = agency_router_sec.write_audit(
            db,
            tenant_id=result.get("tenant_id") or "AGENCY",
            source=result.get("source") or "api",
            message=message,
            agents=list(result.get("mitarbeiter") or []),
            meta={
                "prioritaet": result.get("prioritaet"),
                "llm_used": result.get("llm_used"),
                "llm_reason": result.get("llm_reason"),
            },
        )
        result["audit_id"] = audit.get("id")
        result["audit_fingerprint"] = audit.get("fingerprint")
    except Exception as e:
        result["audit_error"] = str(e)[:120]
    code = 200 if result.get("ok") else 400
    return jsonify(result), code


@app.post("/api/agency/brain")
def agency_brain():
    """WF1 scharf: Router + automatischer Dispatch an Stefan/Scout/Nils/…. Kein Auto-Send."""
    if rate_limit("agency_brain", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    if isinstance(data.get("body"), dict):
        data = {**data, **data["body"]}
    message = (data.get("message") or data.get("text") or data.get("payload") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": "message fehlt"}), 400
    force = (data.get("force_agent") or "").strip() or None
    tenant = (
        data.get("kunde_id")
        or data.get("tenant_id")
        or data.get("tenant")
        or request.headers.get("X-Tenant-Id")
        or "AGENCY"
    )
    dispatch = str(data.get("dispatch", "1")).lower() not in ("0", "false", "nein", "off")
    include_commander = str(data.get("commander", "0")).lower() in ("1", "true", "ja", "yes")
    try:
        max_agents = int(data.get("max_agents") or 4)
    except ValueError:
        max_agents = 4
    secret = request.headers.get("X-Cron-Secret", "") or ""
    cron_ok = bool(CRON_SECRET and secret == CRON_SECRET)
    result = agency_brain_svc.process(
        message,
        source="n8n" if cron_ok else "api",
        force_agent=force,
        tenant_id=str(tenant),
        dispatch=dispatch,
        include_commander=include_commander,
        max_agents=max_agents,
    )
    # Audit wie Router
    try:
        db = get_db()
        audit = agency_router_sec.write_audit(
            db,
            tenant_id=result.get("route", {}).get("tenant_id") or "AGENCY",
            source="brain",
            message=message,
            agents=list(result.get("agents") or []),
            meta={"dispatched": dispatch, "sharp": result.get("sharp")},
        )
        result["audit_id"] = audit.get("id")
    except Exception as e:
        result["audit_error"] = str(e)[:120]
    return jsonify(result), (200 if result.get("ok") or result.get("sharp") else 400)


@app.get("/api/agency/router/security")
def agency_router_security_status():
    """Read-only Security-Status Router WF1 + Dual-Server Topology."""
    status = agency_router_sec.security_status()
    status["dual"] = dual_infra_svc.topology()
    status["router_target"] = dual_infra_svc.TOPOLOGY["router"]
    return jsonify(status)


@app.get("/api/nils/dual-status")
@require_agency_admin
def nils_dual_status():
    """Nils WF9: Health web+auto (CX43 Nuernberg). Optional SSH zu beiden Hosts."""
    if rate_limit("nils_dual_status", 20, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    use_ssh = str(request.args.get("ssh", "1")).lower() not in ("0", "false", "nein")
    data = dual_infra_svc.dual_status(use_ssh=use_ssh)
    data["markdown"] = dual_infra_svc.markdown_status(data)
    return jsonify(data)


@app.get("/api/nils/guardian")
def nils_guardian_status():
    """Ops-Guardian: letzter Lauf / Scorecard. Kein Auto-Send an Kunden."""
    if rate_limit("nils_guardian", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = ops_guardian_svc.status()
    return jsonify(data)


@app.post("/api/nils/guardian/run")
def nils_guardian_run():
    """Ops-Guardian jetzt ausführen (Safe-Fixes + optional Mail)."""
    if rate_limit("nils_guardian_run", 10, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    repair = str(data.get("repair", "1")).lower() not in ("0", "false", "nein")
    mail = str(data.get("mail", "0")).lower() in ("1", "true", "ja", "yes")
    force_mail = str(data.get("force_mail", "0")).lower() in ("1", "true", "ja", "yes")
    result = ops_guardian_svc.run(repair=repair, mail=mail, force_mail=force_mail)
    slim = {k: v for k, v in result.items() if k != "markdown"}
    slim["markdown_bytes"] = len(result.get("markdown") or "")
    return jsonify(slim)


@app.get("/api/agency/router/schema")
def agency_router_schema():
    """JSON-Schema für n8n Structured Output."""
    return jsonify(agency_router_svc.SCHEMA)


@app.get("/api/agency/workflows")
def agency_workflows_registry():
    """Kern-Workflow-Register inkl. Radar (ohne Auth – Read-only Status)."""
    return jsonify(agency_router_svc.registry())


@app.get("/api/agency/radar/status")
def agency_radar_status():
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(agency_radar_svc.status())


@app.post("/api/agency/radar/scan")
def agency_radar_scan():
    """Wochen-Scan: Report schreiben. Kein Auto-Install."""
    if rate_limit("agency_radar_scan", 10, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    live = str(data.get("live", "1")).lower() not in ("0", "false", "nein", "off")
    day = (data.get("date") or "").strip() or None
    result = agency_radar_svc.build_report(live=live, day=day)
    # Response ohne volles Markdown wenn zu groß
    slim = {k: v for k, v in result.items() if k != "markdown"}
    slim["markdown_bytes"] = len(result.get("markdown") or "")
    return jsonify(slim)


@app.get("/api/agency/radar/queue")
def agency_radar_queue_get():
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(agency_radar_svc.load_queue())


@app.post("/api/agency/radar/queue")
def agency_radar_queue_post():
    if rate_limit("agency_radar_queue", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    return jsonify(
        agency_radar_svc.queue_install(
            (data.get("name") or "").strip(),
            reason=(data.get("reason") or "").strip(),
            category=(data.get("category") or "tool").strip(),
            cost=(data.get("cost") or "unbekannt").strip(),
            url=(data.get("url") or "").strip(),
        )
    )


@app.post("/api/agency/radar/queue/<item_id>/decide")
def agency_radar_queue_decide(item_id: str):
    """Christian: approve/reject. Install macht Nils danach manuell."""
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    approve = str(data.get("approve", "1")).lower() not in ("0", "false", "nein", "reject", "rejected")
    if str(data.get("decision") or "").lower() in ("reject", "rejected", "nein", "no"):
        approve = False
    return jsonify(agency_radar_svc.approve_install(item_id, approve=approve))


@app.post("/api/agency/shipcheck")
def agency_shipcheck():
    """Links/Dashboards smoke-testen bevor sie an Christian gehen. Kein Auto-Send."""
    if rate_limit("agency_shipcheck", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    if isinstance(data.get("body"), dict):
        data = {**data, **data["body"]}
    dashboard = (data.get("dashboard") or "").strip()
    if dashboard:
        result = agency_shipcheck_svc.check_dashboard(dashboard)
    else:
        urls = data.get("urls")
        if isinstance(urls, str):
            urls = [u.strip() for u in urls.split() if u.strip()]
        text = (data.get("text") or data.get("message") or data.get("url") or "").strip()
        if isinstance(urls, list) and urls:
            result = agency_shipcheck_svc.check_text(text, urls=[str(u) for u in urls])
        else:
            result = agency_shipcheck_svc.gate_before_share(text)
    slim = {k: v for k, v in result.items() if k != "markdown"}
    slim["markdown_bytes"] = len(result.get("markdown") or "")
    code = 200 if result.get("ship") or result.get("skipped") else 422
    return jsonify(slim), code


@app.post("/api/agency/commander/fulfillment")
def agency_commander_fulfillment():
    """Solo-Fulfillment-Pack: Stefan + Anwalt + Briefings. Kein Auto-Send. Christian schliesst."""
    if rate_limit("agency_commander_fulfill", 20, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    if isinstance(data.get("body"), dict):
        data = {**data, **data["body"]}
    result = agency_commander_svc.fulfillment_pack(
        firma=(data.get("firma") or data.get("company") or "").strip(),
        brief=(data.get("brief") or data.get("message") or data.get("text") or "").strip(),
        budget=str(data.get("budget") or data.get("ticket") or data.get("preis") or "5000"),
        kontakt=(data.get("kontakt") or data.get("contact") or "").strip(),
        zero_retention=bool(data.get("zero_retention", True)),
    )
    return jsonify(result)


@app.post("/api/agency/commander/capacity")
def agency_commander_capacity():
    """Ehrliche Solo-Kapazitaet (keine Umsatzgarantie)."""
    if rate_limit("agency_commander_capacity", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    if isinstance(data.get("body"), dict):
        data = {**data, **data["body"]}
    result = agency_commander_svc.capacity_plan(
        ticket=float(data.get("ticket") or data.get("budget") or 5000),
        target_month=float(data.get("target") or data.get("target_month") or 30000),
        hours_week_sales=float(data.get("hours_week") or data.get("hours_week_sales") or 10),
        parallel_active=int(data.get("parallel") or 3),
    )
    return jsonify(result)


@app.get("/api/agency/commander/briefing")
def agency_commander_briefing():
    """Tagesbriefing: Scout, Freigaben, persoenliche Gates."""
    if rate_limit("agency_commander_brief", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    limit = int(request.args.get("limit") or 5)
    ticket = request.args.get("ticket") or "5000"
    return jsonify(agency_commander_svc.daily_briefing(scout_limit=limit, ticket=ticket))


@app.post("/api/agency/stefan/plan")
def agency_stefan_plan():
    """Stefan WF2: B2B-Schlachtplan aus Rohbriefing. Auth: Cron oder Agency-Passwort."""
    if rate_limit("agency_stefan_plan", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    cron_ok = bool(CRON_SECRET and secret == CRON_SECRET)
    pw = request.headers.get("X-Agency-Password", "") or request.headers.get("X-Admin-Password", "")
    expected = agency_secret_svc.resolve_agency_admin_password(AGENCY_ADMIN_PASSWORD)
    agency_ok = bool(expected and pw == expected)
    if not cron_ok and not agency_ok:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    brief = (data.get("brief") or data.get("message") or data.get("text") or "").strip()
    if not brief and isinstance(data.get("body"), dict):
        b = data["body"]
        brief = (b.get("brief") or b.get("message") or b.get("text") or "").strip()
    firma = (data.get("firma") or data.get("company") or "").strip()
    mode = (data.get("mode") or "").strip().lower()
    if mode in ("filter", "guru", "reality") or data.get("filter"):
        result = agency_stefan_svc.filter_idea(brief)
    elif mode in ("growth", "funnel", "wachstum"):
        result = agency_stefan_svc.growth_plan(
            brief,
            niche=(data.get("niche") or data.get("branche") or "").strip(),
            ticket=str(data.get("ticket") or data.get("budget") or ""),
            offer=(data.get("offer") or data.get("angebot") or "").strip(),
        )
    else:
        result = agency_stefan_svc.plan_project(brief, firma=firma)
    code = 200 if result.get("ok") else 400
    return jsonify(result), code


@app.post("/api/agency/stefan/growth")
def agency_stefan_growth():
    """Stefan als Wachstums-/Funnel-Stratege (Landing, Sequenz, Schnitt). Kein Auto-Send."""
    if rate_limit("agency_stefan_growth", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    if isinstance(data.get("body"), dict):
        data = {**data, **data["body"]}
    result = agency_stefan_svc.growth_plan(
        (data.get("brief") or data.get("message") or data.get("text") or "").strip(),
        niche=(data.get("niche") or data.get("branche") or "").strip(),
        ticket=str(data.get("ticket") or data.get("budget") or "5000"),
        offer=(data.get("offer") or data.get("angebot") or "").strip(),
    )
    return jsonify(result)


@app.post("/api/agency/stefan/filter")
def agency_stefan_filter():
    """Stefan Guru-Filter / Reality-Check fuer Tool-Ideen."""
    if rate_limit("agency_stefan_filter", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    cron_ok = bool(CRON_SECRET and secret == CRON_SECRET)
    pw = request.headers.get("X-Agency-Password", "") or request.headers.get("X-Admin-Password", "")
    expected = agency_secret_svc.resolve_agency_admin_password(AGENCY_ADMIN_PASSWORD)
    agency_ok = bool(expected and pw == expected)
    if not cron_ok and not agency_ok:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    idea = (data.get("idea") or data.get("brief") or data.get("message") or data.get("text") or "").strip()
    if not idea and isinstance(data.get("body"), dict):
        b = data["body"]
        idea = (b.get("idea") or b.get("message") or b.get("text") or "").strip()
    result = agency_stefan_svc.filter_idea(idea)
    return jsonify(result), (200 if result.get("ok") else 400)


def _agency_auth_ok() -> bool:
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if CRON_SECRET and secret == CRON_SECRET:
        return True
    pw = request.headers.get("X-Agency-Password", "") or request.headers.get("X-Admin-Password", "")
    expected = agency_secret_svc.resolve_agency_admin_password(AGENCY_ADMIN_PASSWORD)
    return bool(expected and pw == expected)


def _anwalt_payload() -> dict:
    data = request.get_json(silent=True) or {}
    if isinstance(data.get("body"), dict):
        data = {**data, **data["body"]}
    return {
        "firma": (data.get("firma") or data.get("company") or "").strip(),
        "kontakt": (data.get("kontakt") or data.get("contact") or "").strip(),
        "leistungen": (data.get("leistungen") or data.get("scope") or "").strip(),
        "budget": (data.get("budget") or data.get("preis") or "").strip(),
        "zero_retention": bool(data.get("zero_retention", True)),
        "brief": (data.get("brief") or data.get("message") or data.get("text") or "").strip(),
        "_raw": data,
    }


@app.post("/api/agency/anwalt/enterprise")
def agency_anwalt_enterprise():
    """Anwalt WF10: Enterprise-Paket (Auftrag/AVV-Felder, Vendor-Assessment). Keine Auto-Mails."""
    if rate_limit("agency_anwalt_enterprise", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    p = _anwalt_payload()
    result = agency_anwalt_svc.enterprise_pack(
        firma=p["firma"],
        kontakt=p["kontakt"],
        leistungen=p["leistungen"],
        budget=p["budget"],
        zero_retention=p["zero_retention"],
        brief=p["brief"],
    )
    return jsonify(result)


@app.post("/api/agency/anwalt/pipeline")
def agency_anwalt_pipeline():
    """3-Stufen: Entwurf -> AVV -> Endkontrolle. Deterministisch, kein Auto-Send, kein LLM-Zwang."""
    if rate_limit("agency_anwalt_pipeline", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    p = _anwalt_payload()
    result = agency_anwalt_svc.pipeline_3_stufen(
        firma=p["firma"],
        kontakt=p["kontakt"],
        leistungen=p["leistungen"],
        budget=p["budget"],
        zero_retention=p["zero_retention"],
        brief=p["brief"],
    )
    return jsonify(result)


@app.post("/api/agency/anwalt/stage/<int:stage>")
def agency_anwalt_stage(stage: int):
    """Einzelstufe 1|2|3 fuer n8n-Kette. Stufe 2/3 koennen document aus Body uebernehmen."""
    if rate_limit("agency_anwalt_stage", 60, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    p = _anwalt_payload()
    raw = p["_raw"]
    doc = (raw.get("document") or raw.get("entwurf") or "").strip()
    if stage == 1:
        result = agency_anwalt_svc.stage1_entwurf(
            firma=p["firma"],
            kontakt=p["kontakt"],
            leistungen=p["leistungen"],
            budget=p["budget"],
            zero_retention=p["zero_retention"],
            brief=p["brief"],
        )
    elif stage == 2:
        result = agency_anwalt_svc.stage2_avv(
            entwurf=doc or None,
            firma=p["firma"],
            kontakt=p["kontakt"],
            leistungen=p["leistungen"],
            budget=p["budget"],
            zero_retention=p["zero_retention"],
            brief=p["brief"],
        )
    elif stage == 3:
        if not doc:
            pipe = agency_anwalt_svc.pipeline_3_stufen(
                firma=p["firma"],
                kontakt=p["kontakt"],
                leistungen=p["leistungen"],
                budget=p["budget"],
                zero_retention=p["zero_retention"],
                brief=p["brief"],
            )
            return jsonify(pipe["stages"]["3_endkontrolle"] | {"ok": True, "document": pipe["document"]})
        result = agency_anwalt_svc.stage3_endkontrolle(
            doc,
            firma=p["firma"],
            kontakt=p["kontakt"],
            leistungen=p["leistungen"],
            budget=p["budget"],
            zero_retention=p["zero_retention"],
            brief=p["brief"],
        )
    else:
        return jsonify({"error": "stage muss 1, 2 oder 3 sein"}), 400
    return jsonify(result)


@app.get("/api/agency/anwalt/hosting-truth")
def agency_anwalt_hosting_truth():
    """Read-only Hosting/DSGVO-Fakten fuer Vendor Assessment."""
    return jsonify(
        {
            "ok": True,
            "disclaimer": agency_anwalt_svc.DISCLAIMER,
            "hosting": agency_anwalt_svc.HOSTING_TRUTH,
            "docuseal": agency_anwalt_svc.DOCUSEAL,
            "b2b_security": b2b_portal_svc.security_facts(),
        }
    )


def _b2b_auth_ok() -> bool:
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if CRON_SECRET and secret == CRON_SECRET:
        return True
    pw = request.headers.get("X-Agency-Password", "") or request.headers.get("X-Admin-Password", "")
    expected = agency_secret_svc.resolve_agency_admin_password(AGENCY_ADMIN_PASSWORD)
    if expected and pw == expected:
        return True
    portal = (os.getenv("B2B_PORTAL_TOKEN") or "").strip()
    tok = request.headers.get("X-B2B-Token", "") or request.args.get("token", "")
    return bool(portal and tok == portal)


@app.post("/api/b2b/jobs/upload")
def b2b_job_upload():
    if rate_limit("b2b_upload", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "file fehlt"}), 400
    content = f.read()
    if not content:
        return jsonify({"error": "Datei leer"}), 400
    if len(content) > 8_000_000:
        return jsonify({"error": "Datei zu gross (max 8 MB)"}), 400
    kid = (request.form.get("kunde_id") or request.args.get("kunde_id") or "DEMO").upper()
    firma = (request.form.get("firma") or "").strip()
    job_type = (request.form.get("job_type") or "wholesale").strip()
    zr_raw = (request.form.get("zero_retention") or request.args.get("zero_retention") or "1").strip().lower()
    zero_retention = zr_raw not in ("0", "false", "nein", "off", "no")
    db = get_db()
    try:
        job = b2b_portal_svc.create_job(
            db,
            kunde_id=kid,
            firma=firma,
            filename=f.filename or "upload.csv",
            content=content,
            job_type=job_type,
            zero_retention=zero_retention,
        )
        db.commit()
        return jsonify({"ok": True, "job": job, "security": b2b_portal_svc.security_facts()})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)[:200]}), 500


@app.post("/api/b2b/jobs/purge")
def b2b_jobs_purge():
    """Zero-Retention: abgelaufene Jobs bereinigen (Cron oder Agency)."""
    if rate_limit("b2b_purge", 20, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    result = b2b_portal_svc.purge_expired_jobs(get_db())
    return jsonify(result)


@app.get("/api/b2b/security")
def b2b_security_facts():
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"ok": True, **b2b_portal_svc.security_facts()})


@app.post("/api/b2b/jobs/<job_id>/run")
def b2b_job_run(job_id: str):
    if rate_limit("b2b_run", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    # Optional: an n8n weiterreichen
    hook = (os.getenv("B2B_WHOLESALE_WEBHOOK") or "").strip()
    if hook:
        job = b2b_portal_svc.get_job(db, job_id)
        if not job:
            return jsonify({"error": "Job nicht gefunden"}), 404
        try:
            import urllib.request

            body = json.dumps({"job_id": job_id, "job": job}).encode("utf-8")
            req = urllib.request.Request(
                hook, data=body, headers={"Content-Type": "application/json"}, method="POST"
            )
            urllib.request.urlopen(req, timeout=20)
            db.execute(
                "UPDATE b2b_jobs SET status='running', updated_at=datetime('now') WHERE id=?",
                (job_id,),
            )
            db.commit()
            return jsonify({"ok": True, "mode": "n8n", "job": b2b_portal_svc.get_job(db, job_id)})
        except Exception as e:
            # Fallback lokal
            pass
    result = b2b_portal_svc.run_job_local(db, job_id)
    code = 200 if result.get("ok") else 400
    return jsonify(result), code


@app.get("/api/b2b/jobs/<job_id>")
def b2b_job_get(job_id: str):
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    job = b2b_portal_svc.get_job(get_db(), job_id)
    if not job:
        return jsonify({"error": "nicht gefunden"}), 404
    return jsonify({"ok": True, "job": job})


@app.get("/api/b2b/jobs")
def b2b_jobs_list():
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    kid = (request.args.get("kunde_id") or "DEMO").upper()
    db = get_db()
    return jsonify(
        {
            "ok": True,
            "jobs": b2b_portal_svc.list_jobs(db, kid),
            "stats": b2b_portal_svc.stats_for_kunde(db, kid),
        }
    )


@app.post("/api/b2b/jobs/<job_id>/callback")
def b2b_job_callback(job_id: str):
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    result = b2b_portal_svc.apply_callback(get_db(), job_id, data)
    return jsonify(result), (200 if result.get("ok") else 404)


@app.get("/api/b2b/baustoff/pilot")
def b2b_baustoff_pilot():
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(b2b_baustoff_svc.pilot_pack())


@app.post("/api/b2b/baustoff/parse-order")
def b2b_baustoff_parse_order():
    if rate_limit("b2b_baustoff_parse", 60, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or data.get("message") or "").strip()
    kid = (data.get("kunde_id") or "DEMO").upper()
    phone = (data.get("from") or data.get("from_phone") or "").strip()
    save = bool(data.get("save", True))
    parsed = b2b_baustoff_svc.parse_whatsapp_order(text, from_phone=phone)
    if not parsed.get("ok"):
        return jsonify(parsed), 400
    if save:
        db = get_db()
        saved = b2b_baustoff_svc.save_order_draft(db, kunde_id=kid, parsed=parsed)
        return jsonify({**parsed, "saved": saved})
    return jsonify(parsed)


@app.get("/api/b2b/baustoff/orders")
def b2b_baustoff_orders_list():
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    kid = (request.args.get("kunde_id") or "DEMO").upper()
    return jsonify({"ok": True, "orders": b2b_baustoff_svc.list_orders(get_db(), kid)})


@app.post("/api/b2b/baustoff/orders/<order_id>/approve")
def b2b_baustoff_order_approve(order_id: str):
    if rate_limit("b2b_baustoff_approve", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    result = b2b_baustoff_svc.approve_order(get_db(), order_id)
    return jsonify(result), (200 if result.get("ok") else 404)


@app.post("/api/b2b/baustoff/compare")
def b2b_baustoff_compare():
    if rate_limit("b2b_baustoff_compare", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    fa = request.files.get("file_a") or request.files.get("file")
    fb = request.files.get("file_b")
    if not fa or not fb:
        return jsonify({"error": "file_a und file_b (CSV) noetig"}), 400
    a = fa.read()
    b = fb.read()
    if not a or not b:
        return jsonify({"error": "Dateien leer"}), 400
    if len(a) + len(b) > 12_000_000:
        return jsonify({"error": "Dateien zu gross"}), 400
    label_a = (request.form.get("label_a") or fa.filename or "Liste A")[:80]
    label_b = (request.form.get("label_b") or fb.filename or "Liste B")[:80]
    try:
        outlier = float(request.form.get("outlier_pct") or 5)
    except ValueError:
        outlier = 5.0
    result = b2b_baustoff_svc.compare_price_lists(
        a, b, label_a=label_a, label_b=label_b, outlier_pct=outlier
    )
    # Job-Historie (Zero-Retention)
    kid = (request.form.get("kunde_id") or "DEMO").upper()
    firma = (request.form.get("firma") or "").strip()
    zr_raw = (request.form.get("zero_retention") or "1").strip().lower()
    zero_retention = zr_raw not in ("0", "false", "nein", "off", "no")
    db = get_db()
    try:
        stub = (
            f"price_compare;{label_a};{label_b};bytes_a={len(a)};bytes_b={len(b)}\n"
        ).encode("utf-8")
        safe_a = "".join(c for c in label_a if c.isalnum() or c in "._-")[:40] or "A"
        safe_b = "".join(c for c in label_b if c.isalnum() or c in "._-")[:40] or "B"
        job = b2b_portal_svc.create_job(
            db,
            kunde_id=kid,
            firma=firma,
            filename=f"compare_{safe_a}_{safe_b}.txt",
            content=stub,
            job_type="price_compare",
            zero_retention=zero_retention,
        )
        b2b_portal_svc.apply_callback(
            db,
            job["id"],
            {"status": "done", "result": result, "row_count": result.get("stats", {}).get("gemeinsam") or 0},
        )
        job = b2b_portal_svc.get_job(db, job["id"])
        return jsonify({"ok": True, "result": result, "job": job})
    except Exception as e:
        app.logger.exception("b2b_baustoff_compare")
        return jsonify({"ok": True, "result": result, "job_error": str(e)[:200]})


@app.post("/api/sales/invite")
def sales_invite():
    """Christian: Kunden-E-Mail → Discovery-Einladung (CI-Mail)."""
    if rate_limit("sales_invite", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        result = sales_pipeline_svc.invite(
            db,
            email=(data.get("email") or "").strip(),
            firma=(data.get("firma") or "").strip(),
            kontakt=(data.get("kontakt") or data.get("name") or "").strip(),
            phone=(data.get("phone") or data.get("telefon") or "").strip(),
            product=(data.get("product") or "buchhaltung").strip(),
            website=(data.get("website") or "").strip(),
            send_email=str(data.get("send_email", "1")).lower() not in ("0", "false", "nein"),
        )
        code = 200 if result.get("ok") else 400
        return jsonify(result), code
    finally:
        db.close()


@app.post("/api/sales/lead")
def sales_website_lead():
    """Website-Formular → gleiche Pipeline (Rate-Limit + Honeypot)."""
    if rate_limit("sales_lead", 10, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        result = sales_pipeline_svc.website_lead(
            db,
            email=(data.get("email") or "").strip(),
            firma=(data.get("firma") or data.get("company") or "").strip(),
            name=(data.get("name") or data.get("kontakt") or "").strip(),
            phone=(data.get("phone") or "").strip(),
            message=(data.get("message") or "").strip(),
            website=(data.get("website") or "").strip(),
            honeypot=(data.get("website_url") or data.get("honeypot") or "").strip(),
        )
        # Keine internen Links an anonyme Caller leaken wenn skipped
        if result.get("skipped"):
            return jsonify({"ok": True})
        return jsonify(
            {
                "ok": bool(result.get("ok")),
                "message": "Danke. Sie bekommen gleich eine E-Mail mit dem Onboarding-Link.",
            }
        )
    finally:
        db.close()


@app.get("/api/sales/deals")
def sales_deals_list():
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    try:
        return jsonify(sales_pipeline_svc.list_deals(db))
    finally:
        db.close()


@app.get("/api/sales/deals/<deal_id>")
def sales_deal_get(deal_id: str):
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    try:
        deal = sales_pipeline_svc.get_deal(db, deal_id)
        if not deal:
            return jsonify({"error": "Unbekannt"}), 404
        return jsonify(sales_pipeline_svc.public_deal(deal))
    finally:
        db.close()


@app.get("/api/sales/deals/<deal_id>/public")
def sales_deal_public(deal_id: str):
    """Kundenansicht Angebot/Einschätzung (ohne Secrets)."""
    if rate_limit("sales_deal_public", 60, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    db = get_db()
    try:
        data = sales_pipeline_svc.offer_page_data(db, deal_id)
        if not data.get("ok"):
            return jsonify(data), 404
        # Token/Discovery-Secrets nicht raus
        data.pop("discovery_token", None)
        slim = {k: v for k, v in data.items() if k not in ("discovery_token",)}
        if isinstance(slim.get("discovery_link"), str):
            slim.pop("discovery_link", None)
        return jsonify(slim)
    finally:
        db.close()


@app.post("/api/sales/deals/<deal_id>/price")
def sales_deal_price(deal_id: str):
    """Christian setzt Preis und sendet beziffertes Angebot."""
    if rate_limit("sales_price", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        result = sales_pipeline_svc.set_price(
            db,
            deal_id,
            setup_eur=int(data["setup_eur"]) if data.get("setup_eur") is not None else None,
            monthly_eur=int(data["monthly_eur"]) if data.get("monthly_eur") is not None else None,
            send_offer=str(data.get("send_offer", "1")).lower() not in ("0", "false", "nein"),
        )
        return jsonify(result), (200 if result.get("ok") else 400)
    finally:
        db.close()


@app.post("/api/sales/deals/<deal_id>/freigabe")
def sales_deal_freigabe(deal_id: str):
    """Christian: Einschätzung an Kunden freigeben oder zurückhalten."""
    if rate_limit("sales_freigabe", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        result = sales_pipeline_svc.freigabe(
            db,
            deal_id,
            action=(data.get("action") or "send_pain").strip(),
            note=(data.get("note") or "").strip(),
        )
        return jsonify(result), (200 if result.get("ok") else 400)
    finally:
        db.close()


@app.post("/api/sales/deals/<deal_id>/checkout")
def sales_deal_checkout(deal_id: str):
    if rate_limit("sales_checkout", 20, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    try:
        result = sales_pipeline_svc.accept_and_checkout(db, deal_id)
        return jsonify(result), (200 if result.get("ok") is not False and result.get("checkout_url") else 400)
    finally:
        db.close()


@app.post("/api/sales/deals/<deal_id>/accept")
def sales_deal_accept(deal_id: str):
    """Kunde klickt „passt“ → Checkout-Mail/Link (Preis muss gesetzt sein)."""
    if rate_limit("sales_accept", 20, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    db = get_db()
    try:
        result = sales_pipeline_svc.accept_and_checkout(db, deal_id)
        code = 200 if result.get("checkout_url") else 400
        return jsonify(result), code
    finally:
        db.close()


@app.get("/api/buchhaltung/onboarding/schema")
def buchhaltung_onboarding_schema():
    """Fragen, Tools, Pakete, AVV-Text (öffentlich)."""
    return jsonify(buchhaltung_onb_svc.schema())


@app.post("/api/buchhaltung/onboarding/start")
def buchhaltung_onboarding_start():
    """Neue Session. Braucht Agency-Auth oder B2B-Token."""
    if rate_limit("bh_onb_start", 20, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized – Agency-Passwort oder B2B-Token nötig"}), 401
    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        return jsonify(
            buchhaltung_onb_svc.create_session(
                db,
                firma=(data.get("firma") or "").strip(),
                kontakt=(data.get("kontakt") or "").strip(),
                email=(data.get("email") or "").strip(),
            )
        )
    finally:
        db.close()


@app.get("/api/buchhaltung/onboarding")
def buchhaltung_onboarding_list():
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    try:
        return jsonify(buchhaltung_onb_svc.list_sessions(db))
    finally:
        db.close()


def _bh_session_or_401(session_id: str):
    token = (
        request.headers.get("X-Onboarding-Token", "")
        or request.args.get("t", "")
        or (request.get_json(silent=True) or {}).get("token")
        or ""
    )
    db = get_db()
    row = buchhaltung_onb_svc.auth_session(db, session_id, token)
    if row or _agency_auth_ok():
        if not row:
            row = buchhaltung_onb_svc.get_raw(db, session_id)
        return db, row
    db.close()
    return None, None


@app.get("/api/buchhaltung/onboarding/<session_id>")
def buchhaltung_onboarding_get(session_id: str):
    db, row = _bh_session_or_401(session_id)
    if not db:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        if not row:
            return jsonify({"error": "Session unbekannt"}), 404
        return jsonify(buchhaltung_onb_svc.public_view(row))
    finally:
        db.close()


@app.post("/api/buchhaltung/onboarding/<session_id>/firma")
def buchhaltung_onboarding_firma(session_id: str):
    if rate_limit("bh_onb_firma", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    db, row = _bh_session_or_401(session_id)
    if not db:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        if not row:
            return jsonify({"error": "Session unbekannt"}), 404
        data = request.get_json(silent=True) or {}
        return jsonify(
            buchhaltung_onb_svc.save_firma(
                db,
                session_id,
                firma=(data.get("firma") or "").strip(),
                kontakt=(data.get("kontakt") or "").strip(),
                email=(data.get("email") or "").strip(),
            )
        )
    finally:
        db.close()


@app.post("/api/buchhaltung/onboarding/<session_id>/answers")
def buchhaltung_onboarding_answers(session_id: str):
    if rate_limit("bh_onb_answers", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    db, row = _bh_session_or_401(session_id)
    if not db:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        if not row:
            return jsonify({"error": "Session unbekannt"}), 404
        data = request.get_json(silent=True) or {}
        tools = data.get("tools") or []
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",") if t.strip()]
        answers = data.get("answers") if isinstance(data.get("answers"), dict) else {}
        return jsonify(
            buchhaltung_onb_svc.save_tools_and_answers(
                db, session_id, tools=list(tools), answers=answers
            )
        )
    finally:
        db.close()


@app.post("/api/buchhaltung/onboarding/<session_id>/avv")
def buchhaltung_onboarding_avv(session_id: str):
    if rate_limit("bh_onb_avv", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    db, row = _bh_session_or_401(session_id)
    if not db:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        if not row:
            return jsonify({"error": "Session unbekannt"}), 404
        data = request.get_json(silent=True) or {}
        return jsonify(
            buchhaltung_onb_svc.accept_avv(
                db, session_id, name=(data.get("name") or "").strip()
            )
        )
    finally:
        db.close()


@app.post("/api/buchhaltung/onboarding/<session_id>/credentials")
def buchhaltung_onboarding_credentials(session_id: str):
    if rate_limit("bh_onb_creds", 20, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    db, row = _bh_session_or_401(session_id)
    if not db:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        if not row:
            return jsonify({"error": "Session unbekannt"}), 404
        data = request.get_json(silent=True) or {}
        result = buchhaltung_onb_svc.save_credentials(db, session_id, data)
        code = 200 if result.get("ok") else 400
        return jsonify(result), code
    finally:
        db.close()


@app.post("/api/buchhaltung/onboarding/<session_id>/complete")
def buchhaltung_onboarding_complete(session_id: str):
    if rate_limit("bh_onb_done", 20, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    db, row = _bh_session_or_401(session_id)
    if not db:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        if not row:
            return jsonify({"error": "Session unbekannt"}), 404
        result = buchhaltung_onb_svc.complete(db, session_id)
        mail = buchhaltung_onb_svc.notify_owner(result)
        result["mail"] = mail
        return jsonify(result)
    finally:
        db.close()


@app.post("/api/buchhaltung/onboarding/<session_id>/export")
def buchhaltung_onboarding_export(session_id: str):
    """Agency only: Vault für n8n. Audit-Log. Nicht in Chat posten."""
    if rate_limit("bh_onb_export", 10, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    try:
        return jsonify(buchhaltung_onb_svc.export_credentials_agency(db, session_id))
    finally:
        db.close()


@app.post("/api/b2b/baustoff/complaint")
def b2b_baustoff_complaint():
    if rate_limit("b2b_baustoff_complaint", 60, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _b2b_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or data.get("body") or "").strip()
    subject = (data.get("subject") or "").strip()
    result = b2b_baustoff_svc.classify_complaint(text, subject=subject)
    if not result.get("ok"):
        return jsonify(result), 400
    kid = (data.get("kunde_id") or "DEMO").upper()
    firma = (data.get("firma") or "").strip()
    db = get_db()
    try:
        job = b2b_portal_svc.create_job(
            db,
            kunde_id=kid,
            firma=firma,
            filename="complaint.txt",
            content=(subject + "\n\n" + text).encode("utf-8"),
            job_type="complaint",
            zero_retention=True,
        )
        b2b_portal_svc.apply_callback(
            db,
            job["id"],
            {"status": "done", "result": result, "row_count": 1},
        )
        return jsonify({"ok": True, **result, "job": b2b_portal_svc.get_job(db, job["id"])})
    except Exception as e:
        return jsonify({"ok": True, **result, "job_error": str(e)[:200]})


@app.get("/api/nils/whatsapp-ops")
@require_agency_admin
def nils_whatsapp_ops_status():
    """Readiness: Meta-Token + Owner-Whitelist (keine Secrets)."""
    return jsonify(nils_wa_ops_svc.readiness())


@app.get("/api/nils/telegram-ops")
@require_agency_admin
def nils_telegram_ops_status():
    """Readiness: Bot-Token + Owner-Chat-IDs (keine Secrets)."""
    return jsonify(telegram_ops_svc.readiness())


@app.get("/api/nils/llm")
@require_agency_admin
def nils_llm_status():
    """Ollama + Requesty/Primary + optional andere Provider, keine Secrets."""
    import llm_client as llm

    data = llm.readiness()
    try:
        import requesty_client as rq

        data["requesty"] = rq.catalog_summary()
        data["requesty_usage"] = rq.usage_today()
        data["requesty_key"] = rq.key_info()
    except Exception as e:
        data["requesty"] = {"ok": False, "error": type(e).__name__}
    return jsonify(data)


@app.get("/api/nils/requesty/models")
@require_agency_admin
def nils_requesty_models():
    """Requesty-Modellkatalog (IDs + Capabilities), kein Secret."""
    import requesty_client as rq

    if not rq.configured():
        return jsonify({"ok": False, "error": "Requesty nicht konfiguriert", "models": []}), 400
    force = (request.args.get("force") or "").strip() in ("1", "true", "yes")
    models = rq.list_models(force=force)
    slim = []
    for m in models:
        if not isinstance(m, dict):
            continue
        slim.append(
            {
                "id": m.get("id"),
                "supports_vision": bool(m.get("supports_vision")),
                "supports_image_generation": bool(m.get("supports_image_generation")),
                "supports_reasoning": bool(m.get("supports_reasoning")),
                "supports_tool_calling": bool(m.get("supports_tool_calling")),
                "context_window": m.get("context_window"),
                "input_price": m.get("input_price"),
                "output_price": m.get("output_price"),
            }
        )
    return jsonify({"ok": True, **rq.catalog_summary(), "models": slim})


@app.post("/api/nils/requesty/image")
@require_agency_admin
def nils_requesty_image():
    """Bild über Requesty erzeugen und in Nils-Medien speichern."""
    if rate_limit("nils_requesty_image", 10, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or data.get("text") or "").strip()
    if len(prompt) < 3:
        return jsonify({"ok": False, "error": "prompt fehlt"}), 400
    import requesty_client as rq
    import nils_ops as nils_ops_svc

    if not rq.configured():
        return jsonify({"ok": False, "error": "Requesty nicht konfiguriert"}), 400
    gen = rq.generate_image(
        prompt,
        model=(data.get("model") or "").strip() or None,
        size=(data.get("size") or "1024x1024").strip() or "1024x1024",
    )
    if not gen.get("ok"):
        return jsonify({"ok": False, "error": gen.get("error") or "image_fail"}), 502
    db = get_db()
    item = nils_ops_svc._store_generated_image(
        db,
        str(gen["b64"]),
        prompt=prompt,
        model=str(gen.get("model") or ""),
    )
    db.commit()
    return jsonify({"ok": True, "model": gen.get("model"), "media": item})


@app.get("/api/agency/workorders")
@require_agency_admin
def agency_workorders_list():
    db = get_db()
    status = (request.args.get("status") or "").strip() or None
    return jsonify(workorders_svc.list_orders(db, status=status))


@app.post("/api/agency/workorders")
@require_agency_admin
def agency_workorders_create():
    if rate_limit("workorders_create", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    db = get_db()
    if data.get("message"):
        result = workorders_svc.handle_message(db, str(data.get("message")), source="api")
        db.commit()
        if result is None:
            return jsonify({"ok": False, "error": "Kein Auftrag erkannt"}), 400
        return jsonify(result)
    result = workorders_svc.create_order(
        db,
        title=(data.get("title") or "Auftrag").strip(),
        body=(data.get("body") or "").strip(),
        source=(data.get("source") or "api").strip(),
        kunde_id=(data.get("kunde_id") or "").strip() or None,
        kind=(data.get("kind") or "general").strip(),
        patch=data.get("patch") if isinstance(data.get("patch"), dict) else None,
        auto_execute=bool(data.get("auto_execute", True)),
    )
    db.commit()
    return jsonify(result)


@app.post("/api/agency/workorders/<order_id>/execute")
@require_agency_admin
def agency_workorders_execute(order_id: str):
    db = get_db()
    result = workorders_svc.execute_order(db, order_id, confirm=True)
    db.commit()
    return jsonify(result)


@app.post("/api/agency/workorders/<order_id>/done")
@require_agency_admin
def agency_workorders_done(order_id: str):
    data = request.get_json(silent=True) or {}
    db = get_db()
    result = workorders_svc.mark_done(db, order_id, note=(data.get("note") or "").strip())
    db.commit()
    return jsonify(result)


@app.post("/api/telegram/webhook")
def telegram_incoming():
    """Telegram Updates → Nils Ops (nur Owner-Whitelist).

    Wichtig: Sofort 200 zurück (ACK <100ms), Verarbeitung im Thread-Pool.
    Sonst wiederholt Telegram den Update → 4–5 gleiche Antworten auf einmal.
    """
    import telegram_session as tg_sess

    try:
        secret = telegram_ops_svc.webhook_secret()
        if secret:
            got = (request.headers.get("X-Telegram-Bot-Api-Secret-Token") or "").strip()
            if got != secret:
                app.logger.warning("Telegram webhook: Secret ungültig")
                return "Forbidden", 403
        payload = request.get_json(force=True, silent=True) or {}
        update_id = payload.get("update_id")
        parsed = telegram_ops_svc.parse_update(payload) or {}
        chat_id = str(parsed.get("chat_id") or "")
        message_id = int(parsed.get("message_id") or 0)

        # 1) In-Memory Dedup (60s)
        if not tg_sess.remember_incoming(
            update_id=update_id if update_id is not None else None,
            chat_id=chat_id,
            message_id=message_id or None,
        ):
            return jsonify({"ok": True, "duplicate": True, "via": "memory"})

        # 2) SQLite-Claim (ohne zweiten Memory-Hit)
        claim_db = sqlite3.connect(DB_PATH, timeout=10)
        try:
            telegram_ops_svc.ensure_sessions(claim_db)
            if update_id is not None:
                try:
                    claim_db.execute(
                        """INSERT INTO telegram_updates
                           (update_id, chat_id, message_id, status, created_at)
                           VALUES (?,?,?,?,?)""",
                        (int(update_id), chat_id, message_id, "processing", _time.time()),
                    )
                    claim_db.commit()
                except sqlite3.IntegrityError:
                    # Verwaiste processing-Claims (>2 Min) freigeben und neu nehmen
                    row = claim_db.execute(
                        "SELECT status, created_at FROM telegram_updates WHERE update_id=?",
                        (int(update_id),),
                    ).fetchone()
                    if row:
                        st, created = row[0], float(row[1] or 0)
                        if st == "processing" and (_time.time() - created) > 120:
                            claim_db.execute(
                                """UPDATE telegram_updates
                                   SET status=?, created_at=?, finished_at=NULL
                                   WHERE update_id=?""",
                                ("processing", _time.time(), int(update_id)),
                            )
                            claim_db.commit()
                        else:
                            return jsonify({"ok": True, "duplicate": True, "via": "sqlite"})
                    else:
                        return jsonify({"ok": True, "duplicate": True, "via": "sqlite"})
                except Exception:
                    app.logger.exception("telegram claim")
        finally:
            claim_db.close()

        def _worker():
            # app ist die echte Flask-Instanz (kein LocalProxy) → app_context direkt
            with app.app_context():
                db = sqlite3.connect(DB_PATH, timeout=30)
                db.row_factory = sqlite3.Row
                try:
                    telegram_ops_svc.handle_update(db, payload, already_claimed=True)
                    db.commit()
                except Exception as e:
                    app.logger.exception("telegram_ops")
                    try:
                        telegram_ops_svc.finish_update(db, update_id, "error")
                        db.commit()
                    except Exception:
                        pass
                    try:
                        if chat_id and telegram_ops_svc.is_owner_chat(chat_id):
                            telegram_ops_svc.notify_soft_error(chat_id, detail=str(e))
                    except Exception:
                        pass
                finally:
                    db.close()

        tg_sess.POOL.submit(_worker)
        return jsonify({"ok": True, "queued": True})
    except Exception as e:
        # Nie 500 an Telegram (sonst Retry-Chaos). Loggen + soft ACK.
        app.logger.exception("telegram webhook fatal: %s", e)
        return jsonify({"ok": True, "queued": False, "error": "internal"}), 200


@app.post("/api/telegram/setup-webhook")
@require_agency_admin
def telegram_setup_webhook():
    if rate_limit("telegram_setup_webhook", 5, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip() or None
    return jsonify(telegram_ops_svc.set_webhook(url))


@app.post("/api/telegram/send")
@require_agency_admin
def telegram_send():
    if rate_limit("telegram_send", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or data.get("message") or "").strip()
    if not text:
        return jsonify({"error": "text fehlt"}), 400
    chat_id = (data.get("chat_id") or "").strip()
    if chat_id:
        return jsonify(telegram_ops_svc.send_message(chat_id, text))
    return jsonify(telegram_ops_svc.notify_owner(text))


@app.get("/api/nils/history")
@require_agency_admin
def nils_ops_history():
    db = get_db()
    return jsonify({"messages": nils_ops_svc.get_history(db)})


@app.post("/api/nils/message")
@require_agency_admin
def nils_ops_message():
    if rate_limit("nils_ops_msg", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message and not data.get("confirm"):
        return jsonify({"error": "message fehlt"}), 400
    db = get_db()
    try:
        result = nils_ops_svc.handle_turn(
            db,
            message or "ja",
            confirm=bool(data.get("confirm")),
            pending=data.get("pending"),
        )
        db.commit()
        if result.get("error"):
            return jsonify(result), 400
        return jsonify(result)
    except ValueError as e:
        db.rollback()
        return jsonify({"error": str(e)[:200]}), 400
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)[:200]}), 500


@app.post("/api/nils/upload")
@require_agency_admin
def nils_ops_upload():
    if rate_limit("nils_ops_upload", 15, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    message = (request.form.get("message") or "").strip()
    files = []
    for key in request.files:
        f = request.files[key]
        if not f or not f.filename:
            continue
        raw = f.read()
        if raw:
            files.append({"data": raw, "filename": f.filename, "mime": f.mimetype or ""})
    if not files and not message:
        return jsonify({"error": "Datei oder Text fehlt"}), 400
    db = get_db()
    try:
        result = nils_ops_svc.handle_turn(
            db,
            message,
            uploads=files,
            confirm=request.form.get("confirm") == "1",
            pending=json.loads(request.form.get("pending") or "null") if request.form.get("pending") else None,
        )
        db.commit()
        if result.get("error"):
            return jsonify(result), 400
        return jsonify(result)
    except ValueError as e:
        db.rollback()
        return jsonify({"error": str(e)[:200]}), 400
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)[:200]}), 500


@app.get("/api/nils/media/<media_id>")
@require_agency_admin
def nils_ops_media(media_id: str):
    db = get_db()
    row = nils_ops_svc.get_media(db, media_id)
    if not row or not row.get("path") or not os.path.isfile(row["path"]):
        return jsonify({"error": "Nicht gefunden"}), 404
    mime = row.get("mime") or "application/octet-stream"
    with open(row["path"], "rb") as f:
        data = f.read()
    return Response(data, mimetype=mime)


@app.get("/api/jay/catalog")
@require_agency_admin
def jay_catalog():
    return jsonify(jay_voice_svc.catalog())


@app.post("/api/jay/session")
@require_agency_admin
def jay_session():
    if rate_limit("jay_session", 8, 60):
        return jsonify({"ok": False, "error": "Zu viele Anfragen. Kurz warten."}), 429
    data = request.get_json(silent=True) or {}
    result = jay_voice_svc.create_session(
        voice=(data.get("voice") or "christian").strip(),
        personality=(data.get("personality") or "kollege").strip(),
        style=(data.get("style") or "freundlich").strip(),
        confirm_cost=bool(data.get("confirm_cost")),
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/agency/checkout")
@require_agency_admin
def agency_create_checkout():
    if rate_limit("agency_checkout", 20, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    data = request.get_json(silent=True) or {}
    kid = (data.get("kunde_id") or "").upper()
    pkg = data.get("package") or "pro"
    email = data.get("email")
    if not kid:
        return jsonify({"error": "kunde_id fehlt"}), 400
    try:
        result = stripe_billing_svc.create_checkout_session(
            kunde_id=kid,
            package_id=pkg,
            customer_email=email,
        )
        loaded = stripe_billing_svc.load_kunde(kid)
        if loaded:
            k, path = loaded
            k.setdefault("stripe", {})["payment_link"] = result["url"]
            k["stripe"]["status"] = "checkout_offen"
            stripe_billing_svc.save_kunde(k, path)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 400


@app.post("/api/cron/inbox-digest")
def cron_inbox_digest():
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    return jsonify(inbox_svc.send_evening_digest(db))


# ── Agency Posteingang (E-Mail-Agent) ─────────────────────────────────────────

@app.post("/api/inbox/process")
def inbox_process():
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        return jsonify(inbox_svc.process_incoming(db, data))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500


@app.get("/api/agency/leads")
@require_agency_admin
def agency_leads_list():
    db = get_db()
    status = request.args.get("status") or None
    return jsonify({"leads": agency_leads_svc.list_leads(db, status=status)})


@app.get("/api/agency/leads/<int:lead_id>")
@require_agency_admin
def agency_lead_detail(lead_id: int):
    db = get_db()
    lead = agency_leads_svc.get_lead(db, lead_id)
    if not lead:
        return jsonify({"error": "Kontakt nicht gefunden"}), 404
    return jsonify(lead)


@app.post("/api/agency/leads/<int:lead_id>/convert")
@require_agency_admin
def agency_lead_convert(lead_id: int):
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(agency_leads_svc.convert_lead(
            get_db(), lead_id, data.get("kunde_id") or "",
        ))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


def _meta_leads_db_factory():
    """Eigene Connection für Background-Worker (kein Flask-g)."""
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    return db


@app.get("/api/meta-leads/webhook")
def meta_leads_webhook_verify():
    """Meta Lead Ads Webhook-Verifikation (hub.challenge)."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    expected = meta_leads_svc.verify_token_configured()
    if not expected:
        app.logger.error("meta_leads: META_LEAD_VERIFY_TOKEN fehlt")
        return jsonify({"error": "META_LEAD_VERIFY_TOKEN nicht gesetzt"}), 503
    if mode == "subscribe" and token == expected:
        return challenge or "", 200
    return "Forbidden", 403


@app.post("/api/meta-leads/webhook")
def meta_leads_webhook_post():
    """leadgen-Events: sofort HTTP 200, Verarbeitung/Notify im Background."""
    raw = request.get_data()
    sig = request.headers.get("X-Hub-Signature-256")
    if not meta_leads_svc.app_secret() and not meta_leads_svc.insecure_no_secret_allowed():
        app.logger.error("meta_leads: META_LEAD_APP_SECRET/META_APP_SECRET fehlt")
        return jsonify({"error": "Meta App Secret nicht gesetzt"}), 503
    if not meta_leads_svc.verify_signature(raw, sig):
        app.logger.warning("meta_leads: Signatur ungültig")
        return "Forbidden", 403
    payload = request.get_json(force=True, silent=True) or {}
    try:
        db = get_db()
        result = meta_leads_svc.handle_webhook_post(
            db, payload, get_db=_meta_leads_db_factory
        )
        return jsonify(result), 200
    except Exception:
        app.logger.exception("meta_leads webhook")
        # Meta soll nicht endlos retten – soft ACK
        return jsonify({"ok": True, "queued": False, "error": "internal"}), 200


@app.get("/api/meta-leads")
@require_agency_admin
def meta_leads_list_api():
    db = get_db()
    tenant = (request.args.get("tenant_id") or "").strip().upper() or None
    status = request.args.get("status") or None
    return jsonify({
        "leads": meta_leads_svc.list_leads(db, tenant_id=tenant, status=status),
    })


@app.get("/api/meta-leads/config")
@require_agency_admin
def meta_leads_config_get():
    kid = (request.args.get("tenant_id") or KUNDE_ID or "").strip().upper()
    if not kid:
        return jsonify({"error": "tenant_id fehlt"}), 400
    cfg = meta_leads_svc.get_config_by_tenant(get_db(), kid)
    return jsonify(cfg or {})


@app.put("/api/meta-leads/config")
@require_agency_admin
def meta_leads_config_put():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(meta_leads_svc.upsert_tenant_config(get_db(), data))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.exception("meta_leads config")
        return jsonify({"error": str(e)[:200]}), 500


@app.get("/api/meta-leads/<int:lead_id>")
@require_agency_admin
def meta_leads_detail_api(lead_id: int):
    lead = meta_leads_svc.get_lead(get_db(), lead_id)
    if not lead:
        return jsonify({"error": "Lead nicht gefunden"}), 404
    return jsonify(lead)


@app.patch("/api/meta-leads/<int:lead_id>")
@require_agency_admin
def meta_leads_update_api(lead_id: int):
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(meta_leads_svc.update_lead(
            get_db(), lead_id, data, changed_by="agency_api",
        ))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/cron/meta-leads-sync")
def cron_meta_leads_sync():
    """Täglicher Abgleich + Retry fälliger Jobs. Header X-Cron-Secret."""
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        return jsonify(meta_leads_svc.cron_sync_missing(
            get_db(), get_db=_meta_leads_db_factory,
        ))
    except Exception as e:
        app.logger.exception("meta_leads cron")
        return jsonify({"ok": False, "error": str(e)[:200]}), 500


@app.get("/agency/meta-leads")
@require_agency_admin
def agency_meta_leads_dashboard():
    db = get_db()
    tenant = (request.args.get("tenant_id") or "").strip().upper()
    status = request.args.get("status") or None
    leads = meta_leads_svc.list_leads(
        db, tenant_id=tenant or None, status=status, limit=200,
    )
    return Response(
        meta_leads_svc.render_dashboard_html(leads, tenant_filter=tenant),
        mimetype="text/html; charset=utf-8",
    )


@app.get("/agency/meta-leads/<int:lead_id>")
@require_agency_admin
def agency_meta_lead_detail(lead_id: int):
    lead = meta_leads_svc.get_lead(get_db(), lead_id)
    if not lead:
        return "Lead nicht gefunden", 404
    return Response(
        meta_leads_svc.render_lead_detail_html(lead),
        mimetype="text/html; charset=utf-8",
    )


@app.post("/agency/meta-leads/<int:lead_id>/update")
@require_agency_admin
def agency_meta_lead_update_form(lead_id: int):
    data = {
        "status": request.form.get("status"),
        "notes": request.form.get("notes"),
        "assignee": request.form.get("assignee"),
    }
    try:
        meta_leads_svc.update_lead(get_db(), lead_id, data, changed_by="agency_ui")
    except ValueError as e:
        return str(e), 400
    return Response(
        status=303,
        headers={"Location": f"/agency/meta-leads/{lead_id}"},
    )


@app.get("/api/agency/akquise/approvals")
@require_agency_admin
def agency_akquise_approvals_list():
    status = request.args.get("status") or None
    return jsonify({"items": agency_akquise_svc.list_items(status=status)})


@app.get("/api/agency/akquise/queue")
@require_agency_admin
def agency_akquise_queue():
    return jsonify({"items": agency_akquise_svc.latest_buy_queue()})


@app.get("/api/agency/scout/queue")
def agency_scout_queue():
    """WF3: Buy-Queue Kurzuebersicht."""
    if rate_limit("agency_scout_queue", 60, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    limit = int(request.args.get("limit") or 20)
    return jsonify(agency_scout_svc.queue_summary(limit=limit))


@app.post("/api/agency/scout/campaign")
def agency_scout_campaign():
    """WF3: Top-Leads + Outreach-Entwuerfe. Kein Auto-Send."""
    if rate_limit("agency_scout_campaign", 30, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    if isinstance(data.get("body"), dict):
        data = {**data, **data["body"]}
    result = agency_scout_svc.campaign(
        vertical=(data.get("vertical") or data.get("branche") or "").strip(),
        limit=int(data.get("limit") or 10),
        ticket=str(data.get("ticket") or data.get("budget") or "5000"),
        offer=(data.get("offer") or data.get("angebot") or "").strip(),
    )
    return jsonify(result)


@app.post("/api/agency/scout/outreach-draft")
def agency_scout_outreach_draft():
    """Einzel-Anschreiben-Entwurf fuer einen Lead (Freigabe noetig)."""
    if rate_limit("agency_scout_draft", 40, 60):
        return jsonify({"error": "Zu viele Anfragen"}), 429
    if not _agency_auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    if isinstance(data.get("body"), dict):
        data = {**data, **data["body"]}
    lead = data.get("lead") if isinstance(data.get("lead"), dict) else data
    draft = agency_scout_svc.outreach_draft(
        lead,
        ticket=str(data.get("ticket") or "5000"),
        offer=(data.get("offer") or "").strip(),
    )
    return jsonify({"ok": True, "agent": "outreach", "workflow": 4, "draft": draft, "auto_send": False})


@app.post("/api/agency/akquise/approvals")
@require_agency_admin
def agency_akquise_approvals_upsert():
    data = request.get_json(silent=True) or {}
    try:
        item = agency_akquise_svc.upsert(
            key=(data.get("key") or "").strip(),
            status=(data.get("status") or "").strip(),
            name=data.get("name") or "",
            phone=data.get("phone") or "",
            address=data.get("address") or "",
            note=data.get("note") or "",
            vertical=data.get("vertical") or "",
            buy_summary=data.get("buy_summary") or "",
            addon_pitch=data.get("addon_pitch") or "",
            call_script=data.get("call_script") or "",
            roi_label=data.get("roi_label") or "",
        )
        return jsonify({"ok": True, "item": item})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.get("/api/agency/akquise/reminders")
@require_agency_admin
def agency_akquise_reminders():
    return jsonify({"items": agency_akquise_svc.due_reminders()})


@app.post("/api/cron/akquise-reminders")
def cron_akquise_reminders():
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    items = agency_akquise_svc.due_reminders()
    # Secrets aus Env (Deploy setzt SMTP + AGENCY_OWNER_EMAIL)
    secrets = {
        "AGENCY_OWNER_EMAIL": os.getenv("AGENCY_OWNER_EMAIL", ""),
        "SMTP_HOST": os.getenv("SMTP_HOST", ""),
        "SMTP_USER": os.getenv("SMTP_USER", ""),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", ""),
        "SMTP_PORT": os.getenv("SMTP_PORT", "587"),
    }
    result = agency_akquise_svc.send_reminder_mail(items, secrets)
    return jsonify({"success": bool(result.get("ok")), "due": len(items), **result})


@app.get("/api/agency/inbox")
@require_agency_admin
def agency_inbox_list():
    day = request.args.get("day", "today")
    status = request.args.get("status") or None
    db = get_db()
    list_day = None if day == "all" else day
    items = inbox_svc.list_inbox(db, day=list_day, status=status)
    for it in items:
        m = re.search(r"lead:(\d+)", it.get("action_taken") or "")
        it["lead_id"] = int(m.group(1)) if m else None
    return jsonify({
        "items": items,
        "stats": inbox_svc.inbox_stats(db, day="today"),
    })


@app.get("/api/agency/inbox/stats")
@require_agency_admin
def agency_inbox_stats():
    day = request.args.get("day", "today")
    db = get_db()
    return jsonify(inbox_svc.inbox_stats(db, day=day))


@app.patch("/api/agency/inbox/<int:item_id>")
@require_agency_admin
def agency_inbox_update(item_id: int):
    data = request.get_json(silent=True) or {}
    db = get_db()
    ok = inbox_svc.update_inbox_item(
        db, item_id,
        status=data.get("status"),
        notes=data.get("notes"),
    )
    if not ok:
        return jsonify({"error": "Nicht gefunden"}), 404
    return jsonify({"ok": True})


@app.get("/api/agency/inbox/export.csv")
@require_agency_admin
def agency_inbox_export():
    day = request.args.get("day")
    db = get_db()
    csv_data = inbox_svc.export_csv(db, day=day if day and day != "all" else None)
    stamp = datetime.datetime.now().strftime("%Y%m%d")
    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=posteingang_{stamp}.csv"},
    )


@app.post("/api/stripe/webhook")
def stripe_webhook():
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    if not sig:
        return jsonify({"error": "Keine Signatur"}), 400
    try:
        result = stripe_billing_svc.handle_webhook(payload, sig)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# KUNDENKONTO – Auth + Stempelkarte
# ═══════════════════════════════════════════════════════════════════════════════

CUSTOMER_SESSION_COOKIE = "customer_session"


def _get_customer_session():
    """Gibt (customer_id, session_dict) zurück oder (None, None)."""
    token = (
        request.headers.get("X-Customer-Token", "")
        or request.cookies.get(CUSTOMER_SESSION_COOKIE, "")
    )
    if not token:
        return None, None
    db = get_db()
    sess = ca_svc.get_session(db, token)
    if not sess:
        return None, None
    return int(sess["customer_id"]), sess


def _require_customer(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        cid, sess = _get_customer_session()
        if not cid:
            return jsonify({"error": "Nicht eingeloggt"}), 401
        g.customer_id = cid
        g.customer_session = sess
        return f(*args, **kwargs)
    return decorated


def _set_customer_cookie(resp, token: str):
    ttl = ca_svc.CUSTOMER_SESSION_TTL
    resp.set_cookie(
        CUSTOMER_SESSION_COOKIE,
        token,
        max_age=ttl,
        httponly=True,
        secure=True,
        samesite="Strict",
        path="/",
    )
    return resp


def _clear_customer_cookie(resp):
    resp.set_cookie(
        CUSTOMER_SESSION_COOKIE,
        "",
        max_age=0,
        httponly=True,
        secure=True,
        samesite="Strict",
        path="/",
    )
    return resp


# ── Registrierung ──────────────────────────────────────────────────────────────
@app.post("/api/customer/register")
def customer_register():
    ip = get_real_ip()
    if rate_limit(f"creg:{ip}", max_calls=5, window_s=3600):
        return jsonify({"error": "Zu viele Versuche. Bitte warte eine Stunde."}), 429

    data = request.get_json(force=True) or {}
    pw = data.get("password") or ""
    pw2 = data.get("password2") or data.get("passwordConfirm") or ""
    if pw != pw2:
        return jsonify({"error": "Passwörter stimmen nicht überein"}), 400

    db = get_db()
    result = ca_svc.register(
        db,
        email=data.get("email") or "",
        password=pw,
        display_name=data.get("display_name") or data.get("firstName") or "",
        phone=data.get("phone") or "",
        marketing_consent=bool(data.get("marketing_consent")),
    )
    if not result["ok"]:
        return jsonify({"error": result["error"]}), 400

    customer = result["customer"]
    token = ca_svc.create_session(db, customer["id"])

    # E-Mail-Verifizierung senden – nur wenn SMTP konfiguriert ist.
    # Ohne SMTP wird der Account sofort als verifiziert markiert,
    # da eine Verifizierung ohne E-Mail-Versand keinen Sinn ergibt.
    verify_token = result.get("verify_token")
    if verify_token and SMTP_HOST:
        try:
            verify_url = f"{PUBLIC_BASE_URL}/konto?verify={verify_token}"
            _send_customer_email(
                customer["email"],
                f"Bitte bestätige deine E-Mail – {SHOP_NAME}",
                f"""<p>Hallo {customer['display_name']},</p>
<p>klicke auf den Link, um deine E-Mail-Adresse zu bestätigen:</p>
<p><a href="{verify_url}">{verify_url}</a></p>
<p>Der Link ist 24 Stunden gültig.</p>
<p>– {SHOP_NAME}</p>""",
            )
        except Exception as e:
            app.logger.warning(f"verify-email send: {e}")
    elif verify_token and not SMTP_HOST:
        # Kein SMTP → Account direkt verifizieren
        db.execute(
            "UPDATE customer_accounts SET email_verified=1, email_verify_token=NULL WHERE id=?",
            (customer["id"],),
        )
        db.commit()
        customer["email_verified"] = True

    resp = jsonify({"success": True, "customer": customer})
    return _set_customer_cookie(resp, token)


# ── Login ──────────────────────────────────────────────────────────────────────
@app.post("/api/customer/login")
def customer_login():
    ip = get_real_ip()
    if rate_limit(f"clogin:{ip}", max_calls=10, window_s=300):
        return jsonify({"error": "Zu viele Versuche. Bitte warte 5 Minuten."}), 429

    data = request.get_json(force=True) or {}
    db = get_db()
    result = ca_svc.login(db, email=data.get("email") or "", password=data.get("password") or "")
    if not result["ok"]:
        return jsonify({"error": result["error"]}), 401

    customer = result["customer"]
    token = ca_svc.create_session(db, customer["id"])
    resp = jsonify({"success": True, "customer": customer})
    return _set_customer_cookie(resp, token)


# ── Logout ─────────────────────────────────────────────────────────────────────
@app.post("/api/customer/logout")
def customer_logout():
    token = request.cookies.get(CUSTOMER_SESSION_COOKIE, "")
    if token:
        ca_svc.destroy_session(get_db(), token)
    resp = jsonify({"success": True})
    return _clear_customer_cookie(resp)


# ── Profil: GET ────────────────────────────────────────────────────────────────
@app.get("/api/customer/me")
@_require_customer
def customer_me():
    db = get_db()
    cid = g.customer_id
    customer = ca_svc.get_customer_by_id(db, cid)
    if not customer:
        return jsonify({"error": "Konto nicht gefunden"}), 404
    stamp_info = ca_svc.get_stamp_info(db, cid)
    return jsonify({
        "customer": ca_svc._public_customer(customer),
        "stamp_info": stamp_info,
    })


# ── Profil: PATCH ──────────────────────────────────────────────────────────────
@app.patch("/api/customer/me")
@_require_customer
def customer_update_me():
    data = request.get_json(force=True) or {}
    db = get_db()
    result = ca_svc.update_profile(
        db,
        g.customer_id,
        display_name=data.get("display_name"),
        phone=data.get("phone"),
        marketing_consent=data.get("marketing_consent"),
    )
    if not result["ok"]:
        return jsonify({"error": result["error"]}), 400
    return jsonify({"success": True, "customer": result["customer"]})


# ── Passwort ändern ────────────────────────────────────────────────────────────
@app.post("/api/customer/change-password")
@_require_customer
def customer_change_password():
    data = request.get_json(force=True) or {}
    old_pw = data.get("old_password") or ""
    new_pw = data.get("new_password") or ""
    if len(new_pw) < ca_svc.MIN_PASSWORD_LEN:
        return jsonify({"error": f"Neues Passwort mindestens {ca_svc.MIN_PASSWORD_LEN} Zeichen"}), 400
    db = get_db()
    customer = ca_svc.get_customer_by_id(db, g.customer_id)
    if not customer:
        return jsonify({"error": "Konto nicht gefunden"}), 404
    from werkzeug.security import check_password_hash, generate_password_hash
    if not check_password_hash(customer["password_hash"], old_pw):
        return jsonify({"error": "Aktuelles Passwort falsch"}), 400
    from werkzeug.security import generate_password_hash
    db.execute(
        "UPDATE customer_accounts SET password_hash = ?, updated_at = ? WHERE id = ?",
        (generate_password_hash(new_pw), __import__("time").time(), g.customer_id),
    )
    db.commit()
    return jsonify({"success": True})


# ── Stempelkarte-Status ────────────────────────────────────────────────────────
@app.get("/api/customer/stamps")
@_require_customer
def customer_stamps():
    db = get_db()
    info = ca_svc.get_stamp_info(db, g.customer_id)
    return jsonify(info)


# ── Stempel-Vorschau für Checkout ──────────────────────────────────────────────
@app.get("/api/customer/stamp-preview")
@_require_customer
def customer_stamp_preview():
    """Zeigt dem eingeloggten Kunden im Checkout seinen Stempelstand + ob diese Bestellung Punkte gibt."""
    try:
        subtotal = float(request.args.get("subtotal") or 0)
    except ValueError:
        subtotal = 0.0
    delivery_type = (request.args.get("delivery_type") or "abholung").lower()
    db = get_db()
    info = ca_svc.get_stamp_info(db, g.customer_id)
    cfg = ca_svc.get_loyalty_settings(db)
    will_earn = (
        subtotal >= cfg["min_value"]
        and (delivery_type != "lieferung" or cfg["delivery_eligible"])
        and (delivery_type != "abholung" or cfg["pickup_eligible"])
    )
    missing = max(0.0, cfg["min_value"] - subtotal)
    return jsonify({
        **info,
        "will_earn": will_earn,
        "subtotal": subtotal,
        "min_value": cfg["min_value"],
        "missing_for_stamp": round(missing, 2),
    })


# ── Gutschein-Validierung (öffentlich mit Customer-Session) ───────────────────
@app.post("/api/customer/coupon/validate")
@_require_customer
def customer_coupon_validate():
    data = request.get_json(force=True) or {}
    code = (data.get("code") or "").strip().upper()
    try:
        subtotal = float(data.get("subtotal") or 0)
    except ValueError:
        subtotal = 0.0
    if not code:
        return jsonify({"ok": False, "error": "Kein Code angegeben"}), 400
    db = get_db()
    result = ca_svc.validate_coupon(db, code, g.customer_id, subtotal)
    if not result["ok"]:
        return jsonify(result), 400
    coupon = result["coupon"]
    return jsonify({
        "ok": True,
        "code": coupon["code"],
        "type": coupon["type"],
        "value": coupon["value"],
        "discount": result["discount"],
        "valid_until": coupon.get("valid_until"),
    })


# ── Gutschein einlösen (beim Bestellen) ───────────────────────────────────────
@app.post("/api/customer/coupon/redeem")
@_require_customer
def customer_coupon_redeem():
    data = request.get_json(force=True) or {}
    code = (data.get("code") or "").strip().upper()
    order_number = (data.get("order_number") or "").strip()
    try:
        subtotal = float(data.get("subtotal") or 0)
    except ValueError:
        subtotal = 0.0
    if not code or not order_number:
        return jsonify({"ok": False, "error": "Code und Bestellnummer erforderlich"}), 400
    db = get_db()
    # Sicherstellen, dass die Bestellung dem eingeloggten Kunden gehört
    order_row = db.execute(
        "SELECT customer_account_id FROM orders WHERE order_number = ? LIMIT 1",
        (order_number,),
    ).fetchone()
    if not order_row or order_row["customer_account_id"] != g.customer_id:
        return jsonify({"ok": False, "error": "Bestellung nicht gefunden"}), 403
    result = ca_svc.redeem_coupon(db, code, g.customer_id, order_number, subtotal)
    if not result["ok"]:
        return jsonify(result), 400
    return jsonify(result)


# ── Bestellhistorie ────────────────────────────────────────────────────────────
@app.get("/api/customer/orders")
@_require_customer
def customer_orders():
    db = get_db()
    orders = ca_svc.get_customer_orders(db, g.customer_id)
    # items_parsed zurückgeben, items-JSON entfernen
    for o in orders:
        o.pop("items", None)
    return jsonify(orders)


# ── Verfügbare Gutscheine ──────────────────────────────────────────────────────
@app.get("/api/customer/coupons")
@_require_customer
def customer_coupons():
    db = get_db()
    coupons = ca_svc.get_available_coupons(db, g.customer_id)
    return jsonify(coupons)


# ── Passwort-Reset (anfordern) ────────────────────────────────────────────────
@app.post("/api/customer/password-reset-request")
def customer_pw_reset_request():
    ip = get_real_ip()
    if rate_limit(f"pwreset:{ip}", max_calls=5, window_s=3600):
        return jsonify({"success": True})  # Immer gleiche Antwort
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    db = get_db()
    result = ca_svc.request_password_reset(db, email)
    if result.get("found") and result.get("token") and SMTP_HOST:
        try:
            reset_url = f"{PUBLIC_BASE_URL}/konto?reset={result['token']}"
            _send_customer_email(
                result["email"],
                f"Passwort zurücksetzen – {SHOP_NAME}",
                f"""<p>Hallo,</p>
<p>du hast einen Passwort-Reset für dein Konto bei {SHOP_NAME} angefordert.</p>
<p><a href="{reset_url}">Jetzt Passwort zurücksetzen</a></p>
<p>Dieser Link ist 1 Stunde gültig. Falls du diesen Link nicht angefordert hast, ignoriere diese E-Mail.</p>
<p>– {SHOP_NAME}</p>""",
            )
        except Exception as e:
            app.logger.warning(f"pw-reset mail: {e}")
    return jsonify({"success": True})


# ── Passwort-Reset (abschließen) ───────────────────────────────────────────────
@app.post("/api/customer/password-reset-complete")
def customer_pw_reset_complete():
    data = request.get_json(force=True) or {}
    token = (data.get("token") or "").strip()
    new_pw = data.get("password") or ""
    new_pw2 = data.get("password2") or data.get("passwordConfirm") or ""
    if new_pw != new_pw2:
        return jsonify({"error": "Passwörter stimmen nicht überein"}), 400
    db = get_db()
    result = ca_svc.complete_password_reset(db, token, new_pw)
    if not result["ok"]:
        return jsonify({"error": result["error"]}), 400
    return jsonify({"success": True})


# ── E-Mail-Verifizierung ───────────────────────────────────────────────────────
@app.get("/api/customer/verify-email")
def customer_verify_email():
    token = (request.args.get("token") or "").strip()
    if not token:
        return jsonify({"ok": False, "error": "Token fehlt"}), 400
    result = ca_svc.verify_email(get_db(), token)
    if not result["ok"]:
        return jsonify(result), 400
    return jsonify({"ok": True})


# ── Gastbestellung mit Konto verknüpfen ───────────────────────────────────────
@app.post("/api/customer/link-order")
@_require_customer
def customer_link_order():
    data = request.get_json(force=True) or {}
    order_number = (data.get("order_number") or "").strip()
    verify_email_addr = (data.get("email") or "").strip()
    verify_phone = (data.get("phone") or "").strip()
    if not order_number:
        return jsonify({"ok": False, "error": "Bestellnummer fehlt"}), 400
    db = get_db()
    result = ca_svc.link_guest_order(
        db,
        g.customer_id,
        order_number,
        verify_email=verify_email_addr,
        verify_phone=verify_phone,
    )
    if not result["ok"]:
        return jsonify(result), 400
    return jsonify(result)


# ── Konto löschen ──────────────────────────────────────────────────────────────
@app.delete("/api/customer/me")
@_require_customer
def customer_delete_account():
    db = get_db()
    token = request.cookies.get(CUSTOMER_SESSION_COOKIE, "")
    ca_svc.delete_account(db, g.customer_id)
    resp = jsonify({"success": True})
    return _clear_customer_cookie(resp)


# ── Datenexport (DSGVO) ────────────────────────────────────────────────────────
@app.get("/api/customer/export")
@_require_customer
def customer_export():
    db = get_db()
    result = ca_svc.export_account_data(db, g.customer_id)
    if not result["ok"]:
        return jsonify(result), 404
    return jsonify(result)


# ── Admin: Loyalty2-Einstellungen ──────────────────────────────────────────────
@app.get("/api/admin/loyalty2/settings")
@require_admin
def admin_loyalty2_get():
    db = get_db()
    cfg = ca_svc.get_loyalty_settings(db)
    return jsonify(cfg)


@app.post("/api/admin/loyalty2/settings")
@require_admin
def admin_loyalty2_save():
    data = request.get_json(force=True) or {}
    db = get_db()
    field_map = {
        "enabled":            ("loyalty2_enabled", lambda v: "1" if v else "0"),
        "min_value":          ("loyalty2_min_value", lambda v: str(float(v))),
        "stamps_needed":      ("loyalty2_stamps_needed", lambda v: str(max(2, int(v)))),
        "reward_type":        ("loyalty2_reward_type", lambda v: "fixed" if v == "fixed" else "percent"),
        "reward_value":       ("loyalty2_reward_value", lambda v: str(float(v))),
        "reward_min_order":   ("loyalty2_reward_min_order", lambda v: str(float(v))),
        "valid_days":         ("loyalty2_valid_days", lambda v: str(max(1, int(v)))),
        "delivery_eligible":  ("loyalty2_delivery_eligible", lambda v: "1" if v else "0"),
        "pickup_eligible":    ("loyalty2_pickup_eligible", lambda v: "1" if v else "0"),
        "reward_title":       ("loyalty2_reward_title", lambda v: str(v)[:80]),
    }
    for k, (db_key, transform) in field_map.items():
        if k in data:
            try:
                db.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (db_key, transform(data[k])),
                )
            except (ValueError, TypeError):
                pass
    db.commit()
    return jsonify({"success": True, "settings": ca_svc.get_loyalty_settings(db)})


# ── Admin: Kunden-Übersicht ────────────────────────────────────────────────────
@app.get("/api/admin/customers")
@require_admin
def admin_customers():
    db = get_db()
    rows = db.execute(
        """
        SELECT ca.id, ca.email, ca.display_name, ca.phone,
               ca.email_verified, ca.created_at, ca.marketing_consent,
               (SELECT COALESCE(SUM(ll.amount),0) FROM loyalty_ledger ll
                WHERE ll.customer_id = ca.id AND ll.type='earn' AND ll.reversed_by IS NULL) AS stamps_total,
               (SELECT COUNT(*) FROM orders o WHERE o.customer_account_id = ca.id) AS order_count
        FROM customer_accounts ca
        WHERE ca.deleted_at IS NULL
        ORDER BY ca.created_at DESC
        LIMIT 200
        """
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Admin: Manuelle Stempel-Korrektur ──────────────────────────────────────────
@app.post("/api/admin/customers/<int:customer_id>/adjust-stamps")
@require_admin
def admin_adjust_stamps(customer_id):
    data = request.get_json(force=True) or {}
    amount = int(data.get("amount") or 0)
    reason = (data.get("reason") or "Admin-Anpassung")[:200]
    if amount == 0:
        return jsonify({"error": "Betrag darf nicht 0 sein"}), 400
    db = get_db()
    import time as _t
    db.execute(
        """
        INSERT INTO loyalty_ledger (customer_id, amount, type, reason, created_at)
        VALUES (?,?,'adjust',?,?)
        """,
        (customer_id, amount, reason, _t.time()),
    )
    db.commit()
    balance = ca_svc.get_stamp_balance(db, customer_id)
    return jsonify({"success": True, "new_balance": balance})


# ── Hilfsfunktion: Kunden-E-Mail senden ───────────────────────────────────────
def _send_customer_email(to: str, subject: str, html_body: str) -> None:
    if not SMTP_HOST or not to:
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        if SMTP_USER:
            s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_FROM, [to], msg.as_string())


# ══════════════════════════════════════════════════════════════════════════════
# SCHÜLERANGEBOTE API
# ══════════════════════════════════════════════════════════════════════════════

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────
def _get_admin_user_id() -> int | None:
    """Liefert die user_id aus der aktuellen Admin-Session (falls vorhanden)."""
    sess = getattr(g, "auth_session", None)
    if sess:
        return sess.get("user_id")
    token = (
        request.headers.get("X-Admin-Token", "")
        or request.cookies.get("admin_session", "")
    )
    if token:
        import auth_users as _au
        db = get_db()
        s = _au.get_session(db, token)
        if s:
            return s.get("user_id")
    return None


# ── Settings ──────────────────────────────────────────────────────────────────
@app.get("/api/admin/student-offers/settings")
@require_admin
def so_get_settings():
    db = get_db()
    settings = so_svc.get_settings(db)
    windows = so_svc.get_time_windows(db)
    return jsonify({"settings": settings, "time_windows": windows})


@app.post("/api/admin/student-offers/settings")
@require_admin
def so_save_settings():
    data = request.get_json(force=True) or {}
    db = get_db()
    so_svc.save_settings(db, data.get("settings") or data)
    if "time_windows" in data:
        so_svc.save_time_windows(db, data["time_windows"])
    return jsonify({"success": True, "settings": so_svc.get_settings(db)})


# ── Schulen ───────────────────────────────────────────────────────────────────
@app.get("/api/admin/student-offers/schools")
@require_admin
def so_list_schools():
    db = get_db()
    include_inactive = request.args.get("all", "0") == "1"
    return jsonify(so_svc.get_schools(db, include_inactive=include_inactive))


@app.post("/api/admin/student-offers/schools")
@require_admin
def so_add_school():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Schulname fehlt"}), 400
    db = get_db()
    try:
        school = so_svc.add_school(db, name, data.get("short_name"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"success": True, "school": school}), 201


@app.patch("/api/admin/student-offers/schools/<int:school_id>")
@require_admin
def so_update_school(school_id):
    data = request.get_json(force=True) or {}
    db = get_db()
    result = so_svc.update_school(db, school_id, data)
    if not result:
        return jsonify({"error": "Schule nicht gefunden"}), 404
    return jsonify({"success": True, "school": result})


# ── Öffentliche Schulliste (für Bestellportal + Konto) ────────────────────────
@app.get("/api/student-offers/schools")
def so_public_schools():
    db = get_db()
    settings = so_svc.get_settings(db)
    if not settings["enabled"]:
        return jsonify([])
    return jsonify(so_svc.get_schools(db, include_inactive=False))


# ── Öffentliche Settings (für Bestellportal) ──────────────────────────────────
@app.get("/api/student-offers/config")
def so_public_config():
    """Liefert öffentlich sichere Settings (ohne Admin-Only Felder)."""
    db = get_db()
    settings = so_svc.get_settings(db)
    return jsonify({
        "enabled": settings["enabled"],
        "verification_required": settings["verification_required"],
        "allow_first_order_pending": settings["allow_first_order_pending"],
        "pickup_only": settings["pickup_only"],
        "stack_coupons": settings["stack_coupons"],
        "max_items_per_order": settings["max_items_per_order"],
    })


# ── Kundenstatus (Kunden-API) ─────────────────────────────────────────────────
@app.get("/api/customer/student-status")
def customer_student_status():
    token = (
        request.headers.get("X-Customer-Token", "")
        or request.cookies.get("customer_session", "")
    )
    if not token:
        return jsonify({"error": "Nicht eingeloggt"}), 401
    db = get_db()
    sess = ca_svc.get_session(db, token)
    if not sess:
        return jsonify({"error": "Nicht eingeloggt"}), 401
    cid = int(sess["customer_id"])
    status_row = so_svc.get_customer_status(db, cid)
    settings = so_svc.get_settings(db)
    eligible, reason = so_svc.is_eligible(db, cid)
    return jsonify({
        "student_status": so_svc.public_status_info(status_row),
        "eligible": eligible,
        "reason": reason,
        "system_enabled": settings["enabled"],
    })


# ── Kundenstatus (Admin-API: Details) ────────────────────────────────────────
@app.get("/api/admin/student-offers/customer/<int:customer_id>")
@require_admin
def so_get_customer_status(customer_id):
    db = get_db()
    status_row = so_svc.get_customer_status(db, customer_id)
    audit = so_svc.get_audit_log(db, customer_id)
    return jsonify({
        "student_status": status_row,
        "audit_log": audit,
    })


# ── Verifizierung durch Mitarbeiter ──────────────────────────────────────────
@app.post("/api/admin/student-offers/customer/<int:customer_id>/verify")
@require_admin
def so_verify_customer(customer_id):
    data = request.get_json(force=True) or {}
    school_id = data.get("school_id")
    if not school_id:
        return jsonify({"error": "school_id fehlt"}), 400
    valid_until = data.get("valid_until")
    if not valid_until:
        # Automatisch aus Settings berechnen
        db = get_db()
        valid_until = so_svc.compute_valid_until(db)
    else:
        import time as _t2
        try:
            valid_until = float(valid_until)
        except (ValueError, TypeError):
            return jsonify({"error": "Ungültiges Datum"}), 400

    db = get_db()
    emp_id = _get_admin_user_id()
    order_number = data.get("order_number")
    try:
        result = so_svc.verify_customer(
            db, customer_id, int(school_id), float(valid_until),
            verified_by_user_id=emp_id or 0,
            method=data.get("method", "visual_check"),
            order_number=order_number,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"success": True, "student_status": result})


@app.post("/api/admin/student-offers/customer/<int:customer_id>/reject")
@require_admin
def so_reject_customer(customer_id):
    data = request.get_json(force=True) or {}
    reason = (data.get("reason") or "Kein gültiger Nachweis")[:200]
    db = get_db()
    emp_id = _get_admin_user_id()
    result = so_svc.reject_customer(
        db, customer_id, emp_id or 0, reason,
        order_number=data.get("order_number")
    )
    return jsonify({"success": True, "student_status": result})


@app.post("/api/admin/student-offers/customer/<int:customer_id>/revoke")
@require_admin
def so_revoke_customer(customer_id):
    data = request.get_json(force=True) or {}
    reason = (data.get("reason") or "Widerrufen durch Admin")[:200]
    db = get_db()
    emp_id = _get_admin_user_id()
    result = so_svc.revoke_customer(db, customer_id, emp_id or 0, reason)
    return jsonify({"success": True, "student_status": result})


@app.post("/api/admin/student-offers/customer/<int:customer_id>/block")
@require_admin
def so_block_customer(customer_id):
    data = request.get_json(force=True) or {}
    reason = (data.get("reason") or "Gesperrt durch Admin")[:200]
    db = get_db()
    emp_id = _get_admin_user_id()
    result = so_svc.block_customer(db, customer_id, emp_id or 0, reason)
    return jsonify({"success": True, "student_status": result})


@app.post("/api/admin/student-offers/customer/<int:customer_id>/recheck")
@require_admin
def so_recheck_customer(customer_id):
    data = request.get_json(force=True) or {}
    reason = (data.get("reason") or "Erneute Prüfung erforderlich")[:200]
    db = get_db()
    emp_id = _get_admin_user_id()
    result = so_svc.require_recheck(db, customer_id, emp_id or 0, reason)
    return jsonify({"success": True, "student_status": result})


# ── Bestellkarten mit Schülernachweis-Warnung ─────────────────────────────────
@app.get("/api/admin/student-offers/pending-orders")
@require_admin
def so_pending_orders():
    db = get_db()
    return jsonify(so_svc.get_recent_pending_orders(db))


# ── Preis auf Regulär setzen (Mitarbeiter-Aktion) ─────────────────────────────
@app.post("/api/admin/student-offers/order/<order_number>/apply-regular-price")
@require_admin
def so_apply_regular_price(order_number):
    import json as _j
    db = get_db()
    order = db.execute(
        "SELECT * FROM orders WHERE order_number=?", (order_number,)
    ).fetchone()
    if not order:
        return jsonify({"error": "Bestellung nicht gefunden"}), 404

    if order["pay_method"] == "stripe":
        return jsonify({
            "error": "Bei Online-Zahlungen kann der Preis nicht nachträglich geändert werden."
        }), 400

    student_infos = so_svc.get_student_items_info(db)
    try:
        items = _j.loads(order["items"] or "[]")
    except Exception:
        return jsonify({"error": "Bestellartikel ungültig"}), 400

    overrides = {r["item_id"]: dict(r) for r in db.execute("SELECT * FROM menu_overrides").fetchall()}
    catalog_rows = db.execute("SELECT * FROM menu_overrides WHERE price IS NOT NULL").fetchall()

    new_items = []
    diff = 0.0
    for it in items:
        item_id = (it.get("id") or "").strip()
        si = student_infos.get(item_id)
        if not si:
            new_items.append(it)
            continue
        ov = overrides.get(item_id) or {}
        regular_price = ov.get("price")
        if regular_price is None:
            # Aus Katalog laden
            from order_validation import _load_prices as _lp
            cat = _lp()
            prices = cat.get(item_id)
            if prices:
                regular_price = float(list(prices)[0])
        if regular_price is None:
            new_items.append(it)
            continue
        student_price = float(it.get("price") or 0)
        new_it = dict(it)
        new_it["price"] = float(regular_price)
        new_it["_regular_price_applied"] = True
        diff += (float(regular_price) - student_price) * int(it.get("qty") or 1)
        new_items.append(new_it)

    new_total = float(order["total"]) + diff
    emp_id = _get_admin_user_id()
    cid = order["customer_account_id"]
    db.execute(
        "UPDATE orders SET items=?, total=? WHERE order_number=?",
        (_j.dumps(new_items, ensure_ascii=False), round(new_total, 2), order_number)
    )
    if cid:
        so_svc._log_event(db, customer_id=int(cid), action="regular_price_applied",
                          previous_status=None, new_status=None,
                          employee_user_id=emp_id, order_number=order_number,
                          reason=f"Preisdifferenz {diff:+.2f} €")
    db.commit()
    return jsonify({
        "success": True,
        "new_total": round(new_total, 2),
        "price_diff": round(diff, 2),
    })


# ── Schülerpreise für Produkte (Produkteditor) ────────────────────────────────
@app.patch("/api/admin/student-offers/product/<item_id>")
@require_admin
def so_update_product(item_id):
    data = request.get_json(force=True) or {}
    db = get_db()
    existing = db.execute(
        "SELECT * FROM menu_overrides WHERE item_id=?", (item_id,)
    ).fetchone()

    is_student = int(bool(data.get("is_student_offer", False)))
    sp = data.get("student_price")
    if sp is not None:
        try:
            sp = float(sp)
            if sp < 0:
                return jsonify({"error": "Schülerpreis darf nicht negativ sein"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Ungültiger Schülerpreis"}), 400

    requires_verified = int(bool(data.get("requires_verified_student", True)))
    student_pickup_only = int(bool(data.get("student_pickup_only", False)))
    max_per_order = data.get("student_max_per_order")
    if max_per_order is not None:
        try:
            max_per_order = int(max_per_order)
        except (ValueError, TypeError):
            max_per_order = None

    if existing:
        db.execute(
            """UPDATE menu_overrides
               SET is_student_offer=?, student_price=?, requires_verified_student=?,
                   student_pickup_only=?, student_max_per_order=?
               WHERE item_id=?""",
            (is_student, sp, requires_verified, student_pickup_only, max_per_order, item_id)
        )
    else:
        db.execute(
            """INSERT INTO menu_overrides
               (item_id, available, is_student_offer, student_price, requires_verified_student,
                student_pickup_only, student_max_per_order)
               VALUES (?,1,?,?,?,?,?)""",
            (item_id, is_student, sp, requires_verified, student_pickup_only, max_per_order)
        )
    db.commit()
    row = db.execute("SELECT * FROM menu_overrides WHERE item_id=?", (item_id,)).fetchone()
    return jsonify({"success": True, "product": dict(row) if row else {}})


# ── Schülerangebots-Infos für Bestellportal ───────────────────────────────────
@app.get("/api/student-offers/products")
def so_public_products():
    """Schülerpreise für Bestellportal (ohne Kundendaten)."""
    db = get_db()
    settings = so_svc.get_settings(db)
    if not settings["enabled"]:
        return jsonify({})
    infos = so_svc.get_student_items_info(db)
    # Nur öffentlich relevante Felder
    pub = {}
    for item_id, si in infos.items():
        pub[item_id] = {
            "is_student_offer": bool(si.get("is_student_offer")),
            "student_price": si.get("student_price"),
            "requires_verified_student": bool(si.get("requires_verified_student", 1)),
            "student_pickup_only": bool(si.get("student_pickup_only")),
        }
    return jsonify(pub)


# ── Eligibility-Check (für Bestellportal vor Order-Submit) ───────────────────
@app.get("/api/customer/student-eligibility")
def customer_student_eligibility():
    """Prüft ob der eingeloggte Kunde für Schülerpreise berechtigt ist."""
    token = (
        request.headers.get("X-Customer-Token", "")
        or request.cookies.get("customer_session", "")
    )
    db = get_db()
    cid = None
    if token:
        sess = ca_svc.get_session(db, token)
        if sess:
            cid = int(sess["customer_id"])
    delivery_type = request.args.get("delivery_type", "abholung")
    eligible, reason = so_svc.is_eligible(db, cid, delivery_type)
    settings = so_svc.get_settings(db)
    return jsonify({
        "eligible": eligible,
        "reason": reason,
        "system_enabled": settings["enabled"],
        "logged_in": cid is not None,
    })


# ══════════════════════════════════════════════════════════════════════════════
# PHASE A: Endpunkte sind in phase_a_blueprint.py + registriert via app.register_blueprint()
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)

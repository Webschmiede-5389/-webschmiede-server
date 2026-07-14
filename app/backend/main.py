from flask import Flask, request, jsonify, g, after_this_request
from flask_cors import CORS
import requests as req
import os, sqlite3, json, smtplib, datetime, secrets, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from functools import wraps
from collections import defaultdict
import time as _time

load_dotenv()

app = Flask(__name__)

# ── CORS: nur eigene Domain erlaubt ──────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://167.233.211.170",
    "https://snackhouse-mechernich.de",
    "https://www.snackhouse-mechernich.de",
]
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=False)

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

ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD", "snackhouse2026")
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
CRON_SECRET     = os.getenv("CRON_SECRET", "")
GOOGLE_REVIEW_URL = os.getenv("GOOGLE_REVIEW_URL", "")
JARVIS_BOT_SECRET = os.getenv("JARVIS_BOT_SECRET", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "webschmiede-verify")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
KUNDEN_DIR      = os.getenv("KUNDEN_DIR", os.path.join(os.path.dirname(__file__), "..", "kunden"))
JARVIS_UPLOAD_DIR = os.getenv("JARVIS_UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "..", "uploads", "menu"))
os.environ.setdefault("KUNDEN_DIR", KUNDEN_DIR)
os.environ.setdefault("JARVIS_UPLOAD_DIR", JARVIS_UPLOAD_DIR)

# ── Session-Tokens (in-memory, verlieren sich bei Neustart – kein Leak in DB) ─
_sessions: dict[str, float] = {}
SESSION_TTL = 12 * 3600  # 12 Stunden

def create_session() -> str:
    token = secrets.token_hex(32)
    _sessions[token] = _time.time()
    return token

def is_valid_session(token: str) -> bool:
    ts = _sessions.get(token)
    if ts is None:
        return False
    if _time.time() - ts > SESSION_TTL:
        del _sessions[token]
        return False
    return True

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
    if phone and not _PHONE_RE.match(phone):
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
                review_requested INTEGER DEFAULT 0
            )
        """)
        try:
            db.execute("ALTER TABLE contacts ADD COLUMN review_requested INTEGER DEFAULT 0")
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
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('winback_days','30')")
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('review_days','3')")
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('google_review_url','')")
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

        db.commit()

init_db()

# ── Auth ──────────────────────────────────────────────────────────────────────

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Admin-Token", "")
        pw    = request.headers.get("X-Admin-Password", "")
        # Akzeptiere echten Session-Token ODER (Rückwärtskompatibilität) Passwort direkt
        if not (is_valid_session(token) or pw == ADMIN_PASSWORD):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

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
        if not ok:
            app.logger.warning(f"SMS Fehler {r.status_code}: {r.text[:200]}")
        return ok
    except Exception as e:
        app.logger.warning(f"SMS Fehler: {e}")
        log_message(db, to, "sms", template, text, "error", order_number)
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
    """Tägliche Follow-ups: Google-Review (3 Tage nach fertig) + Win-back (30 Tage inaktiv)."""
    review_days  = int(get_setting(db, "review_days", "3") or "3")
    winback_days = int(get_setting(db, "winback_days", "30") or "30")
    review_url   = get_setting(db, "google_review_url", "") or GOOGLE_REVIEW_URL
    stats = {"reviews_sent": 0, "winbacks_sent": 0, "errors": 0}

    # ── Review: Bestellung abgeschlossen vor X Tagen ───────────────────────
    if review_url:
        rows = db.execute(
            """SELECT * FROM orders
               WHERE status='fertig' AND review_sent=0 AND phone != ''
               AND completed_at IS NOT NULL
               AND completed_at <= datetime('now', ?)""",
            (f"-{review_days} days",),
        ).fetchall()
        for r in rows:
            o = dict(r)
            if already_sent_template(db, o["phone"], "review_request", within_days=365):
                db.execute("UPDATE orders SET review_sent=1 WHERE order_number=?", (o["order_number"],))
                continue
            name = o.get("first_name") or "du"
            msg = (
                f"Hallo {name}! Hat dir deine Bestellung bei {SHOP_NAME} geschmeckt?\n"
                f"Wir würden uns über eine kurze Google-Bewertung freuen:\n{review_url}\n"
                f"Danke! – {SHOP_NAME}"
            )
            if send_sms(db, o["phone"], msg, "review_request", o["order_number"]):
                db.execute("UPDATE orders SET review_sent=1 WHERE order_number=?", (o["order_number"],))
                stats["reviews_sent"] += 1
            else:
                stats["errors"] += 1
    db.commit()

    # ── Win-back: Kunde seit X Tagen inaktiv ───────────────────────────────
    contacts = db.execute(
        """SELECT * FROM contacts
           WHERE phone != '' AND total_orders >= 1
           AND last_order_at IS NOT NULL
           AND last_order_at <= datetime('now', ?)""",
        (f"-{winback_days} days",),
    ).fetchall()
    for c in contacts:
        c = dict(c)
        if already_sent_template(db, c["phone"], "winback_30d", within_days=90):
            continue
        name = c.get("first_name") or "du"
        msg = (
            f"Hallo {name}! Wir vermissen dich bei {SHOP_NAME}.\n"
            f"Komm vorbei oder bestelle online – wir freuen uns auf dich!\n"
            f"{SHOP_PHONE}"
        )
        if send_sms(db, c["phone"], msg, "winback_30d", ""):
            stats["winbacks_sent"] += 1
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

# ── Öffentlich: Aktive Aktion abrufen ─────────────────────────────────────────
@app.get("/api/promo/active")
def promo_active():
    promo = get_active_promo()
    if promo:
        return jsonify({"active": True, "promo": promo})
    return jsonify({"active": False})

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

# ── Öffentlich: Settings abrufen ───────────────────────────────────────────
@app.get("/api/settings")
def get_settings():
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    s = {r["key"]: r["value"] for r in rows}
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
    return jsonify({
        "online":        s.get("online","1") == "1",
        "wait_pickup":   int(s.get("wait_pickup","20")),
        "wait_delivery": int(s.get("wait_delivery","40")),
        "offline_msg":   s.get("offline_msg","Wir sind gleich zurück!"),
        "overrides":     overrides,
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

@app.post("/api/order")
def create_order():
    ip  = request.remote_addr or "unknown"
    if rate_limit(f"order:{ip}", max_calls=10, window_s=3600):
        return jsonify({"error": "Zu viele Bestellungen. Bitte warte etwas."}), 429

    data = request.get_json(force=True)

    err = validate_order(data)
    if err:
        return jsonify({"error": err}), 400

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

    db = get_db()
    db.execute("""INSERT OR IGNORE INTO orders
        (order_number,first_name,last_name,phone,email,address,delivery_type,pay_method,items,total,wunschzeit,notes,promo_applied,contact_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (order["order_number"], order["first_name"], order["last_name"],
         order["phone"], order["email"], order["address"],
         order["delivery_type"], order["pay_method"],
         json.dumps(order["items"], ensure_ascii=False),
         order["total"], order["wunschzeit"], order["notes"], promo_label, None)
    )

    contact_id, is_new = upsert_contact(db, order)
    if contact_id:
        db.execute("UPDATE orders SET contact_id=? WHERE order_number=?", (contact_id, order["order_number"]))
    db.commit()

    order["promo_applied"] = promo_label
    automate_order_created(db, order, is_new)
    ghl_sync(order)
    if order.get("email"):
        send_confirmation_email(order)

    return jsonify({"success": True, "orderNumber": order["order_number"]})

@app.post("/api/admin/login")
def admin_login():
    ip  = request.remote_addr or "unknown"
    key = f"login:{ip}"
    if rate_limit(key, max_calls=5, window_s=60):
        return jsonify({"error": "Zu viele Versuche. Bitte warte 1 Minute."}), 429
    data = request.get_json(force=True)
    if data.get("password") == ADMIN_PASSWORD:
        token = create_session()
        return jsonify({"success": True, "token": token})
    return jsonify({"success": False}), 401

@app.get("/api/admin/orders")
@require_admin
def admin_orders():
    db = get_db()
    rows = db.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 100").fetchall()
    orders = []
    for r in rows:
        o = dict(r)
        o["items"] = json.loads(o["items"] or "[]")
        orders.append(o)
    return jsonify(orders)

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
        if order.get("email"):
            send_status_email(order, new_status)
        automate_status_changed(db, order, new_status)

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

@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "snack-api"})

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

def _whatsapp_download_media(media_id: str) -> tuple[bytes, str] | tuple[None, None]:
    if not WHATSAPP_ACCESS_TOKEN or not media_id:
        return None, None
    try:
        r1 = req.get(
            f"https://graph.facebook.com/v19.0/{media_id}",
            headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"},
            timeout=15,
        )
        r1.raise_for_status()
        url = r1.json().get("url")
        if not url:
            return None, None
        r2 = req.get(url, headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"}, timeout=30)
        r2.raise_for_status()
        ctype = r2.headers.get("Content-Type", "image/jpeg")
        ext = "jpg" if "jpeg" in ctype else "png" if "png" in ctype else "jpg"
        return r2.content, ext
    except Exception:
        return None, None

def _whatsapp_send_text(to_phone: str, body: str):
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        return False
    try:
        req.post(
            f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "to": to_phone, "type": "text", "text": {"body": body[:4096]}},
            timeout=15,
        )
        return True
    except Exception:
        return False

@app.get("/api/whatsapp/webhook")
def whatsapp_verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return challenge or "", 200
    return "Forbidden", 403

@app.post("/api/whatsapp/webhook")
def whatsapp_incoming():
    payload = request.get_json(force=True, silent=True) or {}
    db = get_db()
    replies = []
    for msg in jarvis_bot.parse_whatsapp_payload(payload):
        image_bytes, ext = None, "jpg"
        if msg.get("image_id"):
            image_bytes, ext = _whatsapp_download_media(msg["image_id"])
        result = jarvis_bot.handle_message(
            db, msg["phone"], msg.get("text", ""),
            image_bytes=image_bytes, image_ext=ext or "jpg", channel="whatsapp",
        )
        reply = result.get("reply", "")
        if reply:
            _whatsapp_send_text(msg["phone"], reply)
            replies.append({"phone": msg["phone"], "reply": reply})
    db.commit()
    return jsonify({"success": True, "replies": replies})

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

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)

#!/usr/bin/env python3
"""
Go-Live Paket A+B für Kunden (SMS, Review, Order-Alert, Onboarding, Testbestellungen).

  python scripts/go_live.py SHY001 check
  python scripts/go_live.py SHY001 configure --owner-phone +49170... --sms-key KEY --review-url URL
  python scripts/go_live.py SHY001 test-orders
  python scripts/go_live.py SHY001 onboard --support-email du@webschmiede.de
  python scripts/go_live.py SHY001 run --support-email du@webschmiede.de
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

KUNDEN_DIR = os.path.join(ROOT, "kunden")

try:
    import requests as req
except ImportError:
    req = None


def load_kunde(kid: str) -> dict:
    kid = kid.upper()
    for fname in os.listdir(KUNDEN_DIR):
        if fname.endswith(".json") and fname.startswith(kid):
            with open(os.path.join(KUNDEN_DIR, fname), encoding="utf-8") as f:
                return json.load(f)
    raise SystemExit(f"Kunde {kid} nicht in kunden/")


def api_base(k: dict) -> str:
    u = k.get("urls", {}).get("test_hauptseite", "").rstrip("/")
    if not u:
        ip = k.get("server", {}).get("ip", "167.233.211.170")
        u = f"http://{ip}"
    return u


def ssh_run(cmd: str) -> str:
    import paramiko
    from agency_config import ssh_connect

    c = paramiko.SSHClient()
    ssh_connect(c)
    _, o, e = c.exec_command(cmd, timeout=30)
    out = o.read().decode("utf-8", errors="replace").strip()
    err = e.read().decode("utf-8", errors="replace").strip()
    c.close()
    if err and "grep" not in cmd:
        print("SSH:", err[:300])
    return out


def read_server_env() -> dict:
    env_path = "/root/app/backend/.env"
    raw = ssh_run(f"cat {env_path} 2>/dev/null || true")
    out = {}
    for line in raw.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def set_server_env(updates: dict):
    env_path = "/root/app/backend/.env"
    for key, val in updates.items():
        safe = str(val).replace("'", "'\"'\"'")
        ssh_run(
            f"grep -q '^{key}=' {env_path} && "
            f"sed -i 's|^{key}=.*|{key}={safe}|' {env_path} || "
            f"echo '{key}={safe}' >> {env_path}"
        )
    ssh_run("systemctl restart snack-api")
    time.sleep(2)
    status = ssh_run("systemctl is-active snack-api")
    print(f"snack-api: {status}")


def cmd_check(k: dict):
    print(f"\n=== Go-Live Check: {k['name']} ({k['id']}) ===\n")
    base = api_base(k)
    env = read_server_env()

    checks = []

    if req:
        try:
            r = req.get(f"{base}/api/health", timeout=8)
            checks.append(("API /health", r.ok, r.text[:80]))
        except Exception as e:
            checks.append(("API /health", False, str(e)))
    else:
        checks.append(("API /health", False, "requests nicht installiert"))

    sms_on = env.get("SMS_ENABLED", "false").lower() in ("1", "true", "yes")
    has_key = bool(env.get("SMS_API_KEY"))
    has_owner = bool(env.get("OWNER_PHONE"))
    checks.append(("SMS aktiviert", sms_on, env.get("SMS_ENABLED", "")))
    checks.append(("SMS API Key", has_key, "gesetzt" if has_key else "fehlt"))
    checks.append(("OWNER_PHONE", has_owner, env.get("OWNER_PHONE", "fehlt")))
    checks.append(("GOOGLE_REVIEW_URL (.env)", bool(env.get("GOOGLE_REVIEW_URL")), env.get("GOOGLE_REVIEW_URL", "")[:60]))
    checks.append(("N8N_ORDER_WEBHOOK", bool(env.get("N8N_ORDER_WEBHOOK")), env.get("N8N_ORDER_WEBHOOK", "optional")[:60]))
    checks.append(("CRON_SECRET", bool(env.get("CRON_SECRET")), "für Follow-ups"))

    if req and env.get("ADMIN_PASSWORD"):
        try:
            r = req.get(
                f"{base}/api/admin/settings",
                headers={"X-Admin-Password": env.get("ADMIN_PASSWORD", "")},
                timeout=8,
            )
            if r.ok:
                s = r.json()
                review = s.get("google_review_url", "")
                checks.append(("Review-URL (Admin)", bool(review), review[:60] or "fehlt"))
            else:
                checks.append(("Review-URL (Admin)", False, f"HTTP {r.status_code}"))
        except Exception as e:
            checks.append(("Review-URL (Admin)", False, str(e)))

    print(f"{'Check':<28} {'OK?':<6} Details")
    print("-" * 70)
    ok_count = 0
    for name, ok, detail in checks:
        mark = "OK" if ok else "-"
        if ok:
            ok_count += 1
        print(f"{name:<28} {mark:<6} {detail}")
    print(f"\n{ok_count}/{len(checks)} Checks bestanden.\n")

    if not has_key or not has_owner:
        print("Nächster Schritt:")
        print("  python scripts/go_live.py SHY001 configure --owner-phone +49... --sms-key DEIN_KEY\n")
    print("n8n Order-Alert: infra/n8n/workflow-new-order-alert.json importieren")
    print("  Webhook-URL als N8N_ORDER_WEBHOOK in Server-.env eintragen\n")


def cmd_configure(k: dict, args):
    updates = {}
    if args.sms_key:
        updates["SMS_API_KEY"] = args.sms_key
        updates["SMS_ENABLED"] = "true"
    if args.owner_phone:
        updates["OWNER_PHONE"] = args.owner_phone
    if args.review_url:
        updates["GOOGLE_REVIEW_URL"] = args.review_url
    if args.n8n_webhook:
        updates["N8N_ORDER_WEBHOOK"] = args.n8n_webhook
    if args.public_base:
        updates["PUBLIC_BASE_URL"] = args.public_base
    if not updates:
        print("Nichts zu setzen. Nutze --owner-phone, --sms-key, --review-url, --n8n-webhook")
        return

    print("Aktualisiere Server-.env …")
    set_server_env(updates)

    if args.review_url and req:
        env = read_server_env()
        pw = env.get("ADMIN_PASSWORD", "")
        base = api_base(k)
        if pw:
            r = req.post(
                f"{base}/api/admin/settings",
                headers={"X-Admin-Password": pw, "Content-Type": "application/json"},
                json={"google_review_url": args.review_url},
                timeout=10,
            )
            print(f"Admin Review-URL: {'OK' if r.ok else r.text[:100]}")

    print("Configure fertig.")


def make_order(order_number: str, delivery: bool, unit_price: float = 7.5) -> dict:
    items = [{"id": "d4", "name": "Lahmacun-Rolle (TEST)", "price": unit_price, "qty": 2, "free": False}]
    subtotal = round(unit_price * 2, 2)
    fee = 2.5 if delivery else 0.0
    return {
        "firstName": "Webschmiede",
        "lastName": "Test",
        "phone": "+4917012345678",
        "email": "",
        "address": "Teststraße 1, Mechernich" if delivery else "",
        "deliveryType": "lieferung" if delivery else "abholung",
        "payMethod": "cash",
        "items": items,
        "total": round(subtotal + fee, 2),
        "wunschzeit": "So schnell wie möglich",
        "notes": "TESTBESTELLUNG Go-Live, bitte ignorieren / auf Fertig setzen",
        "orderNumber": order_number,
        "_hp": "",
    }


def _resolve_test_unit_price(base: str) -> float:
    """Menü-Override auf dem Server beachten (z.B. d4=7.80)."""
    try:
        import paramiko
        from agency_config import ssh_connect

        c = paramiko.SSHClient()
        ssh_connect(c)
        _, o, _ = c.exec_command(
            "/root/app/venv/bin/python3 -c "
            "\"import sqlite3; db=sqlite3.connect('/root/app/backend/orders.db'); "
            "r=db.execute(\\\"SELECT price FROM menu_overrides WHERE item_id='d4'\\\").fetchone(); "
            "print(r[0] if r and r[0] is not None else 7.5)\"",
            timeout=15,
        )
        raw = o.read().decode().strip()
        c.close()
        if raw:
            return float(raw)
    except Exception:
        pass
    return 7.5


def cmd_test_orders(k: dict, dry_run: bool):
    if not req:
        raise SystemExit("pip install requests")
    base = api_base(k)
    unit = _resolve_test_unit_price(base)
    ts = datetime.now().strftime("%H%M%S")
    tests = [
        ("Abholung", make_order(f"TEST-PICKUP-{ts}", False, unit)),
        ("Lieferung", make_order(f"TEST-DELIVERY-{ts}", True, unit)),
    ]
    for label, payload in tests:
        print(f"\n--- Test {label} ({payload['orderNumber']}) ---")
        if dry_run:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            continue
        r = req.post(f"{base}/api/order", json=payload, timeout=15)
        print(f"Status: {r.status_code}")
        print(r.text[:200])
    if not dry_run:
        print("\nAdmin oeffnen, Testbestellungen pruefen, Status auf 'Fertig' setzen.\n")


def cmd_onboard(kid: str, extra: list[str]):
    import subprocess
    script = os.path.join(ROOT, "scripts", "send_onboarding_email.py")
    subprocess.run([sys.executable, script, kid.upper()] + extra, check=False)


def cmd_run(k: dict, args):
    cmd_check(k)
    env = read_server_env()
    if args.owner_phone and args.sms_key:
        cmd_configure(k, args)
    elif not env.get("SMS_API_KEY"):
        print("(SMS nicht konfiguriert - configure mit --sms-key und --owner-phone)\n")

    if not args.skip_tests:
        cmd_test_orders(k, dry_run=args.dry_run)

    if args.support_email or args.onboard:
        onboard_args = ["--upload-handout"]
        if args.support_email:
            onboard_args += ["--support-email", args.support_email]
        if args.dry_run:
            onboard_args.append("--dry-run")
        cmd_onboard(k["id"], onboard_args)


def main():
    ap = argparse.ArgumentParser(description="Go-Live Paket A+B")
    ap.add_argument("kunde_id")
    ap.add_argument("action", choices=["check", "configure", "test-orders", "onboard", "run"])
    ap.add_argument("--owner-phone")
    ap.add_argument("--sms-key")
    ap.add_argument("--review-url")
    ap.add_argument("--n8n-webhook")
    ap.add_argument("--public-base")
    ap.add_argument("--support-email")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--onboard", action="store_true", help="Bei run: Onboarding-Mail senden")
    args = ap.parse_args()

    k = load_kunde(args.kunde_id)

    if args.action == "check":
        cmd_check(k)
    elif args.action == "configure":
        cmd_configure(k, args)
    elif args.action == "test-orders":
        cmd_test_orders(k, args.dry_run)
    elif args.action == "onboard":
        extra = []
        if args.support_email:
            extra += ["--support-email", args.support_email]
        if args.dry_run:
            extra.append("--dry-run")
        extra.append("--upload-handout")
        cmd_onboard(k["id"], extra)
    elif args.action == "run":
        cmd_run(k, args)


if __name__ == "__main__":
    main()

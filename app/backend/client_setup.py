"""Kunden-Subdomain, Webroot und Server-Automationen (läuft auf dem Agency-Server)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from stripe_billing import load_kunde, save_kunde

AGENCY_DOMAIN = "digitalehandwerkskunst.de"
DEMO_SUBDOMAIN = "muster"
ENV_PATH = Path(os.getenv("BACKEND_ENV_PATH", "/root/app/backend/.env"))
STATIC_SRC = Path(os.getenv("APP_STATIC_DIR", "/root/app/static"))
SSL_EMAIL = "info@digitalehandwerkskunst.de"


def _on_server() -> bool:
    return ENV_PATH.parent.is_dir() and Path("/etc/nginx").is_dir()


def _run(cmd: str, timeout: int = 120) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return 1, "Timeout"
    except Exception as e:
        return 1, str(e)[:200]


def _read_env_file() -> dict[str, str]:
    out: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    for k, v in os.environ.items():
        if k.startswith(("SMS_", "N8N_", "GOOGLE_", "GHL_", "CRON_", "PUBLIC_", "OWNER_")):
            out.setdefault(k, v)
    return out


def _set_env_var(key: str, val: str) -> None:
    safe = str(val).replace("'", "'\"'\"'")
    _run(
        f"grep -q '^{key}=' {ENV_PATH} 2>/dev/null && "
        f"sed -i 's|^{key}=.*|{key}={safe}|' {ENV_PATH} || "
        f"echo '{key}={safe}' >> {ENV_PATH}"
    )


def _merge_cors(*hosts: str) -> None:
    bases = {
        "http://167.233.150.230",
        "https://167.233.150.230",
        "https://digitalehandwerkskunst.de",
        "https://yassine.digitalehandwerkskunst.de",
        f"http://{DEMO_SUBDOMAIN}.{AGENCY_DOMAIN}",
        f"https://{DEMO_SUBDOMAIN}.{AGENCY_DOMAIN}",
    }
    for h in hosts:
        bases.add(f"http://{h}")
        bases.add(f"https://{h}")
    env = _read_env_file()
    for part in (env.get("CORS_ORIGINS") or "").split(","):
        p = part.strip().rstrip("/")
        if p:
            bases.add(p)
    pub = (env.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if pub:
        bases.add(pub)
    _set_env_var("CORS_ORIGINS", ",".join(sorted(bases)))


def nginx_config(host: str, webroot: str, *, ssl: bool = False) -> str:
    """HTTP immer. Bei ssl=True zusätzlich HTTPS mit Let's Encrypt-Pfaden."""
    http_block = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {host};
"""
    if ssl:
        http_block += f"""    return 301 https://$host$request_uri;
}}

server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name {host};

    ssl_certificate     /etc/letsencrypt/live/{host}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{host}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
"""
    else:
        http_block += "\n"

    body = f"""
    root {webroot};
    index index.html;

    location = /bestellen {{ try_files /order.html =404; }}
    location = /admin {{ try_files /admin.html =404; }}
    location = /onboarding {{ try_files /onboarding.html =404; }}
    location = /uebergabe-handbuch {{ try_files /uebergabe-handbuch.html =404; }}
    location = /datenschutz {{ try_files /datenschutz.html =404; }}
    location = /impressum {{ try_files /impressum.html =404; }}

    location /api/ {{
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 30;
    }}

    location /uploads/ {{
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
    }}

    location / {{ try_files $uri $uri/ /index.html; }}

    location = /robots.txt {{
        add_header Content-Type text/plain;
        return 200 "User-agent: *\\nDisallow: /admin\\nDisallow: /api/\\n";
    }}

    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
}}
"""
    return http_block + body


def global_automation_status() -> dict:
    env = _read_env_file()
    n8n_base = env.get("N8N_WEBHOOK_BASE", "http://127.0.0.1:5678")
    return {
        "sms": {
            "label": "SMS (seven.io)",
            "active": env.get("SMS_ENABLED", "").lower() in ("1", "true", "yes")
            and bool(env.get("SMS_API_KEY")) and bool(env.get("OWNER_PHONE")),
            "hint": "SMS_ENABLED + SMS_API_KEY + OWNER_PHONE",
        },
        "review": {
            "label": "Google Review",
            "active": bool(env.get("GOOGLE_REVIEW_URL")),
            "hint": "GOOGLE_REVIEW_URL",
        },
        "n8n_orders": {
            "label": "n8n Bestell-Alerts",
            "active": bool(env.get("N8N_ORDER_WEBHOOK")),
            "hint": "N8N_ORDER_WEBHOOK",
        },
        "inbox": {
            "label": "E-Mail-Agent",
            "active": bool(env.get("CRON_SECRET")),
            "hint": "CRON_SECRET + n8n IMAP-Workflow",
        },
        "stripe": {
            "label": "Stripe Checkout",
            "active": bool(env.get("STRIPE_SECRET_KEY") or env.get("STRIPE_WEBHOOK_SECRET")),
            "hint": "STRIPE_SECRET_KEY in deploy.secrets.local",
        },
        "n8n_url": n8n_base,
        "public_base": env.get("PUBLIC_BASE_URL", ""),
    }


def prepare_webroot(kid: str) -> dict:
    loaded = load_kunde(kid)
    if not loaded:
        raise ValueError("Kunde nicht gefunden")
    k, path = loaded
    webroot = Path(k.get("server", {}).get("ordner", f"/var/www/{k.get('slug', 'kunde')}"))
    if not _on_server():
        return {
            "ok": False,
            "dry_run": True,
            "webroot": str(webroot),
            "message": "Webroot-Vorbereitung nur auf dem Server möglich",
        }
    webroot.mkdir(parents=True, exist_ok=True)
    copied = 0
    if STATIC_SRC.is_dir():
        for name in ("index.html", "order.html", "admin.html", "onboarding.html",
                     "uebergabe-handbuch.html",
                     "datenschutz.html", "impressum.html", "favicon.png",
                     "favicon-192.png", "apple-touch-icon.png"):
            src = STATIC_SRC / name
            dst = webroot / name
            if src.is_file() and (not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime):
                shutil.copy2(src, dst)
                copied += 1
        # CI-Assets für Onboarding-Logo etc.
        ci_src = STATIC_SRC / "ci"
        ci_dst = webroot / "ci"
        if ci_src.is_dir():
            ci_dst.mkdir(parents=True, exist_ok=True)
            for src in ci_src.iterdir():
                if src.is_file():
                    dst = ci_dst / src.name
                    if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
                        shutil.copy2(src, dst)
                        copied += 1
    return {"ok": True, "webroot": str(webroot), "files_copied": copied}


def setup_subdomain(kid: str, *, ssl: bool = False) -> dict:
    loaded = load_kunde(kid)
    if not loaded:
        raise ValueError("Kunde nicht gefunden")
    k, kpath = loaded
    sub = (k.get("urls") or {}).get("subdomain") or _slugify(k.get("slug", ""))
    if not sub:
        raise ValueError("Subdomain fehlt in kunden.json")
    webroot = k.get("server", {}).get("ordner", f"/var/www/{k.get('slug', 'kunde')}")
    host = f"{sub}.{AGENCY_DOMAIN}"
    base_https = f"https://{host}"

    if not _on_server():
        return {
            "ok": False,
            "dry_run": True,
            "host": host,
            "webroot": webroot,
            "dns_hint": f"A-Record: {sub} → 167.233.150.230 (oder Wildcard *)",
            "message": "Subdomain-Setup nur auf dem Server. Lokal: python scripts/setup_client_subdomain.py",
        }

    prepare_webroot(kid)
    site = Path(f"/etc/nginx/sites-available/kunde-{sub}.{AGENCY_DOMAIN}")
    enabled = Path(f"/etc/nginx/sites-enabled/kunde-{sub}.{AGENCY_DOMAIN}")
    site.write_text(nginx_config(host, webroot, ssl=False), encoding="utf-8")
    if enabled.exists() or not enabled.is_symlink():
        enabled.unlink(missing_ok=True)
    enabled.symlink_to(site)
    code, out = _run("nginx -t && systemctl reload nginx")
    if code != 0:
        raise RuntimeError(f"nginx: {out[:200]}")

    ssl_ok = False
    cert_path = Path(f"/etc/letsencrypt/live/{host}/fullchain.pem")
    if ssl:
        if not cert_path.is_file():
            code, out = _run(
                f"certbot certonly --nginx -d {host} --non-interactive --agree-tos "
                f"-m {SSL_EMAIL} 2>&1",
                timeout=180,
            )
            ssl_ok = code == 0 or "Certificate not yet due" in out or cert_path.is_file()
        else:
            ssl_ok = True
        if cert_path.is_file():
            site.write_text(nginx_config(host, webroot, ssl=True), encoding="utf-8")
            code, out = _run("nginx -t && systemctl reload nginx")
            if code != 0:
                raise RuntimeError(f"nginx ssl: {out[:200]}")
            ssl_ok = True
        else:
            ssl_ok = False

    _set_env_var("PUBLIC_BASE_URL", base_https)
    _set_env_var("ORDER_PORTAL_URL", f"{base_https}/bestellen")
    _merge_cors(host)
    _run("systemctl restart snack-api")

    k.setdefault("urls", {})
    k["urls"]["subdomain"] = sub
    k["urls"]["demo_url"] = f"https://{DEMO_SUBDOMAIN}.{AGENCY_DOMAIN}/"
    k["urls"]["onboarding_url"] = f"{base_https}/onboarding?k={kid}"
    k["urls"]["test_hauptseite"] = f"{base_https}/"
    k["urls"]["test_bestellen"] = f"{base_https}/bestellen"
    k["urls"]["test_admin"] = f"{base_https}/admin"
    if ssl_ok:
        k["urls"]["ssl"] = True
    save_kunde(k, kpath)

    code, _ = _run(f'curl -s -o /dev/null -w "%{{http_code}}" -H "Host: {host}" http://127.0.0.1/')
    return {
        "ok": True,
        "host": host,
        "url": base_https,
        "webroot": webroot,
        "ssl": ssl_ok,
        "http_check": code,
    }


def _slugify(s: str) -> str:
    import re
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:24]

# -*- coding: utf-8 -*-
"""Nach Cursor-Cloud-Agent: Änderungen vom GitHub-Repo auf web-01 ziehen.

Voraussetzung: GITHUB_TOKEN (Repo-Lesen) in cursor/deploy secrets.
Ohne Token: klarer Hinweis, kein Blind-Deploy.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

log = logging.getLogger("nils_git_deploy")

APP_ROOT = Path("/root/app")
MIRROR = Path(os.getenv("NILS_GIT_MIRROR", "/root/repos/webschmiede-server"))
WEBROOT = Path(os.getenv("NILS_WEBROOT", "/var/www/snackhouse-mechernich"))

# Nie Secrets aus dem Repo überschreiben
SKIP_NAMES = {
    ".env",
    "deploy.secrets.local",
    "requesty.secrets.local",
    "cursor.secrets.local",
    "n8n-credentials.local.txt",
}


def _env(name: str, default: str = "") -> str:
    v = (os.environ.get(name) or "").strip()
    if v:
        return v
    try:
        import nils_cursor_bridge as bridge

        return bridge._env(name, default) or default
    except Exception:
        return default


def auto_deploy_enabled() -> bool:
    flag = (_env("NILS_CURSOR_AUTO_DEPLOY", "1") or "1").lower()
    return flag not in ("0", "false", "no", "off")


def github_token() -> str:
    return _env("GITHUB_TOKEN") or _env("GH_TOKEN") or _env("CURSOR_GITHUB_TOKEN")


def _repo_slug(url: str) -> str:
    """https://github.com/org/repo.git → org/repo"""
    u = (url or "").strip().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    if "github.com" in u:
        path = urlparse(u).path.strip("/")
        parts = path.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    return ""


def _auth_clone_url(repo_url: str) -> str:
    token = github_token()
    slug = _repo_slug(repo_url)
    if token and slug:
        return f"https://x-access-token:{token}@github.com/{slug}.git"
    return repo_url


def _run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 180) -> dict[str, Any]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": p.returncode == 0,
            "code": p.returncode,
            "out": (p.stdout or "")[-2000],
            "err": (p.stderr or "")[-2000],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def ensure_mirror(repo_url: str, ref: str = "main") -> dict[str, Any]:
    if not github_token():
        return {
            "ok": False,
            "error": "no_github_token",
            "text": (
                "Auto-Deploy braucht einmalig GITHUB_TOKEN (Repo read) "
                "in cursor.secrets.local oder deploy.secrets.local. "
                "Ohne Token: Cursor fertig → von Laptop nach Merge `python deploy.py`."
            ),
        }
    MIRROR.parent.mkdir(parents=True, exist_ok=True)
    auth = _auth_clone_url(repo_url)
    if not (MIRROR / ".git").is_dir():
        r = _run(["git", "clone", "--depth", "50", auth, str(MIRROR)], timeout=300)
        if not r.get("ok"):
            return {"ok": False, "error": "clone_failed", "detail": r.get("err") or r.get("error")}
    else:
        _run(["git", "remote", "set-url", "origin", auth], cwd=MIRROR)
        r = _run(["git", "fetch", "--all", "--prune"], cwd=MIRROR, timeout=180)
        if not r.get("ok"):
            return {"ok": False, "error": "fetch_failed", "detail": r.get("err") or r.get("error")}
    # Prefer requested ref, then origin/ref, then main
    candidates = []
    if ref:
        candidates.extend([ref, f"origin/{ref}" if not ref.startswith("origin/") else ref])
    candidates.extend(["main", "master", "origin/main", "origin/master"])
    for candidate in candidates:
        c = _run(["git", "checkout", "-f", candidate], cwd=MIRROR)
        if c.get("ok"):
            _run(["git", "pull", "--ff-only", "origin", candidate.replace("origin/", "")], cwd=MIRROR)
            return {"ok": True, "ref": candidate, "mirror": str(MIRROR)}
    return {"ok": False, "error": "checkout_failed", "detail": f"ref={ref}"}


def _should_skip(path: Path) -> bool:
    name = path.name
    if name in SKIP_NAMES:
        return True
    if name.endswith(".local") or name.endswith(".local.txt"):
        return True
    if "__pycache__" in path.parts or path.suffix == ".pyc":
        return True
    return False


def sync_app_from_mirror() -> dict[str, Any]:
    """Kopiert app/ und kunden/ aus Mirror nach /root/app (ohne Secrets)."""
    if not APP_ROOT.is_dir():
        return {"ok": False, "error": "app_root_missing"}
    src_app = MIRROR / "app"
    if not src_app.is_dir():
        # Repo root might already be app layout
        src_app = MIRROR
    copied = 0
    for sub in ("backend", "static", "jarvis"):
        s = src_app / sub
        if not s.is_dir():
            continue
        d = APP_ROOT / sub
        d.mkdir(parents=True, exist_ok=True)
        for root, dirs, files in os.walk(s):
            root_p = Path(root)
            rel = root_p.relative_to(s)
            # prune
            dirs[:] = [x for x in dirs if x != "__pycache__" and not x.startswith(".")]
            dest_dir = d / rel
            dest_dir.mkdir(parents=True, exist_ok=True)
            for f in files:
                sp = root_p / f
                if _should_skip(sp):
                    continue
                dp = dest_dir / f
                shutil.copy2(sp, dp)
                copied += 1
    # kunden json
    src_k = MIRROR / "kunden"
    if src_k.is_dir():
        dest_k = APP_ROOT / "kunden"
        dest_k.mkdir(parents=True, exist_ok=True)
        for f in src_k.glob("*.json"):
            shutil.copy2(f, dest_k / f.name)
            copied += 1
    return {"ok": True, "copied": copied}


def refresh_webroot() -> dict[str, Any]:
    static = APP_ROOT / "static"
    if not static.is_dir() or not WEBROOT.is_dir():
        return {"ok": False, "error": "webroot_or_static_missing"}
    # Nur Dateien, keine Secrets
    n = 0
    for f in static.rglob("*"):
        if not f.is_file() or _should_skip(f):
            continue
        rel = f.relative_to(static)
        dest = WEBROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        n += 1
    return {"ok": True, "files": n}


def restart_api() -> dict[str, Any]:
    return _run(["systemctl", "restart", "snack-api"], timeout=60)


def _pr_head_ref(pr_url: str | None) -> str | None:
    """https://github.com/org/repo/pull/12 → pull/12/head via API."""
    if not pr_url or "/pull/" not in pr_url:
        return None
    token = github_token()
    if not token:
        return None
    try:
        import json
        import re
        import urllib.request

        m = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
        if not m:
            return None
        org, repo, num = m.group(1), m.group(2), m.group(3)
        req = urllib.request.Request(
            f"https://api.github.com/repos/{org}/{repo}/pulls/{num}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "WebschmiedeNilsDeploy/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        ref = ((data.get("head") or {}).get("ref") or "").strip()
        return ref or None
    except Exception as e:
        log.warning("pr head: %s", e)
        return None


def deploy_after_cursor(
    *,
    repo_url: str,
    ref: str = "main",
    pr_url: str | None = None,
) -> dict[str, Any]:
    """Vollständiger Pull+Sync+Restart. Nur wenn Auto-Deploy an."""
    if not auto_deploy_enabled():
        return {
            "ok": False,
            "skipped": True,
            "text": "Auto-Deploy aus (NILS_CURSOR_AUTO_DEPLOY=0).",
        }
    steps: list[str] = []
    pull_ref = _pr_head_ref(pr_url) or ref or "main"
    mir = ensure_mirror(repo_url, ref=pull_ref)
    if not mir.get("ok"):
        return {
            "ok": False,
            "error": mir.get("error"),
            "text": mir.get("text") or mir.get("detail") or "Git-Mirror fehlgeschlagen",
            "pr_url": pr_url,
        }
    steps.append(f"mirror@{mir.get('ref')}")
    sync = sync_app_from_mirror()
    if not sync.get("ok"):
        return {"ok": False, "error": sync.get("error"), "text": "Sync fehlgeschlagen", "steps": steps}
    steps.append(f"copied={sync.get('copied')}")
    wr = refresh_webroot()
    if wr.get("ok"):
        steps.append(f"webroot={wr.get('files')}")
    api = restart_api()
    steps.append("api_restart=" + ("ok" if api.get("ok") else "fail"))
    ok = bool(api.get("ok"))
    text = (
        f"Deploy nach Cursor {'OK' if ok else 'teilweise'}. "
        f"Schritte: {', '.join(steps)}."
        + (f" PR: {pr_url}" if pr_url else "")
    )
    return {"ok": ok, "text": text, "steps": steps, "pr_url": pr_url, "ref": pull_ref}

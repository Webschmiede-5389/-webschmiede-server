# -*- coding: utf-8 -*-
"""Cursor Canary safety: allowlist, path hardening, prompt policy, resources."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

DEFAULT_WORKSPACE_ROOT = Path(
    os.getenv("NILS_CANARY_WORKSPACE_ROOT", "/opt/webschmiede/nils-canary-workspace")
)

DEFAULT_ALLOWED_REPOS = ("cursor-canary-repo",)

FORBIDDEN_WORK_ROOTS = (
    Path("/root"),
    Path("/etc"),
    Path("/var/lib"),
    Path("/boot"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
)

_DANGEROUS_RES = (
    re.compile(r"(?i)\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)*(/|~|\.\.)"),
    re.compile(r"(?i)\brm\s+-rf\b"),
    re.compile(r"(?i)\b(delete|drop)\s+(database|table|schema)\b"),
    re.compile(r"(?i)\bdocker\s+(volume\s+)?(rm|prune)\b"),
    re.compile(r"(?i)\bgit\s+push\s+.*--force\b|\bgit\s+push\s+-f\b"),
    re.compile(r"(?i)\bgit\s+reset\s+--hard\b"),
    re.compile(r"(?i)/etc(/|$)"),
    re.compile(r"(?i)\.env(\.|$|\s)|deploy\.secrets|cursor\.secrets|vapid\.json"),
    re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\s*[:=]"),
    re.compile(r"(?i)\b(prod(uction)?\s+deploy|live\s+schalten|systemctl\s+.*restart\b)"),
    re.compile(r"(?i)\bchmod\s+777\b|\bchown\s+-R\s+root\b"),
    re.compile(r"(?i)\bcurl\s+.*\|\s*(ba)?sh\b"),
    re.compile(r"(?i)\bsudo\b|\bsu\s+-"),
)

ALLOWED_VARIANTS = frozenset(
    {"readonly", "writefile", "branchedit", "fail", "timeout", "long"}
)


def workspace_root() -> Path:
    return Path(os.getenv("NILS_CANARY_WORKSPACE_ROOT", str(DEFAULT_WORKSPACE_ROOT)))


def allowlist() -> list[Path]:
    raw = os.getenv("NILS_CANARY_REPO_ALLOWLIST") or ",".join(DEFAULT_ALLOWED_REPOS)
    root = workspace_root().resolve()
    out: list[Path] = []
    for part in raw.replace(";", ",").split(","):
        p = part.strip()
        if not p:
            continue
        cand = Path(p)
        if not cand.is_absolute():
            cand = root / cand
        try:
            out.append(Path(os.path.realpath(str(cand.resolve(strict=False)))))
        except Exception:
            continue
    return out


def is_under(child: Path, parent: Path) -> bool:
    try:
        Path(os.path.realpath(str(child))).relative_to(Path(os.path.realpath(str(parent))))
        return True
    except Exception:
        return False


def validate_workdir(path: str | Path) -> dict[str, Any]:
    try:
        resolved = Path(path).resolve(strict=False)
        real = Path(os.path.realpath(str(resolved)))
    except Exception as e:
        return {"ok": False, "error": f"path_resolve_failed:{e}"}

    ws = Path(os.path.realpath(str(workspace_root().resolve())))
    if real != ws and not is_under(real, ws):
        return {"ok": False, "error": "outside_workspace_root", "path": str(real)}

    for fr in FORBIDDEN_WORK_ROOTS:
        fr_r = Path(os.path.realpath(str(fr)))
        if real == fr_r:
            return {"ok": False, "error": f"forbidden_workdir:{fr}"}

    allowed = allowlist()
    if not any(real == a or is_under(real, a) for a in allowed):
        return {"ok": False, "error": "not_in_allowlist", "path": str(real)}

    if not real.is_dir():
        return {"ok": False, "error": "not_a_directory"}

    return {"ok": True, "path": str(real), "realpath": str(real)}


def scan_task_text(text: str) -> dict[str, Any]:
    t = text or ""
    hits: list[str] = []
    for rx in _DANGEROUS_RES:
        if rx.search(t):
            hits.append(rx.pattern[:80])
    if hits:
        return {"ok": False, "error": "dangerous_intent", "hits": hits[:5]}
    if ".." in t and re.search(r"\.\.(/|\\)", t):
        return {"ok": False, "error": "path_traversal_in_task"}
    return {"ok": True}


def resource_limits() -> dict[str, Any]:
    return {
        "max_runtime_seconds": int(os.getenv("NILS_CANARY_CURSOR_TIMEOUT", "600") or 600),
        "max_log_bytes": int(os.getenv("NILS_CANARY_MAX_LOG_BYTES", "200000") or 200000),
        "max_result_bytes": int(os.getenv("NILS_CANARY_MAX_RESULT_BYTES", "100000") or 100000),
        "max_parallel": 1,
        "min_disk_free_mb": int(os.getenv("NILS_CANARY_MIN_DISK_MB", "1024") or 1024),
        "max_child_processes": int(os.getenv("NILS_CANARY_MAX_CHILDREN", "32") or 32),
        "grace_seconds": int(os.getenv("NILS_CANARY_KILL_GRACE_SECONDS", "8") or 8),
    }


def disk_ok(path: Path | None = None) -> dict[str, Any]:
    p = path or workspace_root()
    usage = shutil.disk_usage(str(p))
    free_mb = usage.free // (1024 * 1024)
    lim = resource_limits()["min_disk_free_mb"]
    return {
        "ok": free_mb >= lim,
        "free_mb": free_mb,
        "min_mb": lim,
        "total": usage.total,
        "used": usage.used,
    }


def cursor_allowed() -> bool:
    return (os.getenv("NILS_CANARY_ALLOW_CURSOR", "0") or "0").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def default_repo_path() -> Path:
    root = workspace_root()
    name = (os.getenv("NILS_CANARY_DEFAULT_REPO") or DEFAULT_ALLOWED_REPOS[0]).strip()
    return Path(os.path.realpath(str((root / name).resolve())))

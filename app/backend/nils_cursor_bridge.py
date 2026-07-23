# -*- coding: utf-8 -*-
"""Nils ↔ Cursor Cloud Agent Bridge.

Ziel: Unterwegs per Telegram dasselbe wie im Cursor-Chat:
Website/App bauen, Repo ändern, PR öffnen.

Braucht: CURSOR_API_KEY (Dashboard → Integrations) + GitHub-Repo an Cursor.
Ohne Key: klarer Hinweis + Workorder-Handoff.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("nils_cursor_bridge")

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO = "https://github.com/Webschmiede-5389/-webschmiede-server.git"
_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


def _env(name: str, default: str = "") -> str:
    v = (os.environ.get(name) or "").strip()
    if v:
        return v
    # requesty / deploy secrets oft in Dateien am App-Root
    for fname in (
        "cursor.secrets.local",
        "requesty.secrets.local",
        "deploy.secrets.local",
    ):
        for base in (ROOT, ROOT / "app", Path("/root/app")):
            p = base / fname
            if not p.is_file():
                continue
            try:
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, val = line.partition("=")
                    if k.strip() == name:
                        return val.strip().strip('"').strip("'")
            except Exception:
                continue
    return default


def configured() -> bool:
    return bool(_env("CURSOR_API_KEY"))


def enabled() -> bool:
    flag = (_env("NILS_CURSOR_BRIDGE", "1") or "1").lower()
    return flag not in ("0", "false", "no", "off") and configured()


def repo_url() -> str:
    return _env("CURSOR_REPO_URL", DEFAULT_REPO) or DEFAULT_REPO


def repo_ref() -> str:
    return _env("CURSOR_REPO_REF", "main") or "main"


def status_text() -> str:
    if not configured():
        return (
            "Cursor-Bridge: noch kein CURSOR_API_KEY.\n"
            "1) Cursor Dashboard -> Integrations -> User API Key\n"
            "2) In cursor.secrets.local oder requesty.secrets.local: CURSOR_API_KEY=...\n"
            "3) GitHub-Repo an Cursor haengen (Cloud Agents)\n"
            f"Repo-Ziel: {repo_url()}"
        )
    return (
        f"Cursor-Bridge bereit.\n"
        f"Repo: {repo_url()} @ {repo_ref()}\n"
        "Telegram: baue/optimiere Website … → Freigabe → Cursor → Auto-Deploy.\n"
        "GITHUB_TOKEN einmalig für Live-Pull. Ohne Token: Deploy von Laptop."
    )


def _prompt_wrap(task: str, *, workorder_id: str = "") -> str:
    ux = ""
    try:
        import nils_ux_gate as uxgate

        ux = "\n" + uxgate.policy_for_prompt(short=False) + "\n"
    except Exception:
        ux = (
            "\nUX/FACT-GATE: Vor „fertig“ Fakten, Buttons/Links, Abstände, "
            "Mobile (~390px), Flow und Funktion prüfen.\n"
        )
    return (
        "Du bist der Coding-Agent für Webschmiede (Christian / Nils-Bridge).\n"
        "Arbeite im Repo wie im Cursor-IDE-Chat. Deutsch in PR-Beschreibung.\n"
        "Kein GHL. Design: Dunkel + Gold #C9A84C, Bunny Fonts (oder Kunden-CI).\n"
        "Keine Secrets committen. Keine bezahlten Käufe.\n"
        "Nach Freigabe darf Nils die Änderungen auf den Live-Server ziehen (git pull + Deploy).\n"
        "HALLUZINATIONS-VERBOT: Nichts erfinden was nicht im Repo/Auftrag steht. "
        "Unklar → TODO im Code/PR, keine Fake-APIs oder Fake-Kunden.\n"
        f"{ux}"
        "Wenn die Arbeit inhaltlich durch ist: Gate-Report (Fakten/Links/Mobile/Flow). "
        "Nur wenn Gate ok: als umsetzungsbereit bezeichnen. Sonst offene Punkte listen.\n"
        f"Workorder: {workorder_id or '–'}\n\n"
        f"## Auftrag von Christian (Telegram)\n\n{task.strip()}"
    )


def launch_cloud_agent(
    task: str,
    *,
    workorder_id: str = "",
    auto_create_pr: bool = True,
    auto_deploy: bool | None = None,
    notify: bool = True,
    model: str | None = None,
) -> dict[str, Any]:
    """Startet Cursor Cloud Agent (blockiert kurz beim Create, Run im Thread)."""
    if not enabled():
        return {
            "ok": False,
            "error": "not_configured",
            "text": status_text(),
        }
    task = (task or "").strip()
    if len(task) < 8:
        return {"ok": False, "error": "task_too_short", "text": "Auftrag zu kurz."}

    do_deploy = auto_deploy_enabled_flag() if auto_deploy is None else bool(auto_deploy)

    api_key = _env("CURSOR_API_KEY")
    model_id = model or _env("CURSOR_AGENT_MODEL", "composer-2.5") or "composer-2.5"
    prompt = _prompt_wrap(task, workorder_id=workorder_id)

    try:
        from cursor_sdk import Agent, CloudAgentOptions, CloudRepository
    except ImportError:
        return {
            "ok": False,
            "error": "sdk_missing",
            "text": (
                "cursor-sdk fehlt auf dem Server. "
                "pip install cursor-sdk im venv, dann snack-api neu."
            ),
        }

    try:
        agent = Agent.create(
            model=model_id,
            api_key=api_key,
            cloud=CloudAgentOptions(
                repos=[
                    CloudRepository(
                        url=repo_url(),
                        starting_ref=repo_ref(),
                    )
                ],
                auto_create_pr=bool(auto_create_pr),
            ),
        )
    except Exception as e:
        log.exception("cursor Agent.create")
        return {
            "ok": False,
            "error": "create_failed",
            "text": f"Cursor-Agent startet nicht: {e}",
        }

    agent_id = getattr(agent, "agent_id", None) or getattr(agent, "id", None) or ""
    job_id = f"cj_{int(time.time())}_{str(agent_id)[-6:] or 'x'}"

    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "agent_id": str(agent_id),
            "workorder_id": workorder_id,
            "task": task[:500],
            "status": "running",
            "started_at": time.time(),
            "result": None,
            "error": None,
            "pr_url": None,
            "auto_deploy": do_deploy,
            "deploy": None,
        }

    try:
        import nils_eta as eta

        eta.register_job(job_id, kind="cursor", task=task, max_minutes=eta.max_job_minutes())
    except Exception:
        log.exception("register cursor job eta")

    def _notify(msg: str) -> None:
        if not notify:
            return
        try:
            import telegram_ops as tg

            tg.notify_owner(msg[:3800])
        except Exception:
            log.exception("cursor notify")

    def _run() -> None:
        try:
            run = agent.send(prompt)
            chunks: list[str] = []
            try:
                for message in run.messages():
                    if getattr(message, "type", None) == "assistant":
                        content = getattr(getattr(message, "message", None), "content", None)
                        if isinstance(content, list):
                            for block in content:
                                if getattr(block, "type", None) == "text":
                                    chunks.append(getattr(block, "text", "") or "")
                        elif isinstance(content, str):
                            chunks.append(content)
            except Exception:
                pass
            result = run.wait()
            status = getattr(result, "status", None) or "unknown"
            summary = "".join(chunks).strip() or str(getattr(result, "result", "") or "")[:2500]
            pr_url = None
            for attr in ("pr_url", "pull_request_url", "url"):
                if hasattr(result, attr) and getattr(result, attr):
                    pr_url = str(getattr(result, attr))
                    break
            # branch hint from result if any
            branch = repo_ref()
            for attr in ("branch", "branch_name", "ref"):
                if hasattr(result, attr) and getattr(result, attr):
                    branch = str(getattr(result, attr))
                    break

            ok_status = status in ("finished", "completed", "success", "ok")
            with _LOCK:
                job = _JOBS.get(job_id) or {}
                job["status"] = "done" if ok_status else str(status)
                if status == "error":
                    job["status"] = "error"
                job["result"] = summary[:3500]
                job["pr_url"] = pr_url
                job["branch"] = branch
                job["finished_at"] = time.time()
                _JOBS[job_id] = job

            deploy_info = None
            if ok_status and do_deploy:
                try:
                    import nils_git_deploy as gd

                    deploy_info = gd.deploy_after_cursor(
                        repo_url=repo_url(),
                        ref=branch or repo_ref(),
                        pr_url=pr_url,
                    )
                except Exception as e:
                    log.exception("auto deploy")
                    deploy_info = {"ok": False, "error": str(e)[:300]}
                with _LOCK:
                    job = _JOBS.get(job_id) or {}
                    job["deploy"] = deploy_info
                    _JOBS[job_id] = job

            msg = (
                f"Cursor-Job {job_id} fertig ({'OK' if ok_status else status}).\n"
                f"Auftrag: {task[:200]}\n"
            )
            if pr_url:
                msg += f"PR: {pr_url}\n"
            if summary:
                msg += "\n" + summary[:1200] + "\n"
            if deploy_info:
                msg += "\n" + str(deploy_info.get("text") or deploy_info)[:800]
            elif do_deploy and ok_status:
                msg += "\nAuto-Deploy: kein Ergebnis (siehe Logs)."
            _notify(msg)
            try:
                import nils_eta as eta

                eta.finish_job(job_id, status="done" if ok_status else "error", detail=(summary or "")[:200])
            except Exception:
                pass
        except Exception as e:
            log.exception("cursor agent run")
            with _LOCK:
                job = _JOBS.get(job_id) or {}
                job["status"] = "error"
                job["error"] = str(e)[:500]
                job["finished_at"] = time.time()
                _JOBS[job_id] = job
            _notify(f"Cursor-Job {job_id} Fehler: {e}")
            try:
                import nils_eta as eta

                eta.finish_job(job_id, status="error", detail=str(e)[:200])
            except Exception:
                pass
        finally:
            try:
                close = getattr(agent, "close", None) or getattr(agent, "__exit__", None)
                if callable(close) and close.__name__ == "close":
                    agent.close()
            except Exception:
                pass

    threading.Thread(target=_run, name=f"cursor-{job_id}", daemon=True).start()

    deploy_hint = (
        "Danach ziehe ich die Änderungen auf den Live-Server (Auto-Deploy), "
        "sobald Cursor fertig ist. Braucht GITHUB_TOKEN einmalig in den Secrets."
        if do_deploy
        else "Auto-Deploy ist aus."
    )
    return {
        "ok": True,
        "job_id": job_id,
        "agent_id": str(agent_id),
        "text": (
            f"Cursor-Cloud-Agent gestartet (wie im IDE).\n"
            f"Job: {job_id}\n"
            f"Agent: {agent_id or '–'}\n"
            f"Repo: {repo_url()} @{repo_ref()}\n"
            f"PR: {'ja' if auto_create_pr else 'nein'}\n"
            f"{deploy_hint}\n\n"
            f"Status später: „cursor status {job_id}“\n"
            f"Auftrag: {task[:280]}"
        ),
        "task": task[:500],
        "auto_deploy": do_deploy,
    }


def auto_deploy_enabled_flag() -> bool:
    try:
        import nils_git_deploy as gd

        return gd.auto_deploy_enabled()
    except Exception:
        flag = (_env("NILS_CURSOR_AUTO_DEPLOY", "1") or "1").lower()
        return flag not in ("0", "false", "no", "off")


def get_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        return dict(_JOBS.get(job_id) or {}) or None


def job_status_text(job_id: str = "") -> str:
    jid = (job_id or "").strip()
    if not jid:
        with _LOCK:
            items = list(_JOBS.values())[-5:]
        if not items:
            return "Keine Cursor-Jobs in diesem Prozess (nach Restart leer). " + status_text()
        lines = ["Letzte Cursor-Jobs:"]
        for j in items:
            lines.append(
                f"• {j.get('job_id')}: {j.get('status')} · {(j.get('task') or '')[:60]}"
            )
        return "\n".join(lines)

    job = get_job(jid)
    if not job:
        # try match by suffix
        with _LOCK:
            for k, v in _JOBS.items():
                if jid in k or jid == str(v.get("agent_id") or ""):
                    job = dict(v)
                    break
    if not job:
        return f"Job {jid} nicht gefunden (vielleicht nach Restart weg). " + status_text()

    lines = [
        f"Cursor-Job {job.get('job_id')}",
        f"Status: {job.get('status')}",
        f"Agent: {job.get('agent_id') or '–'}",
    ]
    if job.get("pr_url"):
        lines.append(f"PR: {job['pr_url']}")
    if job.get("deploy"):
        lines.append("Deploy: " + str((job.get("deploy") or {}).get("text") or job.get("deploy"))[:400])
    if job.get("error"):
        lines.append(f"Fehler: {job['error']}")
    if job.get("result"):
        lines.append("\n" + str(job["result"])[:2000])
    return "\n".join(lines)


CODING_RE = re.compile(
    r"\b("
    r"programmier|programmiere|app\s+bauen|website\s+bauen|website\s+erstell|"
    r"landing\s+bauen|portal\s+bauen|dashboard\s+bauen|code\s+schreiben|"
    r"feature\s+bauen|implementier|cursor:|wie\s+in\s+cursor|"
    r"repo\s+änder|im\s+repo|html\s+seite\s+bau|react\s+seite|"
    r"anwendung\s+bau|fullstack|neue\s+seite\s+anlegen"
    r")\b",
    re.I,
)


def looks_like_coding_task(text: str) -> bool:
    t = text or ""
    if CODING_RE.search(t):
        return True
    low = t.lower()
    if "website" in low and any(x in low for x in ("bau", "mach", "erstell", "programmier", "code")):
        return True
    if "dashboard" in low and any(x in low for x in ("bau", "mach", "erstell", "programmier")):
        return True
    return False

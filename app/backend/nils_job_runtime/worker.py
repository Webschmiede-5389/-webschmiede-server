# -*- coding: utf-8 -*-
"""Worker task handlers + main loop."""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
from typing import Any, Callable

from nils_job_runtime import notify, queue, store

log = logging.getLogger("nils_job_runtime.worker")

_STOP = False


def _request_stop(*_a: Any) -> None:
    global _STOP
    _STOP = True


Handler = Callable[[dict[str, Any], str], dict[str, Any]]


def handle_echo(job: dict[str, Any], wid: str) -> dict[str, Any]:
    queue.heartbeat(job["job_id"], wid=wid, current_step="echo", progress_message="echo")
    return {"result_reference": f"echo:{job.get('task_summary','')[:80]}"}


def handle_steps(job: dict[str, Any], wid: str) -> dict[str, Any]:
    total = 5
    jid = job["job_id"]
    for i in range(1, total + 1):
        if _STOP:
            raise RuntimeError("worker_stopping")
        queue.heartbeat(
            jid,
            wid=wid,
            current_step=f"step_{i}",
            progress_current=i,
            progress_total=total,
            progress_message=f"Schrittschritt {i}/{total}",
        )
        job2 = store.get_job(jid) or job
        if i in (1, 3, 5):
            notify.notify_status(job2, "progress")
        time.sleep(float(os.getenv("NILS_TEST_STEP_SLEEP", "0.4")))
    return {"result_reference": f"steps:{total}"}


def handle_fail(job: dict[str, Any], wid: str) -> dict[str, Any]:
    queue.heartbeat(job["job_id"], wid=wid, current_step="fail")
    raise RuntimeError("controlled_test_exception")


def handle_block(job: dict[str, Any], wid: str) -> dict[str, Any]:
    """Blocks until timeout (for TEST G)."""
    jid = job["job_id"]
    # short timeout expected on job
    while not _STOP:
        queue.heartbeat(jid, wid=wid, current_step="blocked", progress_message="block")
        time.sleep(2)
        # rely on recover_stale_leases / timeout in outer loop checking started_at
        job2 = store.get_job(jid)
        if not job2 or job2["status"] != "RUNNING":
            break
        started = queue._parse_ts(job2.get("started_at"))
        if started and time.time() - started > int(job2.get("timeout_seconds") or 30):
            raise TimeoutError("task_timeout")
    raise TimeoutError("task_timeout")


def handle_heartbeat_long(job: dict[str, Any], wid: str) -> dict[str, Any]:
    jid = job["job_id"]
    rounds = int(os.getenv("NILS_TEST_HB_ROUNDS", "4") or 4)
    for i in range(1, rounds + 1):
        if _STOP:
            raise RuntimeError("worker_stopping")
        queue.heartbeat(
            jid,
            wid=wid,
            current_step=f"hb_{i}",
            progress_current=i,
            progress_total=rounds,
            progress_message=f"heartbeat round {i}",
        )
        time.sleep(float(os.getenv("NILS_TEST_HB_SLEEP", "1.0")))
    return {"result_reference": f"hb:{rounds}"}


def handle_external_proc(job: dict[str, Any], wid: str) -> dict[str, Any]:
    """Honest external process tracking via real subprocess PID (no fake %)."""
    import subprocess
    from pathlib import Path

    jid = job["job_id"]
    script = (
        "import time,sys\n"
        "for i in range(1,6):\n"
        "  print(f'STEP {i}/5', flush=True)\n"
        "  time.sleep(0.8)\n"
        "print('DONE', flush=True)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    started = store.utc_now()
    store.update_fields(
        jid,
        external_kind="subprocess",
        external_ref=f"python:-c:{proc.pid}",
        external_pid=proc.pid,
        external_started_at=started,
        external_last_step="process_started",
        current_step="external_started",
        progress_message="Externer Prozess gestartet (kein Teilfortschritt-Prozent)",
    )
    queue.heartbeat(
        jid,
        wid=wid,
        current_step="external_started",
        progress_message="Prozess läuft, kein messbarer Teilfortschritt",
    )
    last_step = "process_started"
    assert proc.stdout is not None
    while True:
        if _STOP:
            proc.kill()
            raise RuntimeError("worker_stopping")
        line = proc.stdout.readline()
        if line:
            last_step = store.redact(line.strip(), 120)
            # Only report proven lines — never invent percent
            store.update_fields(jid, external_last_step=last_step)
            queue.heartbeat(
                jid,
                wid=wid,
                current_step="external_running",
                progress_message=f"letzter nachgewiesener Schritt: {last_step}",
            )
            if "STEP" in last_step:
                notify.notify_status(store.get_job(jid) or job, "progress")
        rc = proc.poll()
        if rc is not None:
            finished = store.utc_now()
            store.update_fields(
                jid,
                external_exit_code=rc,
                external_finished_at=finished,
                external_last_step=last_step,
            )
            if rc != 0:
                raise RuntimeError(f"external_exit_{rc}")
            return {
                "result_reference": f"external_pid={proc.pid};exit={rc};last={last_step}"
            }
        # PID liveness check
        if not _pid_alive(proc.pid) and proc.poll() is None:
            raise RuntimeError("external_pid_vanished")
        time.sleep(0.2)


def handle_cursor_probe(job: dict[str, Any], wid: str) -> dict[str, Any]:
    """Honest Cursor probe — no invented percentages."""
    jid = job["job_id"]
    allow = (os.getenv("NILS_CANARY_ALLOW_CURSOR", "0") or "0").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if not allow:
        store.update_fields(
            jid,
            external_kind="cursor",
            external_last_step="cursor_probe_disabled",
            progress_message="Cursor-Probe deaktiviert (NILS_CANARY_ALLOW_CURSOR=0)",
        )
        raise RuntimeError("cursor_probe_disabled")

    try:
        import nils_cursor_bridge as bridge
    except Exception as e:
        raise RuntimeError(f"cursor_bridge_import:{e}") from e

    if not bridge.enabled():
        raise RuntimeError("cursor_not_configured")

    queue.heartbeat(
        jid,
        wid=wid,
        current_step="cursor_launch",
        progress_message="Cursor-Auftrag wird gestartet (kein Teilfortschritt)",
    )
    # Tiny canary prompt — no repo mutations requested
    task = (
        "CANARY-TEST: Antworte ausschließlich mit dem Text CANARY_OK. "
        "Keine Dateiänderungen, kein PR, keine Commits."
    )
    launch = bridge.launch_cloud_agent(
        task,
        workorder_id=f"canary:{jid}",
        auto_create_pr=False,
        auto_deploy=False,
        notify=False,
    )
    if not launch.get("ok"):
        raise RuntimeError(store.redact(str(launch.get("error") or launch.get("text") or "launch_failed"), 120))

    cursor_job_id = str(launch.get("job_id") or "")
    agent_id = str(launch.get("agent_id") or "")
    store.update_fields(
        jid,
        external_kind="cursor",
        external_ref=f"cursor_job={cursor_job_id};agent={agent_id}",
        external_started_at=store.utc_now(),
        external_last_step="cursor_started",
        progress_message="Cursor-Prozess gestartet, kein messbarer Teilfortschritt",
    )
    notify.notify_status(store.get_job(jid) or job, "progress")

    # Poll bridge memory/status honestly until terminal or timeout
    deadline = time.time() + int(job.get("timeout_seconds") or 600)
    last = "cursor_started"
    while time.time() < deadline:
        if _STOP:
            raise RuntimeError("worker_stopping")
        info = bridge.get_job(cursor_job_id) if cursor_job_id else None
        if info:
            st = str(info.get("status") or "")
            last = f"cursor_status={st}"
            store.update_fields(jid, external_last_step=last)
            queue.heartbeat(
                jid,
                wid=wid,
                current_step="cursor_running",
                progress_message=(
                    "Cursor läuft, kein messbarer Teilfortschritt"
                    if st in ("running", "RUNNING", "")
                    else f"Cursor-Status nachgewiesen: {st}"
                ),
            )
            if st in ("done", "error", "FAILED", "finished", "completed", "success", "ok"):
                store.update_fields(
                    jid,
                    external_finished_at=store.utc_now(),
                    external_exit_code=0 if st in ("done", "finished", "completed", "success", "ok") else 1,
                )
                if st == "error":
                    raise RuntimeError("cursor_finished_error")
                return {
                    "result_reference": f"cursor_job={cursor_job_id};agent={agent_id};status={st}"
                }
        else:
            queue.heartbeat(
                jid,
                wid=wid,
                current_step="cursor_unknown",
                progress_message="Cursor-Referenz gesetzt, Live-Status im Bridge-RAM nicht mehr sichtbar",
            )
        time.sleep(3)
    raise TimeoutError("cursor_probe_timeout")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def handle_cursor_canary(job: dict[str, Any], wid: str) -> dict[str, Any]:
    from nils_job_runtime.cursor_handler import handle_cursor_canary as _h

    return _h(job, wid)


def handle_owner_job(job: dict[str, Any], wid: str) -> dict[str, Any]:
    from nils_job_runtime.owner_handler import handle_owner_job as _h

    return _h(job, wid)


def handle_crm_offer_pdf(job: dict[str, Any], wid: str) -> dict[str, Any]:
    from nils_job_runtime.crm_offer_pdf import execute_pdf_send

    return execute_pdf_send(job, wid)


HANDLERS: dict[str, Handler] = {
    "echo": handle_echo,
    "steps": handle_steps,
    "fail": handle_fail,
    "block": handle_block,
    "heartbeat_long": handle_heartbeat_long,
    "shadow_echo": handle_echo,
    "shadow.echo": handle_echo,  # capability id used by older job shells
    "shadow_steps": handle_steps,
    "external_proc": handle_external_proc,
    "cursor_probe": handle_cursor_probe,
    "cursor_canary": handle_cursor_canary,
    "owner_job": handle_owner_job,
    "crm.offer_pdf_send": handle_crm_offer_pdf,
    "crm.offer_read": handle_echo,  # read is inline; should not normally queue
}


def run_job(job: dict[str, Any], *, wid: str) -> None:
    jid = job["job_id"]
    notify.notify_status(job, "started")
    ttype = (job.get("task_type") or "echo").strip()
    handler = HANDLERS.get(ttype)
    if not handler:
        store.transition(
            jid,
            "FAILED",
            extra={
                "finished_at": store.utc_now(),
                "error_category": "unknown_task_type",
                "error_message_redacted": store.redact(ttype, 80),
                "worker_id": None,
                "lease_expires_at": None,
            },
        )
        notify.notify_status(store.get_job(jid) or job, "failed")
        return

    started = time.time()
    timeout = int(job.get("timeout_seconds") or 900)
    try:
        # cooperative timeout for handlers that don't self-check
        result = handler(job, wid)
        # Handler may have finalized (CANCELLED / STALLED / TIMED_OUT)
        cur = store.get_job(jid)
        if cur and cur.get("status") != "RUNNING":
            return
        if time.time() - started > timeout:
            raise TimeoutError("task_timeout")
        store.transition(
            jid,
            "SUCCEEDED",
            extra={
                "finished_at": store.utc_now(),
                "result_reference": store.redact(str((result or {}).get("result_reference") or ""), 200),
                "worker_id": None,
                "lease_expires_at": None,
                "progress_message": "done",
            },
        )
        notify.notify_status(store.get_job(jid) or job, "succeeded")
    except TimeoutError:
        store.transition(
            jid,
            "TIMED_OUT",
            extra={
                "finished_at": store.utc_now(),
                "error_category": "timeout",
                "error_message_redacted": "task_timeout",
                "worker_id": None,
                "lease_expires_at": None,
            },
        )
        notify.notify_status(store.get_job(jid) or job, "timed_out")
    except RuntimeError as e:
        msg = str(e)
        # Cursor canary: never auto-requeue (would double-start the agent).
        if "worker_stopping_cursor" in msg:
            log.warning("worker stop during cursor job %s — leave RUNNING for reattach/STALL", jid)
            store.update_fields(
                jid,
                worker_id=None,
                # Keep lease short so recover can STALL if observe fails
                lease_expires_at=store.utc_now(),
                error_category="worker_restart_cursor",
                error_message_redacted="cursor_process_left_running_no_double_start",
                progress_message="Worker-Neustart: Cursor-Prozess nicht erneut starten",
            )
            try:
                notify._ops_alert(f"STALLED_PENDING cursor job {jid} after worker stop")
            except Exception:
                pass
            return
        # Cooperative shutdown for non-cursor: requeue (not FAILED).
        if "worker_stopping" in msg:
            log.warning("worker stopping mid-job %s — requeue for resume", jid)
            released = queue.release_for_worker_restart(jid)
            if not released:
                try:
                    store.transition(
                        jid,
                        "STALLED",
                        extra={
                            "error_category": "worker_restart",
                            "error_message_redacted": "shutdown without requeue",
                            "worker_id": None,
                            "lease_expires_at": None,
                        },
                    )
                except Exception:
                    log.exception("shutdown stall fallback %s", jid)
            return
        category = "exception"
        if "RESULT_VALIDATION_FAILED" in msg:
            store.transition(
                jid,
                "RESULT_VALIDATION_FAILED",
                extra={
                    "finished_at": store.utc_now(),
                    "error_category": "result_validation_failed",
                    "error_message_redacted": store.redact(msg, 200),
                    "worker_id": None,
                    "lease_expires_at": None,
                },
            )
            notify.notify_status(store.get_job(jid) or job, "failed")
            return
        elif "security_block" in msg:
            category = "security_block"
        store.transition(
            jid,
            "FAILED",
            extra={
                "finished_at": store.utc_now(),
                "error_category": category,
                "error_message_redacted": store.redact(msg, 200),
                "worker_id": None,
                "lease_expires_at": None,
            },
        )
        notify.notify_status(store.get_job(jid) or job, "failed")
    except Exception as e:
        store.transition(
            jid,
            "FAILED",
            extra={
                "finished_at": store.utc_now(),
                "error_category": "exception",
                "error_message_redacted": store.redact(str(e), 200),
                "worker_id": None,
                "lease_expires_at": None,
            },
        )
        notify.notify_status(store.get_job(jid) or job, "failed")


def run_forever(
    *,
    shadow_only: bool | None = True,
    poll_seconds: float = 1.0,
    live_capabilities: set[str] | list[str] | None = None,
) -> None:
    global _STOP
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    wid = queue.worker_id()
    store.ensure_schema()
    live = live_capabilities
    if live is None:
        raw = os.getenv("NILS_WORKER_LIVE_CAPABILITIES") or ""
        live = {p.strip() for p in raw.replace(";", ",").split(",") if p.strip()}
    log.info(
        "nils job worker start wid=%s shadow_only=%s live_caps=%s",
        wid,
        shadow_only,
        sorted(live) if live else [],
    )
    # recover on boot
    actions = queue.recover_stale_leases(wid=wid)
    for a in actions:
        job = store.get_job(a["job_id"])
        if job and a["action"] in ("STALLED", "STALLED_REQUEUE", "TIMED_OUT"):
            kind = "stalled" if "STALL" in a["action"] else "timed_out"
            try:
                notify.notify_status(job, kind)
            except Exception:
                pass
    while not _STOP:
        try:
            queue.recover_stale_leases(wid=wid)
            job = queue.claim_next(
                wid=wid, shadow_only=shadow_only, live_capabilities=live
            )
            if not job:
                time.sleep(poll_seconds)
                continue
            run_job(job, wid=wid)
        except Exception:
            log.exception("worker loop")
            time.sleep(2)
    log.info("nils job worker stop wid=%s", wid)

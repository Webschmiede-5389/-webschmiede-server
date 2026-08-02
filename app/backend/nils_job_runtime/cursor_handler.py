# -*- coding: utf-8 -*-
"""Worker handler: real Local Cursor Agent canary with process-group honesty."""
from __future__ import annotations

import json
import logging
import os
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from nils_job_runtime import notify, queue, store
from nils_job_runtime import cursor_canary_tasks as tasks
from nils_job_runtime import cursor_proc
from nils_job_runtime import cursor_safety as safety

log = logging.getLogger("nils_job_runtime.cursor_handler")


def _worker_stop_flag() -> bool:
    try:
        from nils_job_runtime import worker as worker_mod
        return bool(getattr(worker_mod, "_STOP", False))
    except Exception:
        return False


def _status_dir(job_id: str) -> Path:
    root = safety.workspace_root() / "_runner_status"
    root.mkdir(parents=True, exist_ok=True)
    return root / job_id


def _read_status(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _finalize_from_status(
    job: dict[str, Any],
    wid: str,
    st: dict[str, Any],
    *,
    proc_returncode: int | None,
) -> dict[str, Any]:
    jid = job["job_id"]
    variant = tasks.parse_variant_from_summary(job.get("task_summary") or "")
    repo = Path(st.get("cwd") or safety.default_repo_path())
    baseline = ""
    meta_path = _status_dir(jid) / "baseline.json"
    if meta_path.is_file():
        try:
            baseline = json.loads(meta_path.read_text(encoding="utf-8")).get("porcelain") or ""
        except Exception:
            baseline = ""

    exit_code = proc_returncode if proc_returncode is not None else st.get("exit_code")
    store.update_fields(
        jid,
        external_exit_code=exit_code,
        external_finished_at=store.utc_now(),
        external_last_step=store.redact(str(st.get("last_step") or st.get("phase") or ""), 200),
        external_ref=store.redact(
            f"agent={st.get('agent_id')};run={st.get('run_id')};cwd={st.get('cwd')}",
            300,
        ),
    )

    if st.get("phase") in ("cancelled",) or exit_code == 143:
        raise RuntimeError("cursor_cancelled")

    if st.get("phase") in ("timed_out_inner",) or exit_code == 124:
        raise TimeoutError("cursor_timeout")

    if st.get("phase") == "rejected":
        raise RuntimeError(store.redact(str(st.get("error") or "rejected"), 120))

    if st.get("phase") == "error":
        raise RuntimeError(store.redact(str(st.get("error") or "runner_error"), 160))

    validation = tasks.validate_result(
        variant=variant,
        job_id=jid,
        repo=repo,
        exit_code=int(exit_code) if exit_code is not None else None,
        agent_status=str(st.get("agent_status") or ""),
        baseline_porcelain=baseline,
    )
    ref = (
        f"cursor_local;agent={st.get('agent_id')};exit={exit_code};"
        f"valid={validation.get('ok')};reason={validation.get('reason')};"
        f"result={validation.get('result_path')}"
    )
    if variant == "fail" and validation.get("expected_fail"):
        store.update_fields(jid, result_reference=store.redact(ref, 300))
        raise RuntimeError("RESULT_VALIDATION_FAILED:controlled_fail")

    if not validation.get("ok"):
        store.update_fields(jid, result_reference=store.redact(ref, 300))
        raise RuntimeError(
            f"RESULT_VALIDATION_FAILED:{store.redact(str(validation.get('reason')), 80)}"
        )

    return {
        "result_reference": store.redact(ref, 300),
        "validation": validation,
        "git_diff": validation.get("git_diff"),
    }


def _reattach_or_stall(job: dict[str, Any], wid: str) -> dict[str, Any] | None:
    jid = job["job_id"]
    pid = int(job.get("external_pid") or 0)
    if pid <= 0:
        return None
    if cursor_proc.pid_alive(pid):
        store.update_fields(
            jid,
            external_last_step="reattach_observe",
            progress_message="Bestehender Cursor-Prozess erkannt — kein Zweitstart",
            current_step="cursor_reattach",
        )
        notify.notify_status(store.get_job(jid) or job, "progress")
        status_path = _status_dir(jid) / "status.json"
        deadline = time.time() + int(job.get("timeout_seconds") or 600)
        while time.time() < deadline:
            if _worker_stop_flag():
                raise RuntimeError("worker_stopping_cursor_observe")
            st = _read_status(status_path)
            queue.heartbeat(
                jid,
                wid=wid,
                current_step="cursor_reattach",
                progress_message=f"Beobachtung PID {pid}; Schritt: {st.get('last_step') or 'laeuft'}",
            )
            if st.get("phase") in ("finished", "error", "cancelled", "timed_out_inner", "rejected"):
                return _finalize_from_status(job, wid, st, proc_returncode=st.get("exit_code"))
            if not cursor_proc.pid_alive(pid):
                st = _read_status(status_path)
                if st.get("phase") in ("finished", "error", "cancelled", "timed_out_inner"):
                    return _finalize_from_status(job, wid, st, proc_returncode=st.get("exit_code"))
                store.transition(
                    jid,
                    "STALLED",
                    extra={
                        "finished_at": store.utc_now(),
                        "error_category": "stalled",
                        "error_message_redacted": "cursor_pid_died_during_observe",
                        "worker_id": None,
                        "lease_expires_at": None,
                    },
                )
                notify.notify_status(store.get_job(jid) or job, "stalled")
                return {"result_reference": "stalled_observe"}
            cur = store.get_job(jid)
            if cur and cur.get("status") == "CANCELLED":
                pgid = int(job.get("external_pgid") or 0) or None
                cursor_proc.kill_process_group(
                    pgid, pid, grace_seconds=safety.resource_limits()["grace_seconds"]
                )
                return {"result_reference": "cancelled_reattach"}
            time.sleep(1.0)
        raise TimeoutError("cursor_reattach_timeout")

    store.transition(
        jid,
        "STALLED",
        extra={
            "finished_at": store.utc_now(),
            "error_category": "stalled",
            "error_message_redacted": "cursor_pid_gone_no_autostart",
            "worker_id": None,
            "lease_expires_at": None,
        },
    )
    notify.notify_status(store.get_job(jid) or job, "stalled")
    return {"result_reference": "stalled_no_autostart"}


def handle_cursor_canary(job: dict[str, Any], wid: str) -> dict[str, Any]:
    jid = job["job_id"]
    if not safety.cursor_allowed():
        raise RuntimeError("cursor_canary_disabled")

    if job.get("external_pid") and job.get("external_kind") == "cursor_local":
        re = _reattach_or_stall(job, wid)
        if re is not None:
            return re

    variant = tasks.parse_variant_from_summary(job.get("task_summary") or "")
    if variant not in safety.ALLOWED_VARIANTS:
        raise RuntimeError(f"variant_not_allowed:{variant}")

    scan = safety.scan_task_text(job.get("task_summary") or "")
    if not scan.get("ok"):
        raise RuntimeError(f"security_block:{scan.get('error')}")

    repo = safety.default_repo_path()
    built = tasks.build_prompt(variant, jid, repo)
    if not built.get("ok"):
        raise RuntimeError(store.redact(str(built.get("error") or "build_failed"), 120))

    if variant == "branchedit":
        br = tasks.ensure_canary_branch(repo)
        if not br.get("ok"):
            raise RuntimeError(store.redact(str(br.get("error")), 120))

    baseline = tasks.git_status_porcelain(repo)
    sdir = _status_dir(jid)
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "baseline.json").write_text(
        json.dumps({"porcelain": baseline, "variant": variant, "repo": str(repo)}),
        encoding="utf-8",
    )
    status_path = sdir / "status.json"
    cfg_path = sdir / "runner_config.json"
    timeout = int(job.get("timeout_seconds") or safety.resource_limits()["max_runtime_seconds"])
    if variant == "timeout":
        timeout = min(timeout, int(os.getenv("NILS_CANARY_TIMEOUT_TEST_SECONDS", "45") or 45))

    cfg = {
        "job_id": jid,
        "cwd": built["repo"],
        "prompt": built["prompt"],
        "timeout_seconds": timeout,
        "model": os.getenv("CURSOR_AGENT_MODEL", "composer-2.5"),
        "variant": variant,
    }
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    runner = Path(__file__).resolve().parent / "cursor_local_runner.py"
    proc = subprocess.Popen(
        [sys.executable, str(runner), str(status_path), str(cfg_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
        cwd=str(built["repo"]),
        env={**os.environ, "PYTHONPATH": "/root/app/backend"},
    )
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        pgid = proc.pid

    store.update_fields(
        jid,
        external_kind="cursor_local",
        external_pid=proc.pid,
        external_pgid=pgid,
        external_started_at=store.utc_now(),
        external_last_step="runner_spawned",
        external_ref=f"pid={proc.pid};pgid={pgid};cwd={built['repo']};variant={variant}",
        current_step="cursor_started",
        progress_message="Cursor-Local-Agent-Prozess gestartet (kein erfundenes Prozent)",
    )
    notify.notify_status(store.get_job(jid) or job, "started")
    queue.heartbeat(
        jid,
        wid=wid,
        current_step="cursor_started",
        progress_message=f"Prozess laeuft PID={proc.pid} PGID={pgid}",
    )

    grace = float(safety.resource_limits()["grace_seconds"])
    max_children = safety.resource_limits()["max_child_processes"]
    log_budget = safety.resource_limits()["max_log_bytes"]
    collected = ""
    deadline = time.time() + timeout + 15

    assert proc.stdout is not None
    while True:
        if _worker_stop_flag():
            store.update_fields(
                jid,
                external_last_step="worker_stop_leave_process",
                progress_message="Worker stoppt — Cursor-Prozess bleibt; kein Zweitstart",
            )
            raise RuntimeError("worker_stopping_cursor_keep")

        cur = store.get_job(jid)
        if cur and cur.get("status") in ("CANCELLED", "CANCEL_REQUESTED"):
            kill = cursor_proc.kill_process_group(pgid, proc.pid, grace_seconds=grace)
            store.update_fields(
                jid,
                external_last_step="cancelled_killed",
                external_finished_at=store.utc_now(),
            )
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            return {"result_reference": f"cancelled;kill={kill}"}

        line = ""
        try:
            if select.select([proc.stdout], [], [], 0.5)[0]:
                line = proc.stdout.readline()
        except Exception:
            time.sleep(0.5)

        if line:
            collected = (collected + line)[-log_budget:]
            step = store.redact(line.strip(), 120)
            if step:
                store.update_fields(jid, external_last_step=step)
                queue.heartbeat(
                    jid,
                    wid=wid,
                    current_step="cursor_running",
                    progress_message=f"letzter Log: {step}",
                )

        st = _read_status(status_path)
        if st.get("last_step") or st.get("agent_id"):
            store.update_fields(
                jid,
                external_last_step=store.redact(str(st.get("last_step") or "running"), 160),
                external_ref=store.redact(
                    f"pid={proc.pid};pgid={pgid};agent={st.get('agent_id')};cwd={st.get('cwd')}",
                    300,
                ),
            )
            queue.heartbeat(
                jid,
                wid=wid,
                current_step="cursor_running",
                progress_message=(
                    f"Cursor aktiv; letzter Schritt: {store.redact(str(st.get('last_step') or 'running'), 80)}"
                ),
            )

        tree = cursor_proc.count_process_tree(proc.pid)
        if tree > max_children:
            cursor_proc.kill_process_group(pgid, proc.pid, grace_seconds=grace)
            raise RuntimeError(f"too_many_child_processes:{tree}")

        rc = proc.poll()
        if rc is not None:
            try:
                rest = proc.stdout.read() or ""
                collected = (collected + rest)[-log_budget:]
            except Exception:
                pass
            st = _read_status(status_path)
            if not st:
                st = {
                    "phase": "error" if rc else "finished",
                    "exit_code": rc,
                    "cwd": built["repo"],
                }
            return _finalize_from_status(job, wid, st, proc_returncode=rc)

        if time.time() > deadline:
            kill = cursor_proc.kill_process_group(pgid, proc.pid, grace_seconds=grace)
            store.update_fields(
                jid,
                external_last_step="timeout_kill",
                external_exit_code=124,
                external_finished_at=store.utc_now(),
            )
            try:
                notify._ops_alert(f"TIMED_OUT cursor canary {jid}")
            except Exception:
                pass
            raise TimeoutError("cursor_timeout")

        time.sleep(0.3)

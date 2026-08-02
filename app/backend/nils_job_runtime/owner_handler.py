# -*- coding: utf-8 -*-
"""Owner-limited job handler (Local Cursor Agent + strict validation)."""
from __future__ import annotations

import json
import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from nils_job_runtime import notify, queue, store
from nils_job_runtime import cursor_proc
from nils_job_runtime import cursor_safety as safety
from nils_job_runtime import cursor_canary_tasks as ctasks
from nils_job_runtime import owner_tasks


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


def _parse_meta(summary: str) -> dict[str, str]:
    s = summary or ""
    out: dict[str, str] = {}
    m = re.search(r"\brepo=([A-Za-z0-9._-]+)", s)
    if m:
        out["repo"] = m.group(1)
    m = re.search(r"\bclass=([A-Z_]+)", s)
    if m:
        out["job_class"] = m.group(1)
    m = re.search(r"\battempt=([A-Za-z0-9._-]+)", s)
    if m:
        out["attempt"] = m.group(1)
    m = re.search(r"\b(readonly|branch|report|failtest)\b", s, re.I)
    if m and "job_class" not in out:
        out["kind"] = m.group(1).lower()
    return out


def handle_owner_job(job: dict[str, Any], wid: str) -> dict[str, Any]:
    jid = job["job_id"]
    if not safety.cursor_allowed():
        raise RuntimeError("cursor_disabled")

    # Reattach / no double-start
    if job.get("external_pid") and job.get("external_kind") == "cursor_local":
        from nils_job_runtime.cursor_handler import _reattach_or_stall

        re = _reattach_or_stall(job, wid)
        if re is not None:
            return re

    meta = _parse_meta(job.get("task_summary") or "")
    job_class = job.get("job_class") or meta.get("job_class") or ""
    if not job_class and meta.get("kind"):
        job_class = {
            "readonly": "READ_ONLY_ANALYSIS",
            "branch": "BRANCH_CHANGE",
            "report": "REPORT_GENERATION",
            "failtest": "CONTROLLED_FAIL",
        }.get(meta["kind"], "")
    attempt = job.get("attempt_id") or meta.get("attempt") or f"ATT-{jid[-8:]}"
    repo_name = meta.get("repo") or Path(job.get("workspace_path") or safety.default_repo_path()).name
    resolved = owner_tasks.resolve_repo(repo_name)
    if not resolved.get("ok"):
        raise RuntimeError(f"repo_denied:{resolved.get('error')}")
    repo: Path = resolved["path"]

    # Extract human task after |
    task = (job.get("task_summary") or "").split("|", 1)[-1].strip()
    if task.startswith("attempt="):
        task = re.sub(r"^.*?\|", "", job.get("task_summary") or "").strip()
    built = owner_tasks.build_owner_prompt(
        job_class=job_class,
        job_id=jid,
        attempt_id=attempt,
        repo=repo,
        task=task or job_class,
    )
    if not built.get("ok"):
        raise RuntimeError(f"security_block:{built.get('error')}")

    if job_class == "BRANCH_CHANGE":
        br = ctasks.ensure_canary_branch(repo, built["branch"])
        if not br.get("ok"):
            raise RuntimeError(store.redact(str(br.get("error")), 120))
        store.update_fields(jid, git_branch=built["branch"], workspace_path=str(repo))
    else:
        store.update_fields(jid, workspace_path=str(repo), job_class=job_class, attempt_id=attempt)

    baseline = ctasks.git_status_porcelain(repo)
    sdir = _status_dir(jid)
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "baseline.json").write_text(
        json.dumps(
            {
                "porcelain": baseline,
                "job_class": job_class,
                "repo": str(repo),
                "report": built.get("report_path"),
                "attempt": attempt,
            }
        ),
        encoding="utf-8",
    )
    status_path = sdir / "status.json"
    cfg_path = sdir / "runner_config.json"
    timeout = int(job.get("timeout_seconds") or safety.resource_limits()["max_runtime_seconds"])
    cfg = {
        "job_id": jid,
        "cwd": str(repo),
        "prompt": built["prompt"],
        "timeout_seconds": timeout,
        "model": os.getenv("CURSOR_AGENT_MODEL", "composer-2.5"),
        "variant": job_class.lower(),
    }
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    runner = Path(__file__).resolve().parent / "cursor_local_runner.py"
    proc = subprocess.Popen(
        [sys.executable, str(runner), str(status_path), str(cfg_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
        cwd=str(repo),
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
        external_ref=f"pid={proc.pid};pgid={pgid};cwd={repo};class={job_class}",
        current_step="owner_started",
        progress_message="Owner-Job Cursor-Prozess gestartet",
        job_class=job_class,
        attempt_id=attempt,
    )
    notify.notify_status(store.get_job(jid) or job, "started")
    queue.heartbeat(jid, wid=wid, current_step="owner_started", progress_message=f"PID={proc.pid}")

    grace = float(safety.resource_limits()["grace_seconds"])
    max_children = safety.resource_limits()["max_child_processes"]
    deadline = time.time() + timeout + 15
    assert proc.stdout is not None

    while True:
        if _worker_stop_flag():
            store.update_fields(jid, external_last_step="worker_stop_leave_process")
            raise RuntimeError("worker_stopping_cursor_keep")

        cur = store.get_job(jid)
        if cur and cur.get("status") in ("CANCELLED", "CANCEL_REQUESTED"):
            kill = cursor_proc.kill_process_group(pgid, proc.pid, grace_seconds=grace)
            store.update_fields(jid, external_last_step="cancel_seen_by_worker")
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            return {"result_reference": f"cancel_handled;kill={kill}"}

        try:
            if select.select([proc.stdout], [], [], 0.5)[0]:
                line = proc.stdout.readline()
                if line.strip():
                    store.update_fields(jid, external_last_step=store.redact(line.strip(), 120))
                    queue.heartbeat(
                        jid,
                        wid=wid,
                        current_step="owner_running",
                        progress_message=f"Log: {store.redact(line.strip(), 80)}",
                    )
        except Exception:
            time.sleep(0.4)

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
                current_step="owner_running",
                progress_message=f"Schritt: {store.redact(str(st.get('last_step') or 'running'), 80)}",
            )

        if cursor_proc.count_process_tree(proc.pid) > max_children:
            cursor_proc.kill_process_group(pgid, proc.pid, grace_seconds=grace)
            raise RuntimeError("too_many_child_processes")

        rc = proc.poll()
        if rc is not None:
            try:
                proc.stdout.read()
            except Exception:
                pass
            st = _read_status(status_path) or {
                "phase": "error" if rc else "finished",
                "exit_code": rc,
                "cwd": str(repo),
            }
            return _finalize_owner(job, wid, st, proc_returncode=rc, built=built, baseline=baseline)

        if time.time() > deadline:
            cursor_proc.kill_process_group(pgid, proc.pid, grace_seconds=grace)
            store.update_fields(
                jid,
                external_last_step="timeout_kill",
                external_exit_code=124,
                external_finished_at=store.utc_now(),
            )
            raise TimeoutError("cursor_timeout")
        time.sleep(0.3)


def _finalize_owner(
    job: dict[str, Any],
    wid: str,
    st: dict[str, Any],
    *,
    proc_returncode: int | None,
    built: dict[str, Any],
    baseline: str,
) -> dict[str, Any]:
    jid = job["job_id"]
    job_class = job.get("job_class") or built.get("job_class") or ""
    attempt = job.get("attempt_id") or "ATT"
    repo = Path(st.get("cwd") or built.get("repo") or safety.default_repo_path())
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
    if st.get("phase") in ("rejected", "error"):
        raise RuntimeError(store.redact(str(st.get("error") or st.get("phase")), 160))

    validation = owner_tasks.validate_owner_result(
        job_class=job_class,
        job_id=jid,
        attempt_id=attempt,
        repo=repo,
        branch=job.get("git_branch") or built.get("branch"),
        exit_code=int(exit_code) if exit_code is not None else None,
        agent_status=str(st.get("agent_status") or ""),
        baseline_porcelain=baseline,
        report_hint=built.get("report_path"),
    )
    store.update_fields(
        jid,
        result_validation=store.redact(str(validation.get("reason")), 200),
    )
    ref = (
        f"owner;agent={st.get('agent_id')};exit={exit_code};"
        f"valid={validation.get('ok')};reason={validation.get('reason')};"
        f"reports={validation.get('reports')}"
    )
    if job_class == "CONTROLLED_FAIL" and validation.get("expected_fail"):
        store.update_fields(jid, result_reference=store.redact(ref, 300))
        raise RuntimeError("RESULT_VALIDATION_FAILED:controlled_fail")
    if not validation.get("ok"):
        store.update_fields(jid, result_reference=store.redact(ref, 300))
        raise RuntimeError(
            f"RESULT_VALIDATION_FAILED:{store.redact(str(validation.get('reason')), 80)}"
        )
    return {"result_reference": store.redact(ref, 300), "validation": validation}

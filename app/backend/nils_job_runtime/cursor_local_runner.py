#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone Cursor Local-Agent runner (own process group).

Invoked by the Nils worker — not from free Telegram shell text.
Writes status JSON for the parent worker to monitor honestly.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path

_STOP = False


def _request_stop(*_a: object) -> None:
    global _STOP
    _STOP = True


def _load_api_key() -> str:
    v = (os.environ.get("CURSOR_API_KEY") or "").strip()
    if v:
        return v
    for p in (
        Path("/root/app/cursor.secrets.local"),
        Path("/root/app/requesty.secrets.local"),
        Path("/root/app/backend/.env"),
    ):
        if not p.is_file():
            continue
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("CURSOR_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            continue
    return ""


def _write_status(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    if len(sys.argv) < 2:
        print("usage: cursor_local_runner.py <job_status_json_path>", file=sys.stderr)
        return 2
    status_path = Path(sys.argv[1])
    cfg_path = Path(sys.argv[2]) if len(sys.argv) > 2 else status_path.with_name("runner_config.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    job_id = cfg["job_id"]
    cwd = cfg["cwd"]
    prompt = cfg["prompt"]
    model = cfg.get("model") or os.environ.get("CURSOR_AGENT_MODEL", "composer-2.5")
    timeout = int(cfg.get("timeout_seconds") or 600)

    # Import safety from package if available
    sys.path.insert(0, "/root/app/backend")
    from nils_job_runtime.cursor_safety import validate_workdir, disk_ok, resource_limits
    from nils_job_runtime import store as _store  # noqa: F401 — redact via local

    wd = validate_workdir(cwd)
    if not wd.get("ok"):
        _write_status(
            status_path,
            {
                "phase": "rejected",
                "error": wd.get("error"),
                "exit_code": 10,
                "pid": os.getpid(),
                "pgid": os.getpgid(0),
            },
        )
        return 10

    d = disk_ok(Path(wd["path"]))
    if not d.get("ok"):
        _write_status(
            status_path,
            {"phase": "rejected", "error": "disk_low", "disk": d, "exit_code": 11},
        )
        return 11

    api_key = _load_api_key()
    if not api_key:
        _write_status(status_path, {"phase": "rejected", "error": "no_api_key", "exit_code": 12})
        return 12

    pid = os.getpid()
    pgid = os.getpgid(0)
    started = time.time()
    _write_status(
        status_path,
        {
            "phase": "starting",
            "job_id": job_id,
            "pid": pid,
            "pgid": pgid,
            "cwd": wd["path"],
            "realpath": wd.get("realpath"),
            "started_at": started,
            "last_step": "agent_create",
        },
    )

    agent = None
    try:
        from cursor_sdk import Agent, LocalAgentOptions

        agent = Agent.create(
            model=model,
            api_key=api_key,
            local=LocalAgentOptions(cwd=wd["path"]),
            name=f"nils-canary-{job_id[-12:]}",
        )
        agent_id = getattr(agent, "agent_id", None) or getattr(agent, "id", None) or ""
        _write_status(
            status_path,
            {
                "phase": "running",
                "job_id": job_id,
                "pid": pid,
                "pgid": pgid,
                "cwd": wd["path"],
                "agent_id": str(agent_id),
                "started_at": started,
                "last_step": "agent_send",
            },
        )
        run = agent.send(prompt)
        # Stream / wait with cooperative stop + timeout
        deadline = started + timeout
        last_step = "agent_send"
        chunks: list[str] = []
        max_log = resource_limits()["max_log_bytes"]
        try:
            for message in run.messages():
                if _STOP:
                    try:
                        Agent.cancel_run(run) if hasattr(Agent, "cancel_run") else None
                    except Exception:
                        pass
                    try:
                        cancel = getattr(agent, "cancel_run", None)
                        if callable(cancel):
                            cancel(run)
                    except Exception:
                        pass
                    _write_status(
                        status_path,
                        {
                            "phase": "cancelled",
                            "job_id": job_id,
                            "pid": pid,
                            "pgid": pgid,
                            "agent_id": str(agent_id),
                            "last_step": "sigterm_cancel",
                            "exit_code": 143,
                        },
                    )
                    return 143
                if time.time() > deadline:
                    _write_status(
                        status_path,
                        {
                            "phase": "timed_out_inner",
                            "job_id": job_id,
                            "pid": pid,
                            "pgid": pgid,
                            "agent_id": str(agent_id),
                            "last_step": "timeout_before_wait",
                            "exit_code": 124,
                        },
                    )
                    return 124
                if getattr(message, "type", None) == "assistant":
                    content = getattr(getattr(message, "message", None), "content", None)
                    if isinstance(content, list):
                        for block in content:
                            if getattr(block, "type", None) == "text":
                                chunks.append(getattr(block, "text", "") or "")
                    elif isinstance(content, str):
                        chunks.append(content)
                    last_step = "assistant_message"
                    text_joined = "".join(chunks)[-max_log:]
                    _write_status(
                        status_path,
                        {
                            "phase": "running",
                            "job_id": job_id,
                            "pid": pid,
                            "pgid": pgid,
                            "agent_id": str(agent_id),
                            "cwd": wd["path"],
                            "started_at": started,
                            "last_step": last_step,
                            "partial_text_redacted": text_joined[-500:],
                        },
                    )
        except Exception:
            # messages() optional
            pass

        remaining = max(1, int(deadline - time.time()))
        try:
            result = run.wait(timeout=remaining)
        except TypeError:
            result = run.wait()
        status = str(getattr(result, "status", None) or "unknown")
        summary = "".join(chunks).strip() or str(getattr(result, "result", "") or "")
        summary = summary[: resource_limits()["max_result_bytes"]]
        exit_code = 0 if status in ("finished", "completed", "success", "ok") else 1
        _write_status(
            status_path,
            {
                "phase": "finished",
                "job_id": job_id,
                "pid": pid,
                "pgid": pgid,
                "agent_id": str(agent_id),
                "cwd": wd["path"],
                "started_at": started,
                "finished_at": time.time(),
                "agent_status": status,
                "last_step": f"agent_status={status}",
                "result_excerpt": summary[:1500],
                "exit_code": exit_code,
                "run_id": str(getattr(result, "id", "") or ""),
            },
        )
        return exit_code
    except Exception as e:
        _write_status(
            status_path,
            {
                "phase": "error",
                "job_id": job_id,
                "pid": pid,
                "pgid": pgid,
                "error": str(e)[:400],
                "traceback": traceback.format_exc()[-1500:],
                "exit_code": 1,
                "last_step": "exception",
            },
        )
        return 1
    finally:
        if agent is not None:
            try:
                agent.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())

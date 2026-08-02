# -*- coding: utf-8 -*-
"""Process-group helpers for Cursor Canary (SIGTERM → grace → SIGKILL)."""
from __future__ import annotations

import logging
import os
import signal
import time
from typing import Any

log = logging.getLogger("nils_job_runtime.cursor_proc")


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def list_children(pid: int) -> list[int]:
    """Best-effort child PIDs via /proc (Linux)."""
    kids: list[int] = []
    proc = "/proc"
    if not os.path.isdir(proc):
        return kids
    try:
        for name in os.listdir(proc):
            if not name.isdigit():
                continue
            sp = int(name)
            try:
                with open(f"/proc/{sp}/stat", encoding="utf-8", errors="replace") as f:
                    # field 4 is ppid in /proc/pid/stat after comm
                    data = f.read()
                # format: pid (comm) state ppid ...
                rparen = data.rfind(")")
                if rparen < 0:
                    continue
                rest = data[rparen + 2 :].split()
                if len(rest) < 2:
                    continue
                ppid = int(rest[1])
                if ppid == pid:
                    kids.append(sp)
            except Exception:
                continue
    except Exception:
        log.exception("list_children")
    return kids


def count_process_tree(pid: int, *, limit: int = 64) -> int:
    seen: set[int] = set()
    stack = [pid]
    while stack and len(seen) < limit:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(list_children(cur))
    return len(seen)


def kill_process_group(
    pgid: int | None,
    pid: int | None,
    *,
    grace_seconds: float = 8.0,
) -> dict[str, Any]:
    """SIGTERM process group first, then SIGKILL after grace."""
    out: dict[str, Any] = {
        "pgid": pgid,
        "pid": pid,
        "sigterm": False,
        "sigkill": False,
        "alive_after": False,
    }
    target_pgid = pgid
    if not target_pgid and pid:
        try:
            target_pgid = os.getpgid(pid)
        except OSError:
            target_pgid = None

    def _term() -> None:
        if target_pgid and target_pgid > 1:
            try:
                os.killpg(target_pgid, signal.SIGTERM)
                out["sigterm"] = True
                return
            except OSError:
                pass
        if pid and pid_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
                out["sigterm"] = True
            except OSError:
                pass

    def _kill() -> None:
        if target_pgid and target_pgid > 1:
            try:
                os.killpg(target_pgid, signal.SIGKILL)
                out["sigkill"] = True
                return
            except OSError:
                pass
        if pid and pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
                out["sigkill"] = True
            except OSError:
                pass

    _term()
    deadline = time.time() + max(0.5, grace_seconds)
    while time.time() < deadline:
        alive = (pid and pid_alive(pid)) or False
        if target_pgid:
            # if any child of tree still up
            if pid and count_process_tree(pid) > 1:
                alive = True
        if not alive:
            break
        time.sleep(0.2)
    if pid and pid_alive(pid):
        _kill()
        time.sleep(0.3)
    out["alive_after"] = bool(pid and pid_alive(pid))
    orphans = []
    if pid:
        orphans = [c for c in list_children(pid) if pid_alive(c)]
    out["orphan_children"] = orphans
    return out

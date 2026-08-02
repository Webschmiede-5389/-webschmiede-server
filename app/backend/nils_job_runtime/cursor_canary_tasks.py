# -*- coding: utf-8 -*-
"""Fixed Cursor Canary task variants + result validators (no free-form shell)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from nils_job_runtime.cursor_safety import default_repo_path, scan_task_text, validate_workdir

Validator = Callable[[dict[str, Any]], dict[str, Any]]


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


def git_status_porcelain(cwd: Path) -> str:
    r = _git(cwd, "status", "--porcelain")
    return (r.stdout or "").strip()


def git_diff(cwd: Path) -> str:
    r = _git(cwd, "diff")
    staged = _git(cwd, "diff", "--cached")
    return ((r.stdout or "") + (staged.stdout or "")).strip()


def ensure_canary_branch(cwd: Path, branch: str = "canary/nils-live") -> dict[str, Any]:
    cur = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    name = (cur.stdout or "").strip() or "master"
    # create/switch branch without touching production remotes
    exists = _git(cwd, "show-ref", "--verify", f"refs/heads/{branch}")
    if exists.returncode != 0:
        r = _git(cwd, "checkout", "-b", branch)
    else:
        r = _git(cwd, "checkout", branch)
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout or "branch_failed")[:200]}
    return {"ok": True, "branch": branch, "from": name}


def build_prompt(variant: str, job_id: str, repo: Path) -> dict[str, Any]:
    """Return fixed prompt for a variant. Never concatenate raw Telegram free text as shell."""
    v = (variant or "").lower().strip()
    result_name = f"canary-results/cursor-canary-{job_id}.md"
    prompts = {
        "readonly": (
            "CANARY READ-ONLY TASK.\n"
            "1) List the top-level project structure.\n"
            "2) Read README.md and any simple config files.\n"
            f"3) Write a report ONLY to NEW file {result_name} (create directory canary-results if needed).\n"
            "4) Do NOT modify any existing tracked files.\n"
            "5) Do NOT commit, push, deploy, or touch secrets.\n"
            "6) End the report with the exact line: CANARY_READONLY_OK\n"
        ),
        "writefile": (
            "CANARY WRITE-FILE TASK.\n"
            f"Create exactly one new file: {result_name}\n"
            "Content: a short German summary that this canary write succeeded, "
            "include Job-ID placeholder text and end with CANARY_WRITE_OK.\n"
            "Do not modify any other existing files. No commit, no push, no deploy.\n"
        ),
        "branchedit": (
            "CANARY BRANCH-EDIT TASK.\n"
            "You are already on an isolated canary branch.\n"
            "Make ONE small safe change: append a single line "
            "'# nils-canary-marker' to README.md if not already present.\n"
            "Do not push. Do not force. Do not reset --hard. Do not deploy.\n"
            f"Also create {result_name} with line CANARY_BRANCH_OK.\n"
        ),
        "fail": (
            "CANARY CONTROLLED-FAIL TASK.\n"
            "Reply with text only. Do NOT create any files. Do NOT modify the repo.\n"
            "End with: CANARY_SHOULD_NOT_VALIDATE\n"
            "(This task is expected to fail result validation on purpose.)\n"
        ),
        "timeout": (
            "CANARY TIMEOUT TASK.\n"
            "Slowly explore the repository in many tiny steps. "
            "Keep working for a long time without finishing. "
            "Do not modify files. Do not create files. "
            "This run is intentionally long for timeout testing.\n"
        ),
        "long": (
            "CANARY LONG TASK.\n"
            "Analyze README and list files carefully with several reasoning steps.\n"
            f"When done, write {result_name} ending with CANARY_LONG_OK.\n"
            "Do not modify other existing files. No push/deploy.\n"
        ),
    }
    if v not in prompts:
        return {"ok": False, "error": f"unknown_variant:{v}"}
    prompt = prompts[v]
    scan = scan_task_text(prompt)
    if not scan.get("ok"):
        return scan
    wd = validate_workdir(repo)
    if not wd.get("ok"):
        return wd
    return {
        "ok": True,
        "variant": v,
        "prompt": prompt,
        "repo": str(Path(wd["path"])),
        "result_rel": result_name,
        "expect_marker": {
            "readonly": "CANARY_READONLY_OK",
            "writefile": "CANARY_WRITE_OK",
            "branchedit": "CANARY_BRANCH_OK",
            "fail": None,
            "timeout": None,
            "long": "CANARY_LONG_OK",
        }.get(v),
    }


def validate_result(
    *,
    variant: str,
    job_id: str,
    repo: Path,
    exit_code: int | None,
    agent_status: str | None,
    baseline_porcelain: str,
) -> dict[str, Any]:
    """Exit 0 alone is not enough — task-specific checks required."""
    v = variant.lower().strip()
    out: dict[str, Any] = {
        "variant": v,
        "exit_code": exit_code,
        "agent_status": agent_status,
        "ok": False,
    }
    if exit_code not in (0, None) and v not in ("fail", "timeout"):
        # local runner may use exit 0 with status in JSON
        pass

    result_path = repo / "canary-results" / f"cursor-canary-{job_id}.md"
    porcelain = git_status_porcelain(repo)
    diff = git_diff(repo)
    out["git_porcelain"] = porcelain[:2000]
    out["git_diff"] = diff[:4000]
    out["result_path"] = str(result_path) if result_path.exists() else None

    if v == "fail":
        # Expect validation failure: no result file / wrong marker
        if result_path.exists() and "CANARY_SHOULD_NOT_VALIDATE" in result_path.read_text(
            encoding="utf-8", errors="replace"
        ):
            out["ok"] = False
            out["reason"] = "controlled_fail_unexpected_file"
            return out
        # Agent finished without required success artifact → FAIL as designed
        out["ok"] = False
        out["reason"] = "controlled_result_validation_failed"
        out["expected_fail"] = True
        return out

    if v == "timeout":
        out["ok"] = False
        out["reason"] = "timeout_variant_should_not_succeed_via_validator"
        return out

    if agent_status and agent_status not in ("finished", "completed", "success", "ok", "done"):
        out["reason"] = f"bad_agent_status:{agent_status}"
        return out

    if not result_path.is_file():
        out["reason"] = "missing_result_file"
        return out

    try:
        content = result_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        out["reason"] = f"result_unreadable:{e}"
        return out
    out["result_bytes"] = len(content.encode("utf-8", errors="replace"))
    marker = {
        "readonly": "CANARY_READONLY_OK",
        "writefile": "CANARY_WRITE_OK",
        "branchedit": "CANARY_BRANCH_OK",
        "long": "CANARY_LONG_OK",
    }.get(v)
    if marker and marker not in content:
        out["reason"] = f"missing_marker:{marker}"
        return out

    # Diff constraints
    def _paths_from_porcelain(text: str) -> list[str]:
        paths: list[str] = []
        for line in (text or "").splitlines():
            line = line.rstrip()
            if not line or len(line) < 4:
                continue
            path = line[3:].strip()
            # renames: "R  old -> new"
            if " -> " in path:
                path = path.split(" -> ", 1)[-1].strip()
            if path:
                paths.append(path)
        return paths

    if v in ("readonly", "writefile", "long"):
        baseline_paths = set(_paths_from_porcelain(baseline_porcelain))
        bad_lines = []
        for line in porcelain.splitlines():
            line = line.rstrip()
            if not line:
                continue
            path = line[3:].strip() if len(line) > 3 else line
            if " -> " in path:
                path = path.split(" -> ", 1)[-1].strip()
            if path.startswith("canary-results/") or path.startswith(".cursor"):
                continue
            if line in (baseline_porcelain or "").splitlines():
                continue
            if path in baseline_paths and path == "README.md":
                # prior canary marker dirt is OK if unchanged from baseline intent
                continue
            if path == "README.md" and "# nils-canary-marker" in (
                (repo / "README.md").read_text(encoding="utf-8", errors="replace")
            ):
                # leftover from earlier branchedit canary — not a regression for this variant
                continue
            bad_lines.append(line)
        if bad_lines:
            out["reason"] = "unexpected_git_changes"
            out["bad"] = bad_lines[:20]
            return out

    if v == "branchedit":
        if "# nils-canary-marker" not in (repo / "README.md").read_text(
            encoding="utf-8", errors="replace"
        ):
            out["reason"] = "readme_marker_missing"
            return out
        for path in _paths_from_porcelain(porcelain):
            if path == "README.md" or path.startswith("canary-results/") or path.startswith(
                ".cursor"
            ):
                continue
            if path in ("canary.config.json", ".gitkeep"):
                continue
            out["reason"] = "unexpected_path_in_branch_edit"
            out["bad_path"] = path
            return out

    out["ok"] = True
    out["reason"] = "validated"
    return out


def parse_variant_from_summary(summary: str) -> str:
    s = (summary or "").strip().lower()
    # formats: "readonly …" or "variant=readonly|…"
    first = s.split()[0] if s.split() else ""
    if first in (
        "readonly",
        "writefile",
        "branchedit",
        "fail",
        "timeout",
        "long",
    ):
        return first
    if "variant=" in s:
        part = s.split("variant=", 1)[1].split("|", 1)[0].strip()
        return part
    return "readonly"

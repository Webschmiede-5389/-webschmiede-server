# -*- coding: utf-8 -*-
"""Owner-limited production task classes + validators."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nils_job_runtime import cursor_canary_tasks as tasks
from nils_job_runtime import cursor_safety as safety

JOB_CLASSES = frozenset(
    {"READ_ONLY_ANALYSIS", "BRANCH_CHANGE", "REPORT_GENERATION", "CONTROLLED_FAIL"}
)

FORBIDDEN_BRANCHES = frozenset({"main", "master", "production", "prod", "live"})

_SECRET_DIFF_RE = re.compile(
    r"(?i)(api[_-]?key|secret|password|token|BEGIN (RSA |OPENSSH )?PRIVATE KEY)\s*[:=]"
)


def resolve_repo(name: str) -> dict[str, Any]:
    name = (name or "").strip().strip("/")
    if not name or ".." in name or "/" in name or "\\" in name:
        return {"ok": False, "error": "invalid_repo_name"}
    root = safety.workspace_root()
    cand = (root / name).resolve()
    vd = safety.validate_workdir(cand)
    if not vd.get("ok"):
        return vd
    return {"ok": True, "path": Path(vd["path"]), "name": name}


def job_branch_name(job_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", job_id)[-40:]
    return f"nils/job-{safe}"


def report_path(repo: Path, job_id: str, attempt_id: str) -> Path:
    """Unique report path inside allowlisted repo — never overwrite."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = repo / "owner-results"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"owner-{job_id}-{attempt_id}-{ts}.md"


def build_owner_prompt(
    *,
    job_class: str,
    job_id: str,
    attempt_id: str,
    repo: Path,
    task: str,
) -> dict[str, Any]:
    scan = safety.scan_task_text(task)
    if not scan.get("ok"):
        return scan
    # Extra forbidden intents for production limited
    low = (task or "").lower()
    for bad in (
        "deploy",
        "nginx",
        "firewall",
        "systemctl",
        "migration",
        "n8n",
        "merge ",
        "push ",
        "force push",
        "reset --hard",
    ):
        if bad in low:
            return {"ok": False, "error": f"forbidden_intent:{bad}"}

    branch = job_branch_name(job_id)
    rpt = report_path(repo, job_id, attempt_id)
    if job_class == "READ_ONLY_ANALYSIS":
        prompt = (
            "OWNER LIMITED — READ_ONLY_ANALYSIS.\n"
            f"Task: {task.strip()[:800]}\n"
            "Rules:\n"
            "- Read files, git status, project structure only.\n"
            "- Do NOT modify any existing tracked files.\n"
            f"- Write a NEW report ONLY to relative path: owner-results/{rpt.name}\n"
            "- Report must include sections: Summary, Structure, Findings, Risks.\n"
            "- End with exact line: OWNER_READONLY_OK\n"
            "- No commit, push, deploy, secrets.\n"
        )
    elif job_class == "BRANCH_CHANGE":
        prompt = (
            "OWNER LIMITED — BRANCH_CHANGE.\n"
            f"You are on branch {branch} (isolated job branch).\n"
            f"Task: {task.strip()[:800]}\n"
            "Rules:\n"
            "- Make a SMALL documentation-only improvement (e.g. README clarification).\n"
            "- Do NOT touch main/master/production.\n"
            "- No merge, no push, no deploy, no .env, no secrets.\n"
            f"- Also write a short report to NEW file owner-results/{rpt.name} ending with OWNER_BRANCH_OK\n"
            "- Do not change application code beyond docs.\n"
        )
    elif job_class == "REPORT_GENERATION":
        prompt = (
            "OWNER LIMITED — REPORT_GENERATION.\n"
            f"Task: {task.strip()[:800]}\n"
            f"- Create ONLY new report file owner-results/{rpt.name}\n"
            "- Do not modify existing files.\n"
            "- Sections: Summary, Observations, NextSteps.\n"
            "- End with OWNER_REPORT_OK\n"
        )
    elif job_class == "CONTROLLED_FAIL":
        prompt = (
            "OWNER LIMITED — CONTROLLED FAIL TEST.\n"
            "Reply with text only. Do NOT create files. Do NOT modify the repo.\n"
            "End with OWNER_SHOULD_FAIL_VALIDATION\n"
        )
    else:
        return {"ok": False, "error": f"unknown_class:{job_class}"}

    return {
        "ok": True,
        "prompt": prompt,
        "branch": branch,
        "report_path": str(rpt),
        "repo": str(repo),
        "job_class": job_class,
    }


def validate_owner_result(
    *,
    job_class: str,
    job_id: str,
    attempt_id: str,
    repo: Path,
    branch: str | None,
    exit_code: int | None,
    agent_status: str | None,
    baseline_porcelain: str,
    report_hint: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "job_class": job_class}
    porcelain = tasks.git_status_porcelain(repo)
    diff = tasks.git_diff(repo)
    out["git_porcelain"] = porcelain[:2000]
    out["git_diff"] = diff[:4000]

    if job_class == "CONTROLLED_FAIL":
        out["expected_fail"] = True
        out["reason"] = "controlled_result_validation_failed"
        return out

    # Find report file(s) for this job/attempt inside repo
    results_dir = repo / "owner-results"
    reports = []
    if results_dir.is_dir():
        for p in sorted(results_dir.glob(f"owner-{job_id}-{attempt_id}-*.md")):
            reports.append(p)
    if report_hint:
        hp = Path(report_hint)
        if hp.is_file() and hp not in reports:
            reports.append(hp)
    out["reports"] = [str(p) for p in reports]

    if agent_status and agent_status not in ("finished", "completed", "success", "ok", "done"):
        out["reason"] = f"bad_agent_status:{agent_status}"
        return out

    if not reports:
        out["reason"] = "missing_report"
        return out
    content = reports[-1].read_text(encoding="utf-8", errors="replace")
    if len(content.strip()) < 40:
        out["reason"] = "report_empty"
        return out

    if job_class == "READ_ONLY_ANALYSIS":
        for sec in ("Summary", "Structure", "Findings", "Risks"):
            if sec.lower() not in content.lower():
                out["reason"] = f"missing_section:{sec}"
                return out
        if "OWNER_READONLY_OK" not in content:
            out["reason"] = "missing_marker"
            return out
        # no productive file changes: only new owner-results / canary-results untracked ok
        for line in porcelain.splitlines():
            if not line.strip():
                continue
            path = line[3:].strip() if len(line) > 3 else ""
            if path.startswith("canary-results/") or path.startswith("owner-results/") or path.startswith(
                ".cursor"
            ):
                continue
            if line in (baseline_porcelain or "").splitlines():
                continue
            # modified tracked?
            if line[:2].strip() and not line.startswith("??"):
                out["reason"] = "readonly_tree_dirty"
                out["bad"] = line
                return out
        # tracked diff should not touch non-report files
        if diff.strip() and "owner-results/" not in diff and "README" in diff:
            out["reason"] = "git_diff_not_empty"
            return out

    if job_class == "BRANCH_CHANGE":
        if not branch or branch in FORBIDDEN_BRANCHES:
            out["reason"] = "bad_branch"
            return out
        cur = tasks._git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        cur_b = (cur.stdout or "").strip()
        out["current_branch"] = cur_b
        if cur_b in FORBIDDEN_BRANCHES:
            out["reason"] = "on_forbidden_branch"
            return out
        if "OWNER_BRANCH_OK" not in content:
            out["reason"] = "missing_marker"
            return out
        if _SECRET_DIFF_RE.search(diff) or _SECRET_DIFF_RE.search(content):
            out["reason"] = "secret_in_diff_or_report"
            return out
        # only docs-ish paths
        for line in porcelain.splitlines():
            if not line.strip():
                continue
            path = line[3:].strip() if len(line) > 3 else ""
            if not path:
                continue
            if path.startswith("canary-results/") or path.startswith("owner-results/") or path.startswith(
                ".cursor"
            ):
                continue
            if path.endswith(".md") or path.endswith(".txt") or path.endswith(".rst"):
                continue
            if path in ("README.md", "README", "docs"):
                continue
            if path.startswith("docs/"):
                continue
            out["reason"] = "disallowed_path_changed"
            out["bad_path"] = path
            return out
        # record "test" as format check
        out["format_check"] = "ok" if content.strip() else "fail"

    if job_class == "REPORT_GENERATION":
        if "OWNER_REPORT_OK" not in content:
            out["reason"] = "missing_marker"
            return out
        for sec in ("Summary", "Observations", "NextSteps"):
            if sec.lower() not in content.lower():
                out["reason"] = f"missing_section:{sec}"
                return out

    out["ok"] = True
    out["reason"] = "validated"
    return out

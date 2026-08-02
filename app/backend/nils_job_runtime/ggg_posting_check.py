# -*- coding: utf-8 -*-
"""German Golf Guide posting finder + read-only checker (no publish/edit)."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# --- Confirmed paths (inventory evidence 2026-07-30) ---
DEFAULT_HUB = Path(
    r"C:\Users\kumex\OneDrive\Desktop\Jarvis\My_Company_Hub\projects\german-golf-guide"
)
DEFAULT_PLANNER = Path(
    r"C:\Users\kumex\OneDrive\Desktop\Jarvis\German Gof Guide_Sozial Media Planner"
)

# Production rule: 3 feed slides + story (also tolerate slide4 editorial packs)
EXPECTED_FEED_SLIDES = ("slide1", "slide2", "slide3")
CTA_MARKERS = (
    "jetzt informieren auf",
    "german golf guide",
    "www.german-golf-guide.de",
    "@germangolfguide",
)

SEVERITY = ("critical", "high", "medium", "low", "info")

CancelCheck = Callable[[], bool]


class GggCheckError(Exception):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


@dataclass
class Finding:
    code: str
    severity: str
    message: str
    suggestion: str = ""


@dataclass
class PostingCheckResult:
    posting_id: str
    planned_at: str | None
    source: str
    result: str  # pass | fail | warn | not_found
    findings: list[Finding] = field(default_factory=list)
    evidence_ref: str = ""
    club_name: str = ""
    dgv: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        visual = (self.details or {}).get("visual") or {}
        out = {
            "posting_id": self.posting_id,
            "club": self.club_name,
            "dgv": self.dgv,
            "geplanter_termin": self.planned_at,
            "quelle": self.source,
            "anzahl_slides": visual.get("anzahl_slides"),
            "gesamtstatus": visual.get("gesamtstatus")
            or (
                "FAIL"
                if self.result == "fail"
                else "PASS_WITH_WARNINGS"
                if self.result == "warn"
                else "PASS"
                if self.result == "pass"
                else "INCOMPLETE_CHECK"
            ),
            "pruefergebnis": self.result,
            "fehler": [
                {
                    "code": f.code,
                    "schweregrad": f.severity,
                    "meldung": f.message,
                    "aenderungsvorschlag": f.suggestion,
                }
                for f in self.findings
                if f.severity in ("critical", "high", "medium")
            ],
            "schweregrad_max": _max_severity(self.findings),
            "belegreferenz": self.evidence_ref,
            "slides": visual.get("slides") or [],
            "details": self.details,
        }
        return out


def hub_root() -> Path:
    return Path(os.getenv("GGG_HUB_ROOT") or DEFAULT_HUB)


def planner_root() -> Path:
    return Path(os.getenv("GGG_PLANNER_ROOT") or DEFAULT_PLANNER)


def images_root() -> Path:
    return hub_root() / "output" / "generated_images"


def schedule_mixed_path() -> Path:
    return hub_root() / "output" / "instagram_schedule_mixed.json"


def autopost_db_path() -> Path:
    return planner_root() / "data" / "autopost.db"


def inventory_sources() -> list[dict[str, Any]]:
    """Document each possible source with evidence — no guessing as AVAILABLE."""
    sources: list[dict[str, Any]] = []

    img = images_root()
    club_dirs = 0
    if img.is_dir():
        club_dirs = sum(1 for p in img.iterdir() if p.is_dir() and p.name.isdigit())
    sources.append(
        {
            "id": "local_hub_images",
            "name": "Lokaler Hub generated_images",
            "path": str(img),
            "exists": img.is_dir(),
            "readable": img.is_dir(),
            "write_used": False,
            "evidence": f"{club_dirs} Club-Ordner mit DGV-ID",
            "status": "AVAILABLE" if club_dirs > 0 else "NOT_CONFIGURED",
        }
    )

    sched = schedule_mixed_path()
    sched_jobs = 0
    if sched.is_file():
        try:
            data = json.loads(sched.read_text(encoding="utf-8"))
            sched_jobs = len(data.get("jobs") or [])
        except Exception as e:
            sources.append(
                {
                    "id": "schedule_json",
                    "name": "instagram_schedule_mixed.json",
                    "path": str(sched),
                    "exists": True,
                    "readable": False,
                    "write_used": False,
                    "evidence": f"parse_error:{type(e).__name__}",
                    "status": "CONNECTION_FAILED",
                }
            )
            sched = None  # type: ignore
    if sched is not None:
        sources.append(
            {
                "id": "schedule_json",
                "name": "instagram_schedule_mixed.json",
                "path": str(sched),
                "exists": sched.is_file(),
                "readable": sched.is_file(),
                "write_used": False,
                "evidence": f"{sched_jobs} Jobs" if sched.is_file() else "fehlt",
                "status": "AVAILABLE" if sched_jobs > 0 else "NOT_CONFIGURED",
            }
        )

    db = autopost_db_path()
    posts_n = 0
    if db.is_file():
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                posts_n = int(con.execute("SELECT COUNT(*) FROM posts").fetchone()[0])
            finally:
                con.close()
        except Exception as e:
            sources.append(
                {
                    "id": "autopost_sqlite",
                    "name": "Planner autopost.db",
                    "path": str(db),
                    "exists": True,
                    "readable": False,
                    "write_used": False,
                    "evidence": f"error:{type(e).__name__}",
                    "status": "CONNECTION_FAILED",
                }
            )
            db = None  # type: ignore
    if db is not None:
        sources.append(
            {
                "id": "autopost_sqlite",
                "name": "Planner autopost.db (SQLite Queue)",
                "path": str(db),
                "exists": db.is_file(),
                "readable": db.is_file() and posts_n >= 0,
                "write_used": False,
                "evidence": f"{posts_n} Posts" if db.is_file() else "fehlt",
                "status": "AVAILABLE" if posts_n > 0 else "NOT_CONFIGURED",
            }
        )

    xlsx = images_root() / "Inst_Facebook GGG Clubs.xlsx"
    sources.append(
        {
            "id": "excel_pipeline",
            "name": "Inst_Facebook GGG Clubs.xlsx",
            "path": str(xlsx),
            "exists": xlsx.is_file(),
            "readable": xlsx.is_file(),
            "write_used": False,
            "evidence": "Pipeline-Status Excel" if xlsx.is_file() else "fehlt",
            "status": "AVAILABLE" if xlsx.is_file() else "NOT_CONFIGURED",
            "note": "Read-only Metadaten; kein vollständiger Caption-Check ohne openpyxl-Zwang",
        }
    )

    # Explicitly checked / not available for Nils
    sources.append(
        {
            "id": "google_drive",
            "name": "Google Drive",
            "path": None,
            "exists": False,
            "readable": False,
            "write_used": False,
            "evidence": "drive_search German Golf Guide / germangolfguide → 0 Treffer (Operator-MCP)",
            "status": "NOT_CONFIGURED",
        }
    )
    sources.append(
        {
            "id": "canva",
            "name": "Canva",
            "path": None,
            "exists": False,
            "readable": False,
            "write_used": False,
            "evidence": "Kein Canva-Connector/API-Key für Nils-Bot",
            "status": "NOT_CONFIGURED",
        }
    )
    sources.append(
        {
            "id": "meta_business_suite",
            "name": "Meta Business Suite / Graph (geplante Posts lesen)",
            "path": None,
            "exists": False,
            "readable": False,
            "write_used": False,
            "evidence": "Autopost-Queue lokal ja; Nils hat keinen Read-only Meta Graph Connector",
            "status": "NOT_CONFIGURED",
        }
    )
    sources.append(
        {
            "id": "n8n",
            "name": "n8n GGG Posting-Workflow",
            "path": None,
            "exists": False,
            "readable": False,
            "write_used": False,
            "evidence": "Vision erwähnt n8n; kein dedizierter GGG-Posting-Index in Nils-Runtime gefunden",
            "status": "NOT_CONFIGURED",
        }
    )

    return sources


def _max_severity(findings: list[Finding]) -> str:
    order = {s: i for i, s in enumerate(SEVERITY)}
    if not findings:
        return "info"
    return min((f.severity for f in findings), key=lambda s: order.get(s, 99))


def _norm(s: str) -> str:
    t = (s or "").lower()
    t = re.sub(r"[^a-z0-9äöüß\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _club_folder(dgv: str) -> Path:
    return images_root() / str(dgv)


def _load_editorial(dgv: str) -> dict[str, Any] | None:
    p = _club_folder(dgv) / "editorial_content.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_caption(dgv: str) -> str:
    p = _club_folder(dgv) / "caption.txt"
    if p.is_file():
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
    ed = _load_editorial(dgv)
    if ed and ed.get("caption"):
        return str(ed["caption"])
    return ""


def list_local_postings(*, limit: int = 100) -> list[dict[str, Any]]:
    root = images_root()
    if not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for d in sorted(root.iterdir(), key=lambda p: p.name):
        if not d.is_dir() or not d.name.isdigit():
            continue
        ed = _load_editorial(d.name) or {}
        out.append(
            {
                "posting_id": f"local:{d.name}",
                "dgv": d.name,
                "club_name": str(ed.get("display") or ""),
                "source": "local_hub_images",
                "path": str(d),
                "planned_at": None,
            }
        )
        if len(out) >= limit:
            break
    return out


def list_schedule_postings(*, limit: int = 100) -> list[dict[str, Any]]:
    path = schedule_mixed_path()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for job in data.get("jobs") or []:
        out.append(
            {
                "posting_id": str(job.get("id") or f"sched:{job.get('club_id')}"),
                "dgv": str(job.get("club_id") or ""),
                "club_name": str(job.get("club_name") or ""),
                "source": "schedule_json",
                "planned_at": job.get("scheduled_at"),
                "status": job.get("status"),
                "job_type": job.get("job_type"),
                "media_paths": job.get("media_paths") or [],
            }
        )
        if len(out) >= limit:
            break
    return out


def list_autopost_postings(
    *,
    limit: int = 100,
    status_in: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    db = autopost_db_path()
    if not db.is_file():
        return []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT id, title, caption, status, scheduled_at, media_paths, format, platform
            FROM posts
            ORDER BY COALESCE(scheduled_at, created_at) DESC
            LIMIT ?
            """,
            (limit * 2,),
        ).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        st = r["status"]
        if status_in and st not in status_in:
            continue
        title = r["title"] or ""
        m = re.match(r"^(\d{3,5})\b", title.strip())
        dgv = m.group(1) if m else ""
        out.append(
            {
                "posting_id": f"autopost:{r['id']}",
                "dgv": dgv,
                "club_name": title,
                "source": "autopost_sqlite",
                "planned_at": r["scheduled_at"],
                "status": st,
                "caption": r["caption"] or "",
                "media_paths": json.loads(r["media_paths"] or "[]"),
                "format": r["format"],
                "platform": r["platform"],
            }
        )
        if len(out) >= limit:
            break
    return out


def find_postings(
    *,
    query: str | None = None,
    dgv: str | None = None,
    timeframe_from: str | None = None,
    timeframe_to: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Merge sources read-only. Prefer schedule + autopost for planned dates."""
    items: list[dict[str, Any]] = []
    items.extend(list_autopost_postings(limit=limit))
    items.extend(list_schedule_postings(limit=limit))
    # local fill for clubs without queue entry
    known = {i.get("dgv") for i in items if i.get("dgv")}
    for loc in list_local_postings(limit=limit):
        if loc["dgv"] not in known:
            items.append(loc)

    q = _norm(query or "")
    out = []
    for it in items:
        if dgv and str(it.get("dgv")) != str(dgv):
            continue
        planned = it.get("planned_at") or ""
        if timeframe_from and planned and planned < timeframe_from:
            continue
        if timeframe_to and planned and planned > timeframe_to:
            continue
        if q:
            blob = _norm(f"{it.get('club_name')} {it.get('dgv')} {it.get('posting_id')} {it.get('caption','')}")
            if q not in blob and not all(part in blob for part in q.split() if len(part) > 2):
                continue
        out.append(it)
        if len(out) >= limit:
            break
    return out


def _spell_grammar_heuristics(text: str) -> list[Finding]:
    findings: list[Finding] = []
    if not text.strip():
        findings.append(
            Finding("empty_caption", "high", "Caption/Text leer", "Caption ergänzen")
        )
        return findings
    # Obvious doubles
    if re.search(r"\b(\w+)\s+\1\b", text, re.I):
        findings.append(
            Finding(
                "duplicate_word",
                "medium",
                "Doppeltes Wort in Caption",
                "Wiederholung entfernen",
            )
        )
    # Very rough DE issues
    if "  " in text:
        findings.append(
            Finding("double_space", "low", "Doppelte Leerzeichen", "Leerzeichen bereinigen")
        )
    if re.search(r"[a-zäöüß]\.[A-ZÄÖÜ]", text):
        findings.append(
            Finding(
                "spacing_after_period",
                "low",
                "Fehlendes Leerzeichen nach Punkt",
                "Leerzeichen nach Satzzeichen setzen",
            )
        )
    return findings


def _check_assets(dgv: str, media_paths: list[str] | None = None) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    folder = _club_folder(dgv)
    details: dict[str, Any] = {"folder": str(folder), "files": []}
    if media_paths:
        paths = [Path(p) for p in media_paths]
    else:
        paths = []
        for slide in EXPECTED_FEED_SLIDES:
            paths.append(folder / f"club_{dgv}_{slide}.png")
        paths.append(folder / f"club_{dgv}_story.png")

    existing = []
    missing = []
    for p in paths:
        details["files"].append({"path": str(p), "exists": p.is_file(), "size": p.stat().st_size if p.is_file() else 0})
        if p.is_file() and p.stat().st_size > 1024:
            existing.append(p.name)
        else:
            missing.append(p.name)

    if missing:
        findings.append(
            Finding(
                "missing_image",
                "critical",
                f"Fehlende/leere Bilddateien: {', '.join(missing)}",
                "Fehlende Slides/Story erzeugen",
            )
        )

    # Slide count for feed pack
    feed_present = [s for s in EXPECTED_FEED_SLIDES if (folder / f"club_{dgv}_{s}.png").is_file()]
    if dgv and folder.is_dir():
        if len(feed_present) not in (0, 3) and len(feed_present) < 3:
            findings.append(
                Finding(
                    "wrong_slide_count",
                    "high",
                    f"Feed-Slides vorhanden: {len(feed_present)}/3 ({', '.join(feed_present) or 'keine'})",
                    "Genau slide1–slide3 gemäß GGG-Produktionsregel",
                )
            )
        elif len(feed_present) == 0 and not media_paths:
            findings.append(
                Finding(
                    "wrong_slide_count",
                    "critical",
                    "Keine Feed-Slides gefunden",
                    "Pipeline für Club neu laufen lassen",
                )
            )

    # Logo asset in brand kit (not pixel proof on slide)
    assets = hub_root() / "assets"
    logo_files = list(assets.glob("*logo*.png")) if assets.is_dir() else []
    if not logo_files:
        # alternate known path
        for alt in (
            hub_root() / "assets" / "ggg-logo-wide.png",
            hub_root() / "assets" / "ggg-logo-round.png",
        ):
            if alt.is_file():
                logo_files.append(alt)
    if not logo_files:
        findings.append(
            Finding(
                "missing_logo_asset",
                "high",
                "GGG-Logo-Asset im Hub nicht gefunden",
                "assets/ggg-logo-wide.png bzw. ggg-logo-round.png prüfen",
            )
        )
    else:
        details["logo_assets"] = [str(p) for p in logo_files[:4]]
        findings.append(
            Finding(
                "logo_on_slide_unverified",
                "info",
                "Logo-Asset vorhanden; Sichtbarkeit auf Slide nicht pixelgeprüft (kein Vision-OCR)",
                "Visuell freigeben oder Vision-Probe ergänzen",
            )
        )

    return findings, details


def check_posting(
    posting: dict[str, Any] | None = None,
    *,
    posting_id: str | None = None,
    expected_club_name: str | None = None,
    cancel_check: CancelCheck | None = None,
    visual: bool = False,
) -> PostingCheckResult:
    """Read-only check of one posting. Never mutates sources."""
    if cancel_check and cancel_check():
        raise GggCheckError("cancelled", "Stop während Prüfung")

    if posting is None:
        if not posting_id:
            raise GggCheckError("not_found", "kein posting_id")
        found = find_postings(query=posting_id, limit=20)
        posting = next((p for p in found if p["posting_id"] == posting_id), None)
        if posting is None and posting_id.startswith("local:"):
            dgv = posting_id.split(":", 1)[1]
            if dgv.isdigit() and _club_folder(dgv).is_dir():
                posting = {
                    "posting_id": posting_id,
                    "dgv": dgv,
                    "club_name": (_load_editorial(dgv) or {}).get("display") or "",
                    "source": "local_hub_images",
                    "planned_at": None,
                }
        if posting is None:
            return PostingCheckResult(
                posting_id=posting_id,
                planned_at=None,
                source="unknown",
                result="not_found",
                findings=[Finding("not_found", "critical", "Posting nicht gefunden", "ID/Quelle prüfen")],
                evidence_ref="",
            )

    if cancel_check and cancel_check():
        raise GggCheckError("cancelled", "Stop während Prüfung")

    dgv = str(posting.get("dgv") or "")
    club = str(posting.get("club_name") or "")
    caption = str(posting.get("caption") or "") or (_load_caption(dgv) if dgv else "")
    editorial = _load_editorial(dgv) if dgv else None
    display = str((editorial or {}).get("display") or club)
    findings: list[Finding] = []

    # Club name
    if expected_club_name:
        if _norm(expected_club_name) not in _norm(caption + " " + display):
            findings.append(
                Finding(
                    "wrong_club_name",
                    "critical",
                    f"Erwarteter Clubname '{expected_club_name}' nicht in Caption/Editorial",
                    "Clubname korrigieren",
                )
            )
    elif display and caption and _norm(display.split()[0]) not in _norm(caption):
        # soft: first token of display should appear
        if len(display) > 3 and _norm(display) not in _norm(caption):
            findings.append(
                Finding(
                    "club_name_weak",
                    "medium",
                    "Clubname aus Editorial kaum in Caption wiederzufinden",
                    "Clubname in Caption klar nennen",
                )
            )

    findings.extend(_spell_grammar_heuristics(caption))

    # CTA
    blob = _norm(caption + " " + json.dumps(editorial or {}, ensure_ascii=False))
    cta_hits = [m for m in CTA_MARKERS if m in blob]
    if not cta_hits:
        findings.append(
            Finding(
                "missing_cta",
                "high",
                "CTA/GGG-Marke in Text nicht gefunden",
                "CTA ergänzen: Jetzt informieren auf / German Golf Guide / www.german-golf-guide.de",
            )
        )
    else:
        findings.append(
            Finding(
                "cta_text_ok",
                "info",
                f"CTA-Marker gefunden: {', '.join(cta_hits)}",
                "",
            )
        )
        if "www.german-golf-guide.de" not in blob and "german golf guide" in blob:
            findings.append(
                Finding(
                    "cta_visibility_weak",
                    "medium",
                    "GGG genannt, Domain CTA ggf. schwach",
                    "www.german-golf-guide.de explizit setzen",
                )
            )

    # Assets / slides
    asset_findings, asset_details = _check_assets(dgv, posting.get("media_paths"))
    findings.extend(asset_findings)

    # Scheduling
    planned = posting.get("planned_at")
    status = posting.get("status")
    if posting.get("source") in ("schedule_json", "autopost_sqlite"):
        if not planned:
            findings.append(
                Finding(
                    "missing_schedule",
                    "high",
                    "Kein geplanter Termin",
                    "scheduled_at setzen",
                )
            )
        if status in ("needs_generation", "draft") and not planned:
            findings.append(
                Finding(
                    "not_scheduled",
                    "high",
                    f"Status={status} ohne Terminierung",
                    "Terminieren oder freigeben",
                )
            )

    # Duplicate content across caption lines
    lines = [ln.strip() for ln in caption.splitlines() if ln.strip()]
    if len(lines) != len(set(lines)) and len(lines) > 1:
        findings.append(
            Finding(
                "duplicate_content",
                "medium",
                "Identische Caption-Zeilen",
                "Duplikate entfernen",
            )
        )

    # Text/image mismatch: editorial display vs folder
    if dgv and editorial and str(editorial.get("dgv") or dgv) != dgv:
        findings.append(
            Finding(
                "text_image_mismatch",
                "critical",
                f"Editorial dgv={editorial.get('dgv')} ≠ Ordner {dgv}",
                "Zuordnung korrigieren",
            )
        )

    # Fact contradictions light: empty stats
    if editorial and not editorial.get("stats") and not editorial.get("hook_lines"):
        findings.append(
            Finding(
                "fact_gap",
                "medium",
                "Editorial ohne Stats/Hooks",
                "Fakten ergänzen",
            )
        )

    if cancel_check and cancel_check():
        raise GggCheckError("cancelled", "Stop während Prüfung")

    sev = _max_severity([f for f in findings if f.severity != "info"])
    if any(f.code == "not_found" for f in findings):
        result = "not_found"
    elif sev in ("critical", "high"):
        result = "fail"
    elif sev == "medium":
        result = "warn"
    else:
        result = "pass"

    evidence = posting.get("path") or ""
    if dgv:
        evidence = evidence or str(_club_folder(dgv))
    if posting.get("source") == "autopost_sqlite":
        evidence = f"{autopost_db_path()}#{posting_id or posting.get('posting_id')}"

    visual_report: dict[str, Any] | None = None
    if visual and dgv:
        try:
            from nils_job_runtime import ggg_visual_check as vis

            visual_report = vis.analyze_posting_visual(
                dgv=dgv,
                club_name=expected_club_name or display or club,
                images_dir=images_root(),
                hub_root=hub_root(),
                planned_at=planned,
                posting_id=str(posting.get("posting_id")),
                source=str(posting.get("source")),
                cancel_check=cancel_check,
            )
            # Map visual overall into textual result (never upgrade FAIL away)
            vo = visual_report.get("gesamtstatus")
            if vo == "FAIL":
                result = "fail"
            elif vo == "INCOMPLETE_CHECK" and result == "pass":
                result = "warn"
            elif vo == "PASS_WITH_WARNINGS" and result == "pass":
                result = "warn"
            # Surface critical visual fails as findings
            for slide in visual_report.get("slides") or []:
                for err in slide.get("fehler") or []:
                    findings.append(
                        Finding(
                            code=f"visual:{err.get('regel_id')}",
                            severity=str(err.get("schweregrad") or "high"),
                            message=f"[{slide.get('slide')}] {err.get('begruendung')}",
                            suggestion=str(err.get("empfohlene_korrektur") or ""),
                        )
                    )
        except RuntimeError as e:
            if "cancelled" in str(e).lower():
                raise GggCheckError("cancelled", "Stop während Prüfung") from e
            raise
        except Exception as e:  # noqa: BLE001
            findings.append(
                Finding(
                    "visual_engine_error",
                    "high",
                    f"Visuelle Prüfung fehlgeschlagen: {type(e).__name__}:{e}",
                    "Engine/Dependencies prüfen",
                )
            )
            result = "fail"
            visual_report = {"gesamtstatus": "INCOMPLETE_CHECK", "error": f"{type(e).__name__}:{e}"}

    return PostingCheckResult(
        posting_id=str(posting.get("posting_id")),
        planned_at=planned,
        source=str(posting.get("source")),
        result=result,
        findings=findings,
        evidence_ref=evidence,
        club_name=display or club,
        dgv=dgv,
        details={
            "status": status,
            "assets": asset_details,
            "caption_len": len(caption),
            "read_only": True,
            "mutations": False,
            "visual": visual_report,
            "gesamtstatus_visual": (visual_report or {}).get("gesamtstatus"),
        },
    )


def run_check_batch(
    *,
    query: str | None = None,
    limit: int = 10,
    cancel_check: CancelCheck | None = None,
    project: str | None = None,
    visual: bool = False,
) -> dict[str, Any]:
    """Find + check. Hard-lock project to German Golf Guide when set."""
    if project and "golf" not in project.lower() and project.lower() not in ("ggg", "german golf guide", "agency"):
        raise GggCheckError("wrong_project", f"Projekt '{project}' ist nicht German Golf Guide")

    inv = inventory_sources()
    usable = [s for s in inv if s.get("status") == "AVAILABLE"]
    if not usable:
        return {
            "ok": False,
            "status": "NOT_CONFIGURED",
            "inventory": inv,
            "results": [],
            "message": "Keine lesbare GGG-Posting-Quelle",
        }

    try:
        found = find_postings(query=query, limit=limit)
    except Exception as e:
        return {
            "ok": False,
            "status": "CONNECTION_FAILED",
            "inventory": inv,
            "results": [],
            "error": f"{type(e).__name__}:{e}",
        }

    results = []
    for item in found:
        if cancel_check and cancel_check():
            return {
                "ok": False,
                "status": "CANCELLED",
                "inventory": inv,
                "results": results,
                "message": "Stop während Prüfung",
            }
        try:
            results.append(
                check_posting(item, cancel_check=cancel_check, visual=visual).to_dict()
            )
        except GggCheckError as e:
            if e.code == "cancelled":
                return {
                    "ok": False,
                    "status": "CANCELLED",
                    "inventory": inv,
                    "results": results,
                    "message": e.detail,
                }
            raise

    return {
        "ok": True,
        "status": "AVAILABLE",
        "inventory": inv,
        "found": len(found),
        "results": results,
        "read_only": True,
        "publish": False,
        "visual": visual,
    }


def capability_status_from_inventory() -> dict[str, Any]:
    inv = inventory_sources()
    local_ok = any(s["id"] == "local_hub_images" and s["status"] == "AVAILABLE" for s in inv)
    queue_ok = any(
        s["id"] in ("autopost_sqlite", "schedule_json") and s["status"] == "AVAILABLE" for s in inv
    )
    base = {
        "inventory": inv,
        "canva.design_read": "NOT_CONFIGURED",
        "posting.publish": "DISABLED_BY_POLICY",
        "posting.find": "NOT_CONFIGURED",
        "ggg.postings_find": "NOT_CONFIGURED",
        "posting.text_check": "NOT_CONFIGURED",
        "posting.asset_check": "NOT_CONFIGURED",
        "posting.image_read": "NOT_CONFIGURED",
        "posting.visual_check": "NOT_CONFIGURED",
        "posting.check": "NOT_CONFIGURED",
    }
    if not (local_ok or queue_ok):
        return base

    sample = find_postings(limit=1)
    if not sample:
        base.update(
            {
                "ggg.postings_find": "DEGRADED",
                "posting.find": "DEGRADED",
                "cause": "Quelle da, aber keine Postings gelistet",
            }
        )
        return base

    try:
        r = check_posting(sample[0], visual=False)
        ok = r.result in ("pass", "warn", "fail")
        text_st = "AVAILABLE" if ok else "DEGRADED"
        asset_st = (
            "AVAILABLE"
            if (sample[0].get("dgv") and _club_folder(str(sample[0]["dgv"])).is_dir())
            else "DEGRADED"
        )
        visual_st = "NOT_CONFIGURED"
        visual_detail = None
        try:
            from nils_job_runtime import ggg_visual_check as vis

            info = vis.visual_engine_info()
            if not info.get("ocr_ready"):
                visual_st = "DEGRADED"
                visual_detail = info.get("ocr_error") or "OCR nicht bereit"
            else:
                # Prove on one real local PNG if possible
                dgv = str(sample[0].get("dgv") or "")
                folder = _club_folder(dgv)
                slide = folder / f"club_{dgv}_slide1.png"
                if slide.is_file():
                    one = vis.analyze_slide(
                        slide,
                        slide_name="slide1",
                        expected_club=str(sample[0].get("club_name") or ""),
                        hub_root=hub_root(),
                    )
                    # AVAILABLE only if engine produced rule statuses including non-PASS possibilities
                    statuses = {x["status"] for x in one.get("regeln") or []}
                    if "NOT_CHECKABLE" in statuses and len(statuses) == 1:
                        visual_st = "DEGRADED"
                    else:
                        visual_st = "AVAILABLE"
                    visual_detail = {
                        "sample_slide": str(slide),
                        "slide_status": one.get("status"),
                        "rule_statuses": sorted(statuses),
                    }
                else:
                    visual_st = "DEGRADED"
                    visual_detail = "Kein slide1 für Sample"
        except Exception as e:  # noqa: BLE001
            visual_st = "CONNECTION_FAILED"
            visual_detail = f"{type(e).__name__}:{e}"

        check_st = text_st if visual_st != "AVAILABLE" else "AVAILABLE"
        base.update(
            {
                "ggg.postings_find": "AVAILABLE",
                "posting.find": "AVAILABLE",
                "posting.text_check": text_st,
                "posting.asset_check": asset_st,
                "posting.image_read": asset_st,
                "posting.visual_check": visual_st,
                "posting.check": check_st,
                "sample_posting_id": r.posting_id,
                "sample_result": r.result,
                "visual_detail": visual_detail,
            }
        )
        return base
    except Exception as e:
        base.update(
            {
                "ggg.postings_find": "CONNECTION_FAILED",
                "posting.find": "CONNECTION_FAILED",
                "posting.check": "CONNECTION_FAILED",
                "cause": f"{type(e).__name__}:{e}",
            }
        )
        return base

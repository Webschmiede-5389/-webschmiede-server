# -*- coding: utf-8 -*-
"""Nils Google Drive — nur Agency-Sales-Root (Zug F / SM-4)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

# Unter Webschmiede/ angelegt 2026-08-01
DEFAULT_ROOT_ID = "1tk3sGwp0NJYim9QKdj9SzMnoF4kjxb9p"


class DriveError(Exception):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _truthy(name: str, default: str = "0") -> bool:
    return (os.getenv(name) or default).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class DriveConfig:
    enabled: bool = False
    root_id: str = ""
    root_name: str = "Agency-Sales"

    @classmethod
    def from_env(cls) -> "DriveConfig":
        return cls(
            enabled=_truthy("NILS_CAP_DRIVE", "0"),
            root_id=(
                os.getenv("NILS_DRIVE_ROOT_ID") or DEFAULT_ROOT_ID
            ).strip(),
            root_name=(os.getenv("NILS_DRIVE_ROOT_NAME") or "Agency-Sales").strip(),
        )


def _access_token() -> str:
    from nils_job_runtime.calendar_connector import _google_access_token

    try:
        return _google_access_token()
    except Exception as e:
        raise DriveError("not_configured", f"OAuth: {e}") from e


def _drive_request(
    method: str,
    path: str,
    *,
    query: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    base: str = "https://www.googleapis.com/drive/v3",
) -> dict[str, Any]:
    token = _access_token()
    q = urllib.parse.urlencode(query or {})
    url = f"{base}{path}"
    if q:
        url = f"{url}?{q}"
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        if e.code in (401, 403):
            raise DriveError("permission_denied", detail) from e
        if e.code == 404:
            raise DriveError("not_found", detail) from e
        raise DriveError("connection_failed", f"HTTP {e.code}: {detail}") from e
    except DriveError:
        raise
    except Exception as e:
        raise DriveError("connection_failed", f"{type(e).__name__}: {e}") from e


def _multipart_drive_upload(
    *,
    name: str,
    parents: list[str],
    google_mime: str,
    media_mime: str,
    media_bytes: bytes,
) -> dict[str, Any]:
    token = _access_token()
    boundary = "=======nils_drive_boundary======="
    meta = json.dumps(
        {
            "name": name,
            "mimeType": google_mime,
            "parents": parents,
        },
        ensure_ascii=False,
    )
    parts = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{meta}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {media_mime}; charset=UTF-8\r\n\r\n"
    ).encode("utf-8") + media_bytes + f"\r\n--{boundary}--".encode("utf-8")
    q = urllib.parse.urlencode(
        {"uploadType": "multipart", "fields": "id,name,mimeType,webViewLink,parents"}
    )
    url = f"https://www.googleapis.com/upload/drive/v3/files?{q}"
    req = urllib.request.Request(
        url,
        data=parts,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        if e.code in (401, 403):
            raise DriveError("permission_denied", detail) from e
        raise DriveError("connection_failed", f"HTTP {e.code}: {detail}") from e
    except DriveError:
        raise
    except Exception as e:
        raise DriveError("connection_failed", f"{type(e).__name__}: {e}") from e


def _create_google_doc_with_text(
    *,
    name: str,
    parents: list[str],
    body: str,
) -> dict[str, Any]:
    """Doc inkl. Text nur über Drive-Upload (kein Docs-API-Enable nötig)."""
    return _multipart_drive_upload(
        name=name,
        parents=parents,
        google_mime="application/vnd.google-apps.document",
        media_mime="text/plain",
        media_bytes=(body or "").encode("utf-8"),
    )


def _csv_escape(cell: str) -> str:
    s = str(cell or "")
    if any(ch in s for ch in (",", '"', "\n", "\r", ";")):
        return '"' + s.replace('"', '""') + '"'
    return s


def _rows_to_csv(rows: list[list[str]]) -> bytes:
    lines = []
    for row in rows:
        lines.append(",".join(_csv_escape(c) for c in row))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _create_sheet_with_rows(
    *,
    name: str,
    parents: list[str],
    rows: list[list[str]],
) -> dict[str, Any]:
    """Spreadsheet inkl. Startzeilen via CSV→Google-Sheet (Drive-Scope reicht)."""
    return _multipart_drive_upload(
        name=name,
        parents=parents,
        google_mime="application/vnd.google-apps.spreadsheet",
        media_mime="text/csv",
        media_bytes=_rows_to_csv(rows),
    )


SHEETS_API_ENABLE_URL = (
    "https://console.developers.google.com/apis/api/"
    "sheets.googleapis.com/overview?project=995821377099"
)


def _sheets_request(
    method: str,
    path: str,
    *,
    query: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = _access_token()
    q = urllib.parse.urlencode(query or {})
    url = f"https://sheets.googleapis.com/v4{path}"
    if q:
        url = f"{url}?{q}"
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        low = detail.lower()
        if e.code in (401, 403) and (
            "has not been used" in low
            or "is disabled" in low
            or "is not enabled" in low
            or "access not configured" in low
            or ("sheets.googleapis.com" in low and "enable" in low)
        ):
            raise DriveError(
                "api_not_enabled",
                "Google Sheets API im GCP-Projekt aktivieren: " + SHEETS_API_ENABLE_URL,
            ) from e
        if e.code in (401, 403):
            raise DriveError("permission_denied", detail) from e
        if e.code == 404:
            raise DriveError("not_found", detail) from e
        raise DriveError("connection_failed", f"HTTP {e.code}: {detail}") from e
    except DriveError:
        raise
    except Exception as e:
        raise DriveError("connection_failed", f"{type(e).__name__}: {e}") from e


def probe_sheets_api() -> dict[str, Any]:
    """Leichter Check: Sheets API erreichbar? (kein Write)."""
    try:
        # spreadsheets.get auf ungültige ID → 404 = API an, 403 disabled = aus
        _sheets_request("GET", "/spreadsheets/1invalidprobe000000000000000000000")
        return {"ok": True, "status": "available"}
    except DriveError as e:
        if e.code == "api_not_enabled":
            return {
                "ok": False,
                "status": "api_not_enabled",
                "enable_url": SHEETS_API_ENABLE_URL,
                "detail": e.detail,
            }
        if e.code == "not_found":
            return {"ok": True, "status": "available"}
        if e.code == "permission_denied":
            # oft: API an, aber keine Rechte auf Fake-ID — zählt als API erreichbar
            detail = (e.detail or "").lower()
            if "has not been used" in detail or "is disabled" in detail:
                return {
                    "ok": False,
                    "status": "api_not_enabled",
                    "enable_url": SHEETS_API_ENABLE_URL,
                    "detail": e.detail,
                }
            return {"ok": True, "status": "available"}
        return {"ok": False, "status": e.code, "detail": e.detail}
    except Exception as e:
        return {"ok": False, "status": "error", "detail": f"{type(e).__name__}: {e}"}


class DriveConnector:
    def __init__(self, cfg: DriveConfig | None = None):
        self.cfg = cfg or DriveConfig.from_env()

    def _guard(self) -> None:
        if not self.cfg.enabled:
            raise DriveError("disabled_by_policy", "NILS_CAP_DRIVE aus")
        if not self.cfg.root_id:
            raise DriveError("not_configured", "NILS_DRIVE_ROOT_ID fehlt")

    def assert_in_root(self, file_id: str) -> dict[str, Any]:
        """Datei muss Root selbst sein oder Root als Parent haben (1 Ebene)."""
        self._guard()
        fid = (file_id or "").strip()
        if not fid:
            raise DriveError("wrong_folder", "file_id fehlt")
        if fid == self.cfg.root_id:
            return {"id": fid, "name": self.cfg.root_name, "parents": []}
        meta = _drive_request(
            "GET",
            f"/files/{urllib.parse.quote(fid, safe='')}",
            query={"fields": "id,name,parents,mimeType,webViewLink,trashed"},
        )
        if meta.get("trashed"):
            raise DriveError("not_found", "Datei im Papierkorb")
        parents = meta.get("parents") or []
        if self.cfg.root_id not in parents and fid != self.cfg.root_id:
            raise DriveError(
                "wrong_folder",
                "nur Dateien im Agency-Sales-Root erlaubt",
            )
        return meta

    def list_files(self, *, limit: int = 20, query: str = "") -> dict[str, Any]:
        self._guard()
        root = self.cfg.root_id
        q = f"'{root}' in parents and trashed=false"
        if (query or "").strip():
            safe = (query or "").replace("\\", "\\\\").replace("'", "\\'")
            q += f" and name contains '{safe}'"
        data = _drive_request(
            "GET",
            "/files",
            query={
                "q": q,
                "pageSize": str(max(1, min(limit, 50))),
                "fields": "files(id,name,mimeType,modifiedTime,webViewLink)",
                "orderBy": "modifiedTime desc",
            },
        )
        files = data.get("files") or []
        return {
            "ok": True,
            "root_id": root,
            "root_name": self.cfg.root_name,
            "files": files,
            "n": len(files),
        }

    def create_doc(
        self,
        *,
        title: str,
        body: str = "",
        approved: bool = False,
    ) -> dict[str, Any]:
        if not approved:
            raise DriveError("approval_required", "drive.doc_create")
        self._guard()
        name = (title or "Nils Notiz").strip()[:120]
        text = (body or "").strip()[:15000]
        if text:
            created = _create_google_doc_with_text(
                name=name,
                parents=[self.cfg.root_id],
                body=text,
            )
        else:
            created = _drive_request(
                "POST",
                "/files",
                query={"fields": "id,name,mimeType,webViewLink,parents"},
                payload={
                    "name": name,
                    "mimeType": "application/vnd.google-apps.document",
                    "parents": [self.cfg.root_id],
                },
            )
        doc_id = created.get("id") or ""
        if not doc_id:
            raise DriveError("connection_failed", "Doc ohne id")
        return {
            "ok": True,
            "file": created,
            "webViewLink": created.get("webViewLink") or "",
            "id": doc_id,
        }

    def create_sheet(
        self,
        *,
        title: str,
        approved: bool = False,
        rows: list[list[str]] | None = None,
    ) -> dict[str, Any]:
        """Tabelle im Root — optional mit Startzeilen (CSV-Upload, nur Drive-Scope)."""
        if not approved:
            raise DriveError("approval_required", "drive.sheet_create")
        self._guard()
        name = (title or "Nils Tabelle").strip()[:120]
        if rows:
            created = _create_sheet_with_rows(
                name=name, parents=[self.cfg.root_id], rows=rows
            )
        else:
            created = _drive_request(
                "POST",
                "/files",
                query={"fields": "id,name,mimeType,webViewLink,parents"},
                payload={
                    "name": name,
                    "mimeType": "application/vnd.google-apps.spreadsheet",
                    "parents": [self.cfg.root_id],
                },
            )
        return {
            "ok": True,
            "file": created,
            "webViewLink": created.get("webViewLink") or "",
            "id": created.get("id") or "",
            "rows": len(rows or []),
        }

    def find_sheet_by_name(self, title: str) -> dict[str, Any] | None:
        """Erste nicht gelöschte Spreadsheet im Root mit exaktem/teilweisem Namen."""
        self._guard()
        want = (title or "").strip()
        if not want:
            return None
        listed = self.list_files(limit=50, query=want)
        sheets = [
            f
            for f in (listed.get("files") or [])
            if "spreadsheet" in str(f.get("mimeType") or "")
        ]
        for f in sheets:
            if str(f.get("name") or "").strip().lower() == want.lower():
                return f
        return sheets[0] if sheets else None

    def append_rows(
        self,
        *,
        file_id: str,
        rows: list[list[str]],
        approved: bool = False,
        range_a1: str = "A1",
    ) -> dict[str, Any]:
        """Zeilen an bestehende Tabelle hängen (Sheets API). Root-Guard via Parent."""
        if not approved:
            raise DriveError("approval_required", "drive.sheet_write")
        self._guard()
        meta = self.assert_in_root(file_id)
        if "spreadsheet" not in str(meta.get("mimeType") or ""):
            raise DriveError("wrong_folder", "Datei ist keine Tabelle")
        values = [[str(c) for c in row] for row in (rows or []) if row]
        if not values:
            raise DriveError("not_configured", "keine Zeilen")
        data = _sheets_request(
            "POST",
            f"/spreadsheets/{urllib.parse.quote(file_id, safe='')}/values/"
            f"{urllib.parse.quote(range_a1, safe='')}:append",
            query={
                "valueInputOption": "USER_ENTERED",
                "insertDataOption": "INSERT_ROWS",
            },
            payload={"values": values},
        )
        return {
            "ok": True,
            "file": meta,
            "id": file_id,
            "webViewLink": meta.get("webViewLink") or "",
            "updatedRange": data.get("updates", {}).get("updatedRange")
            or data.get("updatedRange")
            or "",
            "rows": len(values),
            "mode": "append",
            "raw": data,
        }

    def write_sheet(
        self,
        *,
        title: str,
        rows: list[list[str]],
        approved: bool = False,
        create_if_missing: bool = True,
    ) -> dict[str, Any]:
        """Zeilen schreiben: Append in bestehende Tabelle, sonst CSV-Neu (Zug I/N)."""
        if not approved:
            raise DriveError("approval_required", "drive.sheet_write")
        want = (title or "").strip()
        existing = self.find_sheet_by_name(want)
        # auch „Titel (Nils)“ aus Zug-I-Fallback finden
        if not existing and want and not want.endswith("(Nils)"):
            existing = self.find_sheet_by_name(f"{want} (Nils)")
        fallback_reason = ""
        if existing and existing.get("id"):
            try:
                out = self.append_rows(
                    file_id=str(existing["id"]),
                    rows=rows,
                    approved=True,
                )
                out["created"] = False
                out["mode"] = "append"
                return out
            except DriveError as e:
                if e.code not in ("permission_denied", "api_not_enabled"):
                    raise
                fallback_reason = e.code
                want = f"{want} (Nils)" if not want.endswith("(Nils)") else want
        if not create_if_missing and not existing:
            raise DriveError(
                "not_found", f"Tabelle „{title}“ nicht im Agency-Sales-Root"
            )
        created = self.create_sheet(title=want, approved=True, rows=rows)
        created["created"] = True
        created["mode"] = "create_csv"
        if fallback_reason:
            created["fallback_reason"] = fallback_reason
        return created

    def trash_file(self, *, file_id: str, approved: bool = False) -> dict[str, Any]:
        """Datei im Agency-Sales-Root in den Papierkorb (Zug V)."""
        if not approved:
            raise DriveError("approval_required", "drive.trash")
        meta = self.assert_in_root(file_id)
        fid = str(meta.get("id") or file_id).strip()
        if fid == self.cfg.root_id:
            raise DriveError("wrong_folder", "Root selbst darf nicht gelöscht werden")
        updated = _drive_request(
            "PATCH",
            f"/files/{urllib.parse.quote(fid, safe='')}",
            query={"fields": "id,name,mimeType,trashed,webViewLink"},
            payload={"trashed": True},
        )
        return {
            "ok": True,
            "id": updated.get("id") or fid,
            "name": updated.get("name") or meta.get("name") or "",
            "trashed": bool(updated.get("trashed", True)),
            "file": updated,
        }


def format_sheet_write(result: dict[str, Any]) -> str:
    f = result.get("file") or {}
    mode = result.get("mode") or ("create" if result.get("created") else "write")
    lines = [
        "Drive Tabelle geschrieben",
        f"Name: {f.get('name') or '–'}",
        f"Modus: {mode}",
        f"Zeilen: {result.get('rows') or 0}",
    ]
    if result.get("updatedRange"):
        lines.append(f"Range: {result['updatedRange']}")
    if mode == "create_csv" and result.get("fallback_reason") == "api_not_enabled":
        lines.append(
            "Hinweis: Sheets-API noch aus — neue Datei statt Append. "
            f"Aktivieren: {SHEETS_API_ENABLE_URL}"
        )
    elif mode == "create_csv" and result.get("fallback_reason"):
        lines.append(
            f"Hinweis: Append nicht möglich ({result.get('fallback_reason')}) "
            "— neue Datei angelegt."
        )
    lines.append(f"Link: {result.get('webViewLink') or f.get('webViewLink') or '–'}")
    lines.append(f"Beleg: {result.get('id') or f.get('id') or '–'}")
    return "\n".join(lines)


def format_list(result: dict[str, Any]) -> str:
    files = result.get("files") or []
    lines = [
        f"Drive · {result.get('root_name') or 'Agency-Sales'}",
        f"Dateien: {result.get('n') or 0}",
        "",
    ]
    if not files:
        lines.append("(leer — Leg Kurzdoc: „Drive Doc Titel: … Text: …“)")
        return "\n".join(lines)
    for f in files[:15]:
        kind = "📁" if "folder" in str(f.get("mimeType") or "") else "📄"
        if "spreadsheet" in str(f.get("mimeType") or ""):
            kind = "📊"
        lines.append(f"· {kind} {f.get('name') or '–'}")
        if f.get("webViewLink"):
            lines.append(f"  {f['webViewLink']}")
    return "\n".join(lines).strip()


def format_created(result: dict[str, Any], *, kind: str = "Doc") -> str:
    f = result.get("file") or {}
    return (
        f"Drive {kind} angelegt\n"
        f"Name: {f.get('name') or '–'}\n"
        f"Link: {result.get('webViewLink') or f.get('webViewLink') or '–'}\n"
        f"Beleg: {result.get('id') or f.get('id') or '–'}"
    )

# -*- coding: utf-8 -*-
"""Nils Google Calendar connector — isolierter Zielkalender (Hold oder Business)."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

_LOCK = threading.RLock()

# Hard denylist — never write here
FORBIDDEN_CALENDAR_IDS = frozenset(
    {
        "primary",
        "christian.kummetat@gmail.com",
    }
)

# Known isolated Hold calendar (operator inventory 2026-07-30)
DEFAULT_HOLD_ID = (
    "0b4d9c56c4cf8b842881af7129500498d6ffb9073ae199e742f3a52c93501775"
    "@group.calendar.google.com"
)

# Agency Business calendar (created 2026-08-01)
DEFAULT_WEBSCHMIEDE_ID = (
    "6e8446fa24a1b59fc261611c18accd008fc01fb2402567b6af15afb74e29188e"
    "@group.calendar.google.com"
)

TITLE_PREFIX = "NILS TEST – NICHT ECHT"
_BUSINESS_TARGETS = frozenset({"webschmiede", "business", "agency"})


class CalendarError(Exception):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


@dataclass
class CalendarConfig:
    enabled: bool = False
    backend: str = "mock"  # mock | google
    target_name: str = ""
    test_calendar_id: str = ""
    business_calendar_id: str = ""
    mode: str = "test"  # test | business
    token_status: str = "missing"  # missing | valid | expired | denied | mock
    timezone: str = "Europe/Berlin"
    allow_primary: bool = False  # must stay False
    user_mapping: str = "owner"

    @property
    def allowed_calendar_id(self) -> str:
        if self.mode == "business":
            return (self.business_calendar_id or self.test_calendar_id or "").strip()
        return (self.test_calendar_id or self.business_calendar_id or "").strip()

    @property
    def use_title_prefix(self) -> bool:
        return self.mode != "business"

    @classmethod
    def from_env(cls) -> "CalendarConfig":
        enabled = _truthy("NILS_CAP_CALENDAR", "0")
        backend = (os.getenv("NILS_CALENDAR_BACKEND") or "mock").strip().lower()
        target = (os.getenv("NILS_CALENDAR_TARGET") or "").strip()
        target_l = target.lower()
        mode_raw = (os.getenv("NILS_CALENDAR_MODE") or "").strip().lower()
        if mode_raw in ("business", "test"):
            mode = mode_raw
        elif target_l in _BUSINESS_TARGETS:
            mode = "business"
        else:
            mode = "test"

        test_id = (os.getenv("NILS_CALENDAR_TEST_ID") or "").strip()
        business_id = (os.getenv("NILS_CALENDAR_BUSINESS_ID") or "").strip()
        if not test_id and target_l in ("hold", "test", "nils-test"):
            test_id = DEFAULT_HOLD_ID
        if not business_id and target_l in _BUSINESS_TARGETS:
            business_id = DEFAULT_WEBSCHMIEDE_ID
        # Business-Ziel: TEST_ID darf die Business-ID tragen (ein erlaubter Kalender)
        if mode == "business" and not business_id and test_id:
            business_id = test_id
        if mode == "business" and not test_id and business_id:
            test_id = business_id

        token = (
            os.getenv("NILS_CALENDAR_TOKEN")
            or os.getenv("GOOGLE_CALENDAR_TOKEN")
            or ""
        ).strip()
        refresh = (os.getenv("NILS_GOOGLE_REFRESH_TOKEN") or "").strip()
        client_id = (os.getenv("NILS_GOOGLE_CLIENT_ID") or "").strip()
        client_secret = (os.getenv("NILS_GOOGLE_CLIENT_SECRET") or "").strip()

        if backend == "google":
            if token.lower() in ("expired", "invalid", "revoked"):
                token_status = "expired"
            elif token.lower() == "denied":
                token_status = "denied"
            elif refresh and client_id and client_secret:
                token_status = "valid"
            elif token and token.lower() not in ("mock", "valid", "valid-token", "1", ""):
                # raw refresh token in NILS_CALENDAR_TOKEN + client creds
                token_status = "valid" if client_id and client_secret else "missing"
            else:
                token_status = "missing"
        elif not token:
            token_status = "missing"
        elif token.lower() in ("expired", "invalid", "revoked"):
            token_status = "expired"
        elif token.lower() == "denied":
            token_status = "denied"
        elif token.lower() in ("mock", "valid", "valid-token", "1"):
            token_status = "mock" if backend == "mock" or token.lower() == "mock" else "valid"
        else:
            token_status = "valid"

        allow_primary = _truthy("NILS_CALENDAR_ALLOW_PRIMARY", "0")
        return cls(
            enabled=enabled,
            backend=backend if backend in ("mock", "google") else "mock",
            target_name=target,
            test_calendar_id=test_id,
            business_calendar_id=business_id,
            mode=mode,
            token_status=token_status,
            timezone=(os.getenv("NILS_CALENDAR_TZ") or "Europe/Berlin").strip(),
            allow_primary=allow_primary,
            user_mapping=(os.getenv("NILS_CALENDAR_USER") or "owner").strip(),
        )


def _truthy(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or default).lower() not in (
        "0",
        "false",
        "no",
        "off",
        "",
    )


def inspect_auth(cfg: CalendarConfig | None = None) -> dict[str, Any]:
    """Read-only auth/capability inspection — no secrets."""
    cfg = cfg or CalendarConfig.from_env()
    scopes_expected = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ]
    allowed = cfg.allowed_calendar_id
    return {
        "enabled": cfg.enabled,
        "backend": cfg.backend,
        "auth_mode": "mock_token" if cfg.backend == "mock" else "oauth_refresh",
        "token_status": cfg.token_status,
        "token_renewal": "n/a_mock" if cfg.backend == "mock" else "refresh_token_required",
        "target_name": cfg.target_name or None,
        "mode": cfg.mode,
        "test_calendar_id_set": bool(cfg.test_calendar_id),
        "business_calendar_id_set": bool(cfg.business_calendar_id),
        "allowed_calendar_id_set": bool(allowed),
        "test_calendar_id_suffix": (cfg.test_calendar_id[-24:] if cfg.test_calendar_id else None),
        "business_calendar_id_suffix": (
            cfg.business_calendar_id[-24:] if cfg.business_calendar_id else None
        ),
        "allow_primary": cfg.allow_primary,
        "user_mapping": cfg.user_mapping,
        "timezone": cfg.timezone,
        "scopes_expected": scopes_expected,
        "scopes_verified_for_nils": False if cfg.backend != "mock" else ["mock.calendar"],
        "operator_mcp_separate": True,
        "read_rights": cfg.enabled and cfg.token_status in ("mock", "valid"),
        "write_rights": cfg.enabled
        and cfg.token_status in ("mock", "valid")
        and bool(allowed),
        "notes": [
            "Operator Google Workspace MCP ≠ Nils-Bot-Connector",
            "Writes nur in erlaubtem Zielkalender (Hold/Test oder webschmiede), nie primary",
        ],
    }


def assert_test_calendar(calendar_id: str | None, cfg: CalendarConfig) -> str:
    """Nur den einen konfigurierten Zielkalender (Test oder Business) erlauben."""
    allowed = cfg.allowed_calendar_id
    cid = (calendar_id or allowed or "").strip()
    if not cid:
        raise CalendarError("wrong_calendar", "keine Kalender-ID")
    low = cid.lower()
    if low in FORBIDDEN_CALENDAR_IDS or low == "primary":
        raise CalendarError("forbidden_calendar", "Hauptkalender/primary gesperrt")
    if cfg.allow_primary:
        raise CalendarError("policy", "NILS_CALENDAR_ALLOW_PRIMARY darf nicht aktiv sein")
    if not allowed:
        raise CalendarError(
            "not_configured",
            "NILS_CALENDAR_TEST_ID / NILS_CALENDAR_BUSINESS_ID fehlt",
        )
    if cid != allowed:
        raise CalendarError(
            "wrong_calendar",
            "nur konfigurierter Zielkalender erlaubt",
        )
    return cid


def _apply_title_prefix(title: str, cfg: CalendarConfig) -> str:
    title = (title or "").strip()
    if not cfg.use_title_prefix:
        return title
    if not title.startswith(TITLE_PREFIX):
        return f"{TITLE_PREFIX}: {title}"
    return title


def _google_creds() -> tuple[str, str, str]:
    client_id = (os.getenv("NILS_GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("NILS_GOOGLE_CLIENT_SECRET") or "").strip()
    refresh = (os.getenv("NILS_GOOGLE_REFRESH_TOKEN") or "").strip()
    if not refresh:
        tok = (os.getenv("NILS_CALENDAR_TOKEN") or "").strip()
        if tok.lower() not in ("", "mock", "valid", "valid-token", "1", "expired", "denied"):
            refresh = tok
    if not (client_id and client_secret and refresh):
        raise CalendarError("not_configured", "NILS_GOOGLE_* OAuth fehlt")
    return client_id, client_secret, refresh


def _google_access_token() -> str:
    client_id, client_secret, refresh = _google_creds()
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:240]
        if e.code in (400, 401):
            raise CalendarError("token_expired", detail) from e
        raise CalendarError("connection_failed", f"token HTTP {e.code}: {detail}") from e
    except Exception as e:
        raise CalendarError("connection_failed", f"token: {type(e).__name__}: {e}") from e
    access = (data.get("access_token") or "").strip()
    if not access:
        raise CalendarError("token_expired", "kein access_token")
    return access


def _google_request(
    method: str,
    path: str,
    *,
    query: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = _google_access_token()
    q = urllib.parse.urlencode(query or {})
    url = f"https://www.googleapis.com/calendar/v3{path}"
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
            raise CalendarError("permission_denied", detail) from e
        if e.code == 404:
            raise CalendarError("not_found", detail) from e
        raise CalendarError("connection_failed", f"HTTP {e.code}: {detail}") from e
    except CalendarError:
        raise
    except Exception as e:
        raise CalendarError("connection_failed", f"{type(e).__name__}: {e}") from e


def _event_from_google(item: dict[str, Any], calendar_id: str) -> dict[str, Any]:
    start = item.get("start") or {}
    end = item.get("end") or {}
    start_iso = start.get("dateTime") or start.get("date") or ""
    end_iso = end.get("dateTime") or end.get("date") or ""
    attendees = [
        a.get("email")
        for a in (item.get("attendees") or [])
        if isinstance(a, dict) and a.get("email")
    ]
    return {
        "event_id": item.get("id") or "",
        "calendar_id": calendar_id,
        "summary": item.get("summary") or "",
        "description": item.get("description") or "",
        "start_iso": start_iso,
        "end_iso": end_iso,
        "timezone": start.get("timeZone") or "",
        "attendees_json": json.dumps(attendees, ensure_ascii=False),
        "status": item.get("status") or "confirmed",
        "html_link": item.get("htmlLink") or "",
        "backend": "google",
    }


def mock_db_path() -> Path:
    raw = os.getenv("NILS_CALENDAR_MOCK_DB")
    if raw:
        return Path(raw)
    if os.name == "nt":
        return Path(__file__).resolve().parents[3] / "agency" / "nils-calendar-mock.db"
    return Path("/var/lib/webschmiede/nils-calendar-mock.db")


def _mock_connect() -> sqlite3.Connection:
    p = mock_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS cal_events (
            event_id TEXT PRIMARY KEY,
            calendar_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            description TEXT,
            start_iso TEXT NOT NULL,
            end_iso TEXT NOT NULL,
            timezone TEXT NOT NULL,
            attendees_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'confirmed',
            idempotency_key TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(calendar_id, idempotency_key)
        )
        """
    )
    con.commit()
    return con


CancelCheck = Callable[[], bool]


@dataclass
class EventDraft:
    title: str
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str | None = None
    duration_minutes: int | None = None
    timezone: str = "Europe/Berlin"
    calendar_id: str | None = None
    attendees: list[str] = field(default_factory=list)
    description: str = ""
    idempotency_key: str | None = None

    def resolve_times(self) -> tuple[str, str]:
        if not self.end_time and not self.duration_minutes:
            raise CalendarError("preflight", "Endzeit oder Dauer fehlt")
        start = datetime.fromisoformat(f"{self.date}T{self.start_time}:00")
        if self.end_time:
            end = datetime.fromisoformat(f"{self.date}T{self.end_time}:00")
        else:
            end = start + timedelta(minutes=int(self.duration_minutes or 30))
        if end <= start:
            raise CalendarError("preflight", "Ende muss nach Start liegen")
        # store as naive local + tz label; ISO without forcing UTC conversion
        return start.isoformat(), end.isoformat()


def preflight_event_fields(draft: EventDraft, cfg: CalendarConfig | None = None) -> dict[str, Any]:
    """Preflight before create — title, date, times, tz, calendar, attendees, approval separate."""
    cfg = cfg or CalendarConfig.from_env()
    missing: list[str] = []
    if not (draft.title or "").strip():
        missing.append("titel")
    if not (draft.date or "").strip():
        missing.append("datum")
    if not (draft.start_time or "").strip():
        missing.append("startzeit")
    if not draft.end_time and not draft.duration_minutes:
        missing.append("endzeit_oder_dauer")
    if not (draft.timezone or cfg.timezone):
        missing.append("zeitzone")
    try:
        cal = assert_test_calendar(draft.calendar_id, cfg)
    except CalendarError as e:
        return {
            "ok": False,
            "missing": missing + ["zielkalender"],
            "error": f"{e.code}:{e.detail}",
        }
    if missing:
        return {"ok": False, "missing": missing, "calendar_id": cal}
    try:
        start_iso, end_iso = draft.resolve_times()
    except CalendarError as e:
        return {"ok": False, "missing": missing, "error": f"{e.code}:{e.detail}"}
    return {
        "ok": True,
        "missing": [],
        "calendar_id": cal,
        "start_iso": start_iso,
        "end_iso": end_iso,
        "timezone": draft.timezone or cfg.timezone,
        "attendees": list(draft.attendees or []),
        "title": draft.title.strip(),
    }


# --- Approval matrix ---
APPROVAL_MATRIX: dict[str, dict[str, Any]] = {
    "calendar.read": {"approval_required": False, "policy": "nach_bestehender_policy"},
    "calendar.freebusy": {"approval_required": False, "policy": "nach_bestehender_policy"},
    "calendar.availability": {"approval_required": False, "policy": "nach_bestehender_policy"},
    "calendar.prepare": {"approval_required": False, "policy": "ohne_schreibaktion"},
    "calendar.create": {"approval_required": True, "policy": "ausdrueckliche_freigabe"},
    "calendar.update": {"approval_required": True, "policy": "ausdrueckliche_freigabe"},
    "calendar.delete": {"approval_required": True, "policy": "ausdrueckliche_freigabe"},
    "calendar.invite": {"approval_required": True, "policy": "ausdrueckliche_freigabe"},
}


def approval_required(capability: str) -> bool:
    return bool(APPROVAL_MATRIX.get(capability, {}).get("approval_required"))


def ensure_approval(capability: str, *, approved: bool) -> None:
    if approval_required(capability) and not approved:
        raise CalendarError("approval_required", capability)


class CalendarConnector:
    """Isolated calendar ops. Default backend=mock."""

    def __init__(self, cfg: CalendarConfig | None = None):
        self.cfg = cfg or CalendarConfig.from_env()

    def _guard_enabled(self) -> None:
        if not self.cfg.enabled:
            raise CalendarError("disabled_by_policy", "NILS_CAP_CALENDAR aus")
        if self.cfg.token_status == "missing":
            raise CalendarError("not_configured", "Token fehlt")
        if self.cfg.token_status == "expired":
            raise CalendarError("token_expired", "Token abgelaufen")
        if self.cfg.token_status == "denied":
            raise CalendarError("permission_denied", "Schreib-/Leserecht verweigert")

    def list_events(
        self,
        *,
        calendar_id: str | None = None,
        time_min: str | None = None,
        time_max: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        self._guard_enabled()
        cid = assert_test_calendar(calendar_id, self.cfg)
        if self.cfg.backend == "google":
            q: dict[str, str] = {
                "maxResults": str(max(1, min(limit, 50))),
                "singleEvents": "true",
                "orderBy": "startTime",
            }
            if time_min:
                q["timeMin"] = time_min if "T" in time_min else f"{time_min}T00:00:00Z"
            if time_max:
                q["timeMax"] = time_max if "T" in time_max else f"{time_max}T23:59:59Z"
            data = _google_request(
                "GET",
                f"/calendars/{urllib.parse.quote(cid, safe='')}/events",
                query=q,
            )
            events = [
                _event_from_google(it, cid)
                for it in (data.get("items") or [])
                if isinstance(it, dict)
            ]
            return {"ok": True, "calendar_id": cid, "events": events, "backend": "google"}
        with _LOCK:
            con = _mock_connect()
            try:
                rows = con.execute(
                    """
                    SELECT * FROM cal_events
                    WHERE calendar_id=? AND status!='cancelled'
                    ORDER BY start_iso ASC LIMIT ?
                    """,
                    (cid, limit),
                ).fetchall()
                events = [dict(r) for r in rows]
                if time_min:
                    events = [e for e in events if e["start_iso"] >= time_min]
                if time_max:
                    events = [e for e in events if e["start_iso"] <= time_max]
                return {"ok": True, "calendar_id": cid, "events": events, "backend": "mock"}
            finally:
                con.close()

    def freebusy(
        self,
        *,
        calendar_id: str | None = None,
        time_min: str,
        time_max: str,
    ) -> dict[str, Any]:
        self._guard_enabled()
        cid = assert_test_calendar(calendar_id, self.cfg)
        listed = self.list_events(calendar_id=cid, time_min=time_min, time_max=time_max)
        busy = [
            {"start": e["start_iso"], "end": e["end_iso"], "summary": e["summary"]}
            for e in listed["events"]
        ]
        return {
            "ok": True,
            "calendar_id": cid,
            "time_min": time_min,
            "time_max": time_max,
            "busy": busy,
            "free": len(busy) == 0,
        }

    def prepare(self, draft: EventDraft) -> dict[str, Any]:
        """Prepare event payload without write."""
        self._guard_enabled()
        pf = preflight_event_fields(draft, self.cfg)
        if not pf.get("ok"):
            return {"ok": False, "prepared": False, **pf}
        title = _apply_title_prefix(pf["title"], self.cfg)
        desc_default = (
            "Via Nils · Kalender webschmiede"
            if self.cfg.mode == "business"
            else "Nils isolierter Testtermin"
        )
        return {
            "ok": True,
            "prepared": True,
            "write": False,
            "payload": {
                "summary": title,
                "start": pf["start_iso"],
                "end": pf["end_iso"],
                "timezone": pf["timezone"],
                "calendar_id": pf["calendar_id"],
                "attendees": pf["attendees"],
                "description": draft.description or desc_default,
            },
        }

    def create(
        self,
        draft: EventDraft,
        *,
        approved: bool = False,
        cancel_check: CancelCheck | None = None,
        invite: bool = False,
    ) -> dict[str, Any]:
        cap = "calendar.invite" if invite else "calendar.create"
        ensure_approval(cap, approved=approved)
        self._guard_enabled()
        if cancel_check and cancel_check():
            raise CalendarError("cancelled", "Stop während Erstellung")
        prepared = self.prepare(draft)
        if not prepared.get("ok"):
            return prepared
        if cancel_check and cancel_check():
            raise CalendarError("cancelled", "Stop während Erstellung")
        payload = prepared["payload"]
        cid = payload["calendar_id"]
        idem = draft.idempotency_key or None
        if self.cfg.backend == "google":
            body: dict[str, Any] = {
                "summary": payload["summary"],
                "description": payload["description"],
                "start": {
                    "dateTime": payload["start"],
                    "timeZone": payload["timezone"],
                },
                "end": {
                    "dateTime": payload["end"],
                    "timeZone": payload["timezone"],
                },
            }
            if payload.get("attendees"):
                body["attendees"] = [{"email": a} for a in payload["attendees"]]
            if idem:
                body["extendedProperties"] = {
                    "private": {"nils_idempotency_key": idem}
                }
            item = _google_request(
                "POST",
                f"/calendars/{urllib.parse.quote(cid, safe='')}/events",
                query={"sendUpdates": "all" if invite and payload.get("attendees") else "none"},
                payload=body,
            )
            return {
                "ok": True,
                "duplicate": False,
                "event": _event_from_google(item, cid),
                "backend": "google",
            }
        with _LOCK:
            con = _mock_connect()
            try:
                if idem:
                    existing = con.execute(
                        "SELECT * FROM cal_events WHERE calendar_id=? AND idempotency_key=?",
                        (cid, idem),
                    ).fetchone()
                    if existing:
                        return {
                            "ok": True,
                            "duplicate": True,
                            "event": dict(existing),
                            "backend": "mock",
                        }
                now = datetime.now(timezone.utc).isoformat()
                eid = f"mock-{uuid.uuid4().hex[:16]}"
                con.execute(
                    """
                    INSERT INTO cal_events (
                        event_id, calendar_id, summary, description, start_iso, end_iso,
                        timezone, attendees_json, status, idempotency_key, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        eid,
                        cid,
                        payload["summary"],
                        payload["description"],
                        payload["start"],
                        payload["end"],
                        payload["timezone"],
                        json.dumps(payload["attendees"], ensure_ascii=False),
                        "confirmed",
                        idem,
                        now,
                        now,
                    ),
                )
                con.commit()
                row = con.execute("SELECT * FROM cal_events WHERE event_id=?", (eid,)).fetchone()
                return {"ok": True, "duplicate": False, "event": dict(row), "backend": "mock"}
            finally:
                con.close()

    def get(self, event_id: str, *, calendar_id: str | None = None) -> dict[str, Any]:
        self._guard_enabled()
        cid = assert_test_calendar(calendar_id, self.cfg)
        if self.cfg.backend == "google":
            item = _google_request(
                "GET",
                f"/calendars/{urllib.parse.quote(cid, safe='')}/events/"
                f"{urllib.parse.quote(event_id, safe='')}",
            )
            return {"ok": True, "event": _event_from_google(item, cid)}
        with _LOCK:
            con = _mock_connect()
            try:
                row = con.execute(
                    "SELECT * FROM cal_events WHERE event_id=? AND calendar_id=?",
                    (event_id, cid),
                ).fetchone()
                if not row:
                    raise CalendarError("not_found", event_id)
                return {"ok": True, "event": dict(row)}
            finally:
                con.close()

    def update(
        self,
        event_id: str,
        *,
        approved: bool = False,
        calendar_id: str | None = None,
        summary: str | None = None,
        start_iso: str | None = None,
        end_iso: str | None = None,
    ) -> dict[str, Any]:
        ensure_approval("calendar.update", approved=approved)
        self._guard_enabled()
        cid = assert_test_calendar(calendar_id, self.cfg)
        if self.cfg.backend == "google":
            patch: dict[str, Any] = {}
            if summary is not None:
                patch["summary"] = _apply_title_prefix(summary, self.cfg)
            if start_iso is not None:
                patch["start"] = {
                    "dateTime": start_iso,
                    "timeZone": self.cfg.timezone,
                }
            if end_iso is not None:
                patch["end"] = {
                    "dateTime": end_iso,
                    "timeZone": self.cfg.timezone,
                }
            item = _google_request(
                "PATCH",
                f"/calendars/{urllib.parse.quote(cid, safe='')}/events/"
                f"{urllib.parse.quote(event_id, safe='')}",
                payload=patch,
            )
            return {"ok": True, "event": _event_from_google(item, cid)}
        with _LOCK:
            con = _mock_connect()
            try:
                row = con.execute(
                    "SELECT * FROM cal_events WHERE event_id=? AND calendar_id=?",
                    (event_id, cid),
                ).fetchone()
                if not row:
                    raise CalendarError("not_found", event_id)
                new_sum = summary or row["summary"]
                if summary:
                    new_sum = _apply_title_prefix(summary, self.cfg)
                con.execute(
                    """
                    UPDATE cal_events SET summary=?, start_iso=?, end_iso=?, updated_at=?
                    WHERE event_id=?
                    """,
                    (
                        new_sum,
                        start_iso or row["start_iso"],
                        end_iso or row["end_iso"],
                        datetime.now(timezone.utc).isoformat(),
                        event_id,
                    ),
                )
                con.commit()
                out = con.execute("SELECT * FROM cal_events WHERE event_id=?", (event_id,)).fetchone()
                return {"ok": True, "event": dict(out)}
            finally:
                con.close()

    def delete(
        self,
        event_id: str,
        *,
        approved: bool = False,
        calendar_id: str | None = None,
    ) -> dict[str, Any]:
        ensure_approval("calendar.delete", approved=approved)
        self._guard_enabled()
        cid = assert_test_calendar(calendar_id, self.cfg)
        if self.cfg.backend == "google":
            _google_request(
                "DELETE",
                f"/calendars/{urllib.parse.quote(cid, safe='')}/events/"
                f"{urllib.parse.quote(event_id, safe='')}",
            )
            return {"ok": True, "deleted": True, "event_id": event_id, "calendar_id": cid}
        with _LOCK:
            con = _mock_connect()
            try:
                row = con.execute(
                    "SELECT * FROM cal_events WHERE event_id=? AND calendar_id=?",
                    (event_id, cid),
                ).fetchone()
                if not row:
                    raise CalendarError("not_found", event_id)
                con.execute(
                    "UPDATE cal_events SET status='cancelled', updated_at=? WHERE event_id=?",
                    (datetime.now(timezone.utc).isoformat(), event_id),
                )
                con.commit()
                return {"ok": True, "deleted": True, "event_id": event_id, "calendar_id": cid}
            finally:
                con.close()

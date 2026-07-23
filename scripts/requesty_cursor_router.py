#!/usr/bin/env python3
"""
Requesty Cursor-Router: wählt Modell automatisch nach Einsatzzweck (A/B/C).

Cursor → http://127.0.0.1:8787/v1  →  Requesty EU
Modell in Cursor: requesty-auto (oder beliebig – wird überschrieben)

Routen:
  A = schnell/günstig (Chat, kurze Fragen)
  B = Coding/Agent/Analyse (Tools, Code, lange Kontexte)
  C = Vision (Bilder/PDF)
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "requesty.secrets.local"
HOST = os.environ.get("REQUESTY_CURSOR_HOST", "127.0.0.1")
PORT = int(os.environ.get("REQUESTY_CURSOR_PORT", "8787"))
AUTO_MODEL = "requesty-auto"

_ROUTE_C = (
    "lieferschein", "rechnung", "pdf", "bild", "foto", "screenshot", "ocr",
    "extrahier", "beleg", "scan", "vision", "image", "screenshot",
)
_ROUTE_B = (
    "architektur", "strategie", "code", "refactor", "analysier", "komplex",
    "implementier", "python", "typescript", "docker", "sql", "agent",
    "composer", "tool", "funktion", "debug", "fehler", "fix", "deploy",
    "test", "unittest", "api", "endpoint", "class ", "function ", "diff",
)


def load_secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    if not SECRETS.is_file():
        raise SystemExit(f"Fehlt: {SECRETS}")
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


SECRETS_MAP = load_secrets()
GATEWAY = SECRETS_MAP.get("PRIMARY_LLM_GATEWAY", "https://router.eu.requesty.ai/v1").rstrip("/")
API_KEY = SECRETS_MAP.get("PRIMARY_API_KEY", "")
if not API_KEY:
    raise SystemExit("PRIMARY_API_KEY fehlt in requesty.secrets.local")

MODELS = {
    "A": [
        x.strip()
        for x in SECRETS_MAP.get(
            "CURSOR_ROUTE_A",
            SECRETS_MAP.get("REQUESTY_CHAT_MODEL", "mistral/mistral-small-latest"),
        ).split(",")
        if x.strip()
    ],
    "B": [
        x.strip()
        for x in SECRETS_MAP.get(
            "CURSOR_ROUTE_B",
            SECRETS_MAP.get("REQUESTY_SMART_MODEL", "bedrock/claude-sonnet-4@eu-central-1"),
        ).split(",")
        if x.strip()
    ],
    "C": [
        x.strip()
        for x in SECRETS_MAP.get(
            "CURSOR_ROUTE_C",
            SECRETS_MAP.get("REQUESTY_VISION_MODEL", "azure/gpt-4o-mini@swedencentral"),
        ).split(",")
        if x.strip()
    ],
}
# Fallback-Ketten ergänzen
if "azure/gpt-4o-mini@swedencentral" not in MODELS["A"]:
    MODELS["A"].append("azure/gpt-4o-mini@swedencentral")
if "azure/gpt-4o-mini@swedencentral" not in MODELS["B"]:
    MODELS["B"].append("azure/gpt-4o-mini@swedencentral")


def _text_from_messages(messages: list) -> str:
    parts: list[str] = []
    for m in messages or []:
        c = m.get("content")
        if isinstance(c, str):
            parts.append(c)
        elif isinstance(c, list):
            for block in c:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
    return "\n".join(parts)


def _has_image(messages: list) -> bool:
    for m in messages or []:
        c = m.get("content")
        if isinstance(c, list):
            for block in c:
                if isinstance(block, dict) and block.get("type") in (
                    "image_url",
                    "image",
                    "input_image",
                ):
                    return True
    return False


def classify(messages: list, tools: list | None, model_hint: str) -> str:
    """A=fast, B=coding/agent, C=vision."""
    hint = (model_hint or "").lower()
    if "vision" in hint or hint.endswith("-c") or "/c" in hint:
        return "C"
    if "smart" in hint or "coding" in hint or hint.endswith("-b") or "/b" in hint:
        return "B"
    if "fast" in hint or "cheap" in hint or hint.endswith("-a") or "/a" in hint:
        return "A"

    if _has_image(messages):
        return "C"
    if tools:
        return "B"

    text = _text_from_messages(messages).lower()
    # Agent/system signals
    for m in messages or []:
        role = (m.get("role") or "").lower()
        if role == "system" and len(str(m.get("content") or "")) > 800:
            return "B"
    if any(k in text for k in _ROUTE_C):
        return "C"
    if len(text) > 2500 or any(k in text for k in _ROUTE_B):
        return "B"
    # Cursor agent often sends tool_calls in history
    for m in messages or []:
        if m.get("tool_calls") or m.get("role") == "tool":
            return "B"
    return "A"


def pick_model(route: str) -> str:
    chain = MODELS.get(route) or MODELS["A"]
    return chain[0]


def forward(path: str, body: bytes | None, method: str = "POST", stream: bool = False):
    url = f"{GATEWAY}{path}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://digitalehandwerkskunst.de",
        "X-Title": "Webschmiede-Cursor-Router",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    return urllib.request.urlopen(req, timeout=300)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[requesty-cursor] " + (fmt % args) + "\n")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/models") or self.path.endswith("/v1/models"):
            payload = {
                "object": "list",
                "data": [
                    {
                        "id": AUTO_MODEL,
                        "object": "model",
                        "owned_by": "webschmiede-router",
                        "description": "Auto: A=fast, B=coding, C=vision",
                    },
                    {"id": "requesty-fast", "object": "model", "owned_by": "webschmiede-router"},
                    {"id": "requesty-coding", "object": "model", "owned_by": "webschmiede-router"},
                    {"id": "requesty-vision", "object": "model", "owned_by": "webschmiede-router"},
                ],
            }
            raw = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self._cors()
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        path = self.path.split("?")[0]

        if not path.endswith("/chat/completions"):
            sub = path[3:] if path.startswith("/v1") else path
            if not sub.startswith("/"):
                sub = "/" + sub
            try:
                resp = forward(sub, raw)
                data = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(data)))
                self._cors()
                self.end_headers()
                self.wfile.write(data)
            except urllib.error.HTTPError as e:
                body = e.read()
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self._cors()
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:  # noqa: BLE001
                msg = json.dumps({"error": str(e)}).encode()
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(msg)))
                self._cors()
                self.end_headers()
                self.wfile.write(msg)
            return

        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        messages = payload.get("messages") or []
        tools = payload.get("tools")
        model_hint = str(payload.get("model") or "")
        route = classify(messages, tools, model_hint)
        # Explicit aliases
        ml = model_hint.lower()
        if "requesty-fast" in ml:
            route = "A"
        elif "requesty-coding" in ml or "requesty-smart" in ml:
            route = "B"
        elif "requesty-vision" in ml:
            route = "C"

        chosen = pick_model(route)
        payload["model"] = chosen
        # Keine unbekannten Top-Level-Felder an Requesty (sonst 400 Invalid request format)
        payload.pop("requesty", None)

        stream = bool(payload.get("stream"))
        body = json.dumps(payload).encode("utf-8")
        self.log_message("route=%s model=%s stream=%s", route, chosen, stream)

        chain = MODELS.get(route) or MODELS["A"]
        last_err: Exception | None = None
        for attempt_model in chain:
            payload["model"] = attempt_model
            body = json.dumps(payload).encode("utf-8")
            try:
                resp = forward("/chat/completions", body)
                if stream:
                    self.send_response(200)
                    self.send_header("Content-Type", resp.headers.get("Content-Type", "text/event-stream"))
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self._cors()
                    self.end_headers()
                    while True:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    return
                data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("X-Requesty-Route", route)
                self.send_header("X-Requesty-Model", attempt_model)
                self._cors()
                self.end_headers()
                self.wfile.write(data)
                return
            except urllib.error.HTTPError as e:
                last_err = e
                err_body = e.read()
                self.log_message("fail model=%s code=%s %s", attempt_model, e.code, err_body[:200])
                if e.code in (400, 401, 403):
                    self.send_response(e.code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(err_body)))
                    self._cors()
                    self.end_headers()
                    self.wfile.write(err_body)
                    return
                continue
            except Exception as e:  # noqa: BLE001
                last_err = e
                self.log_message("error model=%s %s", attempt_model, e)
                continue

        msg = json.dumps({"error": {"message": f"all models failed: {last_err}"}}).encode()
        self.send_response(502)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(msg)))
        self._cors()
        self.end_headers()
        self.wfile.write(msg)


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Requesty Cursor-Router auf http://{HOST}:{PORT}/v1", flush=True)
    print(f"Gateway: {GATEWAY}", flush=True)
    print(f"Modelle A={MODELS['A'][0]} | B={MODELS['B'][0]} | C={MODELS['C'][0]}", flush=True)
    print(f"In Cursor: Base URL = http://{HOST}:{PORT}/v1  Modell = {AUTO_MODEL}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStop.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

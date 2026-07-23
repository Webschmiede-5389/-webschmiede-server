"""One-off: transcribe WhatsApp voice notes with faster-whisper."""
from __future__ import annotations

import json
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
FFMPEG = TOOLS / "ffmpeg.exe"
OUT = ROOT / "docs" / "memory" / "topics" / "kunden-sprachnachrichten-2026-07-17.json"

FILES = [
    Path(r"c:\Users\kumex\Downloads\WhatsApp Ptt 2026-07-17 at 13.31.23.ogg"),
    Path(r"c:\Users\kumex\Downloads\WhatsApp Ptt 2026-07-17 at 13.33.37.ogg"),
    Path(r"c:\Users\kumex\Downloads\WhatsApp Ptt 2026-07-17 at 13.34.24.ogg"),
    Path(r"c:\Users\kumex\Downloads\WhatsApp Ptt 2026-07-17 at 13.36.00.ogg"),
]


def ensure_ffmpeg() -> Path:
    TOOLS.mkdir(exist_ok=True)
    if FFMPEG.is_file():
        return FFMPEG
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    zpath = TOOLS / "ffmpeg.zip"
    print("Downloading ffmpeg…")
    urllib.request.urlretrieve(url, zpath)
    print("Extracting…")
    with zipfile.ZipFile(zpath) as zf:
        for name in zf.namelist():
            if name.replace("\\", "/").endswith("/ffmpeg.exe"):
                zf.extract(name, TOOLS)
                src = TOOLS / name
                FFMPEG.write_bytes(src.read_bytes())
                print("ffmpeg ready:", FFMPEG)
                return FFMPEG
    raise SystemExit("ffmpeg.exe not found in zip")


def main() -> None:
    import os

    ensure_ffmpeg()
    os.environ["PATH"] = str(TOOLS) + os.pathsep + os.environ.get("PATH", "")

    from faster_whisper import WhisperModel

    print("Loading Whisper model (small)…")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    results = []
    for f in FILES:
        print("===", f.name, "===")
        segments, info = model.transcribe(str(f), language="de", vad_filter=True)
        text = " ".join(s.text.strip() for s in segments).strip()
        print(text)
        print()
        results.append(
            {
                "file": f.name,
                "duration": getattr(info, "duration", None),
                "language": getattr(info, "language", "de"),
                "text": text,
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", OUT)


if __name__ == "__main__":
    main()

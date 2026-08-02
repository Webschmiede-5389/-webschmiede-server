# -*- coding: utf-8 -*-
"""Visual quality checks for GGG posting PNGs (read-only)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image

CancelCheck = Callable[[], bool]

_RULES_PATH = Path(__file__).with_name("ggg_design_rules.json")
_OCR_LOCK = threading.Lock()
_OCR_READER = None
_OCR_INIT_ERROR: str | None = None


@dataclass
class RuleResult:
    rule_id: str
    status: str  # PASS | WARNING | FAIL | NOT_CHECKABLE
    severity: str
    reason: str
    suggestion: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "regel_id": self.rule_id,
            "status": self.status,
            "schweregrad": self.severity,
            "begruendung": self.reason,
            "empfohlene_korrektur": self.suggestion,
            "beleg": self.evidence,
        }


def load_rules() -> dict[str, Any]:
    return json.loads(_RULES_PATH.read_text(encoding="utf-8"))


def visual_engine_info() -> dict[str, Any]:
    rules = load_rules()
    return {
        "rules_version": rules.get("version"),
        "engine": rules.get("analysis"),
        "ocr_ready": _get_ocr_reader() is not None,
        "ocr_error": _OCR_INIT_ERROR,
        "opencv": True,
        "pillow": True,
    }


def _get_ocr_reader():
    global _OCR_READER, _OCR_INIT_ERROR
    if _OCR_READER is not None or _OCR_INIT_ERROR:
        return _OCR_READER
    with _OCR_LOCK:
        if _OCR_READER is not None or _OCR_INIT_ERROR:
            return _OCR_READER
        try:
            import easyocr

            _OCR_READER = easyocr.Reader(["de", "en"], gpu=False, verbose=False)
        except Exception as e:  # noqa: BLE001
            _OCR_INIT_ERROR = f"{type(e).__name__}:{e}"
            _OCR_READER = None
        return _OCR_READER


def _bbox_from_quad(quad: list) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in quad]
    ys = [float(p[1]) for p in quad]
    return min(xs), min(ys), max(xs), max(ys)


def _intersection_area(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    return iw * ih


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    inter = _intersection_area(a, b)
    if inter <= 0:
        return 0.0
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def _iom(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    """Intersection over minimum area — catches partial overlaps better than IoU."""
    inter = _intersection_area(a, b)
    if inter <= 0:
        return 0.0
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    area_a = max(1.0, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1.0, (bx2 - bx1) * (by2 - by1))
    return inter / min(area_a, area_b)


def _vertical_stack_conflict(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    *,
    x_overlap_min: float = 0.45,
    max_gap_px: float = 2.0,
) -> bool:
    """True if boxes share horizontal span and vertically touch/overlap (stacked collision)."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    min_w = min(ax2 - ax1, bx2 - bx1)
    if min_w <= 1 or inter_x / min_w < x_overlap_min:
        return False
    # same text line (nearly identical y-range) → not a vertical stack collision
    ha, hb = max(1.0, ay2 - ay1), max(1.0, by2 - by1)
    y_inter = max(0.0, min(ay2, by2) - max(ay1, by1))
    y_union = ha + hb - y_inter
    if y_union > 0 and (y_inter / y_union) >= 0.65:
        return False
    if ay1 <= by1:
        gap = by1 - ay2
    else:
        gap = ay1 - by2
    return gap < max_gap_px


def _component_boxes(mask: np.ndarray, *, min_area: int = 400, min_h: int = 12, min_w: int = 40) -> list[tuple[float, float, float, float]]:
    n, _labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    boxes: list[tuple[float, float, float, float]] = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if int(area) < min_area or int(h) < min_h or int(w) < min_w:
            continue
        boxes.append((float(x), float(y), float(x + w), float(y + h)))
    return boxes


def _heterochrome_text_overlaps(img: np.ndarray, iom_fail: float) -> list[tuple[str, str, float]]:
    """Detect white-vs-yellow/gold text layers that occupy the same region (common overlap fail)."""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    white = cv2.inRange(hsv, (0, 0, 200), (180, 45, 255))
    yellow = cv2.inRange(hsv, (15, 60, 150), (45, 255, 255))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, kernel)
    yellow = cv2.morphologyEx(yellow, cv2.MORPH_CLOSE, kernel)
    wb = _component_boxes(white, min_area=600)
    yb = _component_boxes(yellow, min_area=600)

    def _in_logo_zone(box: tuple[float, float, float, float]) -> bool:
        x1, y1, x2, y2 = box
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        return cx >= w * 0.70 and cy <= h * 0.30

    yb = [b for b in yb if not _in_logo_zone(b)]
    hits: list[tuple[str, str, float]] = []
    for a in wb:
        for b in yb:
            iom = _iom(a, b)
            # nur echte Flächenüberlappung — kein bloßer Zeilenabstand
            if iom >= iom_fail:
                hits.append(("white_layer", "yellow_layer", round(iom, 2)))
    return hits[:5]


def _normalize_club_expectation(name: str | None) -> str:
    if not name:
        return ""
    s = str(name).strip()
    s = re.sub(r"^\d{3,5}\s+", "", s)
    s = re.sub(r"\s+story\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _phash(path: Path, hash_size: int = 8) -> int:
    im = Image.open(path).convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = list(im.getdata())
    # difference hash
    h = 0
    for row in range(hash_size):
        for col in range(hash_size):
            left = pixels[row * (hash_size + 1) + col]
            right = pixels[row * (hash_size + 1) + col + 1]
            h = (h << 1) | (1 if left > right else 0)
    return h


def _hamming(a: int, b: int) -> int:
    return int((a ^ b).bit_count())


def _open_cv_image(path: Path) -> np.ndarray | None:
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _contrast_delta(img: np.ndarray, bbox: tuple[float, float, float, float]) -> float | None:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w - 1, x2), min(h - 1, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # text vs local background: high vs low percentiles
    lo, hi = np.percentile(gray, [15, 85])
    return float(hi - lo)


def _run_ocr(path: Path) -> list[dict[str, Any]]:
    reader = _get_ocr_reader()
    if reader is None:
        return []
    raw = reader.readtext(str(path), detail=1, paragraph=False)
    out = []
    for quad, text, conf in raw:
        bbox = _bbox_from_quad(quad)
        out.append(
            {
                "text": str(text),
                "confidence": float(conf),
                "bbox": bbox,
                "height": float(bbox[3] - bbox[1]),
                "width": float(bbox[2] - bbox[0]),
            }
        )
    return out


def _detect_round_logo(img: np.ndarray, rules: dict[str, Any], hub_assets: Path) -> dict[str, Any]:
    """Detect GGG gold coin in top-right via gold mask + optional template."""
    h, w = img.shape[:2]
    logo_cfg = rules["logo"]
    safe = rules["safe_area"]["feed_top_right_logo_box"]
    x0 = int(w * float(safe["x_min_ratio"]))
    y1 = int(h * float(safe["y_max_ratio"]))
    roi = img[0:y1, x0:w]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (12, 60, 60), (45, 255, 255))
    gold_px = int(mask.sum() / 255)
    ys, xs = np.where(mask > 0)
    bbox = None
    if len(xs) > 50:
        bx1, by1, bx2, by2 = int(xs.min()) + x0, int(ys.min()), int(xs.max()) + x0, int(ys.max())
        bbox = (bx1, by1, bx2, by2)

    score = 0.0
    tloc = None
    logo_path = hub_assets / "ggg-logo-round.png"
    if logo_path.is_file():
        logo = cv2.imread(str(logo_path), cv2.IMREAD_UNCHANGED)
        if logo is not None:
            if logo.shape[2] == 4:
                bgr = logo[:, :, :3]
                a = logo[:, :, 3:4] / 255.0
                white = np.full_like(bgr, 255)
                logo = (bgr * a + white * (1 - a)).astype(np.uint8)
            glogo = cv2.cvtColor(logo, cv2.COLOR_BGR2GRAY)
            groi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            target_h = int(logo_cfg["round_expected_height_px"]["feed"])
            for hh in (target_h - 30, target_h, target_h + 30):
                if hh < 40:
                    continue
                scale = hh / glogo.shape[0]
                ww = max(20, int(glogo.shape[1] * scale))
                templ = cv2.resize(glogo, (ww, hh))
                if templ.shape[0] >= groi.shape[0] or templ.shape[1] >= groi.shape[1]:
                    continue
                res = cv2.matchTemplate(groi, templ, cv2.TM_CCOEFF_NORMED)
                _mn, mx, _ml, ml = cv2.minMaxLoc(res)
                if mx > score:
                    score = float(mx)
                    tloc = (ml[0] + x0, ml[1], ml[0] + x0 + ww, ml[1] + hh)

    present = gold_px >= int(logo_cfg["min_gold_pixels_top_right"]) or score >= float(
        logo_cfg["min_template_score"]
    )
    used_bbox = tloc or bbox
    return {
        "present": present,
        "gold_pixels": gold_px,
        "template_score": score,
        "bbox": used_bbox,
        "method": "gold+template",
    }


def analyze_slide(
    path: Path,
    *,
    slide_name: str,
    expected_club: str | None,
    hub_root: Path,
    rules: dict[str, Any] | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict[str, Any]:
    rules = rules or load_rules()
    results: list[RuleResult] = []
    sev_map = {r["id"]: r.get("severity", "medium") for r in rules.get("rules", [])}

    def add(rule_id: str, status: str, reason: str, suggestion: str = "", **ev: Any) -> None:
        results.append(
            RuleResult(
                rule_id=rule_id,
                status=status,
                severity=str(sev_map.get(rule_id, "medium")),
                reason=reason,
                suggestion=suggestion,
                evidence=ev,
            )
        )

    if cancel_check and cancel_check():
        raise RuntimeError("cancelled")

    # --- file integrity ---
    if not path.is_file():
        add("IMG_EXISTS", "FAIL", f"Datei fehlt: {path.name}", "Slide erzeugen", path=str(path))
        return _pack_slide(path, slide_name, results, [], {})

    add("IMG_EXISTS", "PASS", "Datei vorhanden", path=str(path), bytes=path.stat().st_size)

    if path.stat().st_size < int(rules["slides"]["min_file_bytes"]):
        add("IMG_NOT_EMPTY", "FAIL", "Datei zu klein / leer", "Neu rendern", bytes=path.stat().st_size)
    else:
        add("IMG_NOT_EMPTY", "PASS", "Dateigröße ausreichend", bytes=path.stat().st_size)

    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im2:
            width, height = im2.size
            mode = im2.mode
    except Exception as e:  # noqa: BLE001
        add("IMG_NOT_CORRUPT", "FAIL", f"PNG beschädigt/ungültig: {type(e).__name__}", "Datei neu exportieren")
        return _pack_slide(path, slide_name, results, [], {})

    add("IMG_NOT_CORRUPT", "PASS", "PNG lesbar", mode=mode)

    kind = "story" if "story" in slide_name.lower() else "feed"
    canvas = rules["canvas"][kind]
    ew, eh = int(canvas["width"]), int(canvas["height"])
    if width == ew and height == eh:
        add("IMG_DIMENSIONS", "PASS", f"{width}x{height}", expected=[ew, eh])
    else:
        add(
            "IMG_DIMENSIONS",
            "FAIL",
            f"Ist {width}x{height}, erwartet {ew}x{eh}",
            "Auf GGG-Canvas rendern",
            actual=[width, height],
            expected=[ew, eh],
        )

    aspect = width / height if height else 0
    exp_a = float(canvas["aspect"])
    if abs(aspect - exp_a) <= float(canvas["aspect_tol"]):
        add("IMG_ASPECT", "PASS", f"aspect={aspect:.4f}", expected=exp_a)
    else:
        add(
            "IMG_ASPECT",
            "FAIL",
            f"aspect={aspect:.4f} ≠ {exp_a}",
            "Seitenverhältnis korrigieren",
            actual=aspect,
            expected=exp_a,
        )

    img = _open_cv_image(path)
    if img is None:
        add("IMG_NOT_CORRUPT", "FAIL", "OpenCV konnte PNG nicht dekodieren", "Datei prüfen")
        return _pack_slide(path, slide_name, results, [], {"width": width, "height": height})

    if cancel_check and cancel_check():
        raise RuntimeError("cancelled")

    # --- OCR ---
    ocr_items: list[dict[str, Any]] = []
    if _get_ocr_reader() is None:
        for rid in (
            "CLUBNAME_PRESENT",
            "CLUBNAME_SIZE",
            "CLUBNAME_NOT_CROPPED",
            "CTA_PRESENT",
            "CTA_SIZE",
            "CTA_CONTRAST",
            "CTA_SAFE_AREA",
            "TEXT_IN_BOUNDS",
            "TEXT_NO_OVERLAP",
            "CLUB_MATCH",
            "BRANDING_HANDLE",
        ):
            add(rid, "NOT_CHECKABLE", f"OCR nicht verfügbar: {_OCR_INIT_ERROR}", "EasyOCR/Tesseract bereitstellen")
    else:
        ocr_items = _run_ocr(path)
        margin = float(rules["safe_area"]["margin_px"])
        # text in bounds / crop
        out_of_bounds = []
        for it in ocr_items:
            x1, y1, x2, y2 = it["bbox"]
            if x1 < -2 or y1 < -2 or x2 > width + 2 or y2 > height + 2:
                out_of_bounds.append(it["text"])
        if out_of_bounds:
            add(
                "TEXT_IN_BOUNDS",
                "FAIL",
                f"Text über Bildrand: {out_of_bounds[:3]}",
                "Layout/Safe Area prüfen",
                samples=out_of_bounds[:5],
            )
        else:
            add("TEXT_IN_BOUNDS", "PASS", "OCR-Boxen innerhalb Bild")

        # overlaps: OCR-Boxen mit starker Schnittmenge (Layer-Check nur opt-in, sonst FP auf Fotos)
        overlaps: list[Any] = []
        iou_fail = float(rules["text"]["overlap_iou_fail"])
        iom_fail = float(rules["text"].get("overlap_iom_fail", 0.45))
        min_conf = float(rules["text"]["min_ocr_confidence"])
        for i, a in enumerate(ocr_items):
            if a["confidence"] < min_conf or len(a["text"].strip()) < 3:
                continue
            for b in ocr_items[i + 1 :]:
                if b["confidence"] < min_conf or len(b["text"].strip()) < 3:
                    continue
                iou = _iou(a["bbox"], b["bbox"])
                iom = _iom(a["bbox"], b["bbox"])
                if iou < iou_fail and iom < iom_fail:
                    continue
                # nested kurze/numerische Fragmente (OCR-Artefakte) ignorieren
                shorter = a if len(a["text"]) <= len(b["text"]) else b
                st = shorter["text"].strip()
                if iom >= 0.85 and (
                    len(st) <= 4 or sum(ch.isdigit() or ch in ",.:;%" for ch in st) / max(1, len(st)) > 0.5
                ):
                    continue
                overlaps.append(
                    {
                        "a": a["text"],
                        "b": b["text"],
                        "iou": round(iou, 2),
                        "iom": round(iom, 2),
                    }
                )
        # White/Yellow-Layer nur auf expliziten Negativ-Fixtures (Fotos = zu viele Gold-Akzente)
        if os.environ.get("GGG_VISUAL_LAYER_OVERLAP") == "1":
            layer_hits = _heterochrome_text_overlaps(img, iom_fail=max(0.45, iom_fail))
            for hit in layer_hits:
                overlaps.append({"a": hit[0], "b": hit[1], "iom": hit[2], "layer": True})
        if overlaps:
            add(
                "TEXT_NO_OVERLAP",
                "FAIL",
                f"Überlappende Texte/Layer: {overlaps[:3]}",
                "Abstände erhöhen",
                overlaps=overlaps[:5],
            )
        else:
            add("TEXT_NO_OVERLAP", "PASS", "Keine starken Text-Überlappungen")

        # clubname: prefer top-left high conf
        club_box = None
        club_text = ""
        top_left = [
            it
            for it in ocr_items
            if it["bbox"][0] < width * 0.7
            and it["bbox"][1] < height * 0.25
            and it["confidence"] >= float(rules["text"]["min_ocr_confidence"])
        ]
        top_left.sort(key=lambda it: (it["bbox"][1], -it["height"]))
        if top_left:
            club_box = top_left[0]
            club_text = club_box["text"]
            add("CLUBNAME_PRESENT", "PASS", f"Clubname OCR: '{club_text}'", bbox=club_box["bbox"], confidence=club_box["confidence"])
            h_txt = club_box["height"]
            if h_txt < float(rules["text"]["clubname_min_height_px"]):
                add(
                    "CLUBNAME_SIZE",
                    "FAIL",
                    f"Clubname zu klein ({h_txt:.0f}px)",
                    f"Mindestens {rules['text']['clubname_warn_height_px']}px",
                    height=h_txt,
                )
            elif h_txt < float(rules["text"]["clubname_warn_height_px"]):
                add(
                    "CLUBNAME_SIZE",
                    "WARNING",
                    f"Clubname knapp ({h_txt:.0f}px)",
                    "Auf 32px anheben",
                    height=h_txt,
                )
            else:
                add("CLUBNAME_SIZE", "PASS", f"Clubname-Höhe {h_txt:.0f}px", height=h_txt)

            x1, y1, x2, y2 = club_box["bbox"]
            if x1 < margin or y1 < margin or x2 > width - margin:
                add(
                    "CLUBNAME_NOT_CROPPED",
                    "FAIL",
                    "Clubname nahe/über Safe-Area-Rand",
                    "Einrücken",
                    bbox=club_box["bbox"],
                )
            else:
                add("CLUBNAME_NOT_CROPPED", "PASS", "Clubname innerhalb Safe Area")
        else:
            add("CLUBNAME_PRESENT", "FAIL", "Kein Clubname im oberen Bereich erkannt", "Clubname oben links setzen")
            add("CLUBNAME_SIZE", "NOT_CHECKABLE", "Kein Clubname-BBox", "")
            add("CLUBNAME_NOT_CROPPED", "NOT_CHECKABLE", "Kein Clubname-BBox", "")

        if expected_club and club_text:
            if str(slide_name).lower() == "story" or "story" in path.name.lower():
                add(
                    "CLUB_MATCH",
                    "NOT_CHECKABLE",
                    "Story-Layout: Club-Match nicht strikt per OCR",
                    "",
                )
            else:
                exp = _normalize_club_expectation(expected_club).lower()
                got = club_text.lower()
                exp_toks = [t for t in exp.replace("-", " ").split() if len(t) > 2]
                hit = sum(1 for t in exp_toks if t in got)
                if hit == 0 and exp_toks:
                    add(
                        "CLUB_MATCH",
                        "FAIL",
                        f"OCR '{club_text}' passt nicht zu erwartet '{expected_club}'",
                        "Club-Zuordnung prüfen",
                    )
                else:
                    add("CLUB_MATCH", "PASS", f"Club-Zuordnung plausibel ('{club_text}')")
        elif expected_club and not club_text:
            add("CLUB_MATCH", "FAIL", "Erwarteter Club, aber kein OCR-Clubname", "Slide prüfen")
        else:
            add("CLUB_MATCH", "NOT_CHECKABLE", "Kein expected_club übergeben", "")

        # CTA / branding
        markers = [m.lower() for m in rules["text"]["cta_markers"]]
        handle_markers = [m.lower() for m in rules["text"]["handle_markers"]]
        cta_hits = []
        handle_hits = []
        for it in ocr_items:
            t = it["text"].lower().replace(" ", "")
            raw = it["text"].lower()
            for m in markers:
                if m.replace(" ", "") in t or m in raw:
                    cta_hits.append(it)
                    break
            for m in handle_markers:
                if m.replace("@", "") in t.replace("@", ""):
                    handle_hits.append(it)
                    break

        # CTA primarily expected on slide3; other slides: handle/branding enough as WARNING path
        need_strong_cta = slide_name.lower() in ("slide3", "club_slide3") or "slide3" in path.name
        if cta_hits:
            best = max(cta_hits, key=lambda it: it["height"])
            add(
                "CTA_PRESENT",
                "PASS",
                f"CTA/Brand-Text: '{best['text']}'",
                bbox=best["bbox"],
            )
            if best["height"] < float(rules["text"]["cta_min_height_px"]):
                add("CTA_SIZE", "FAIL", f"CTA zu klein ({best['height']:.0f}px)", "CTA vergrößern", height=best["height"])
            elif best["height"] < float(rules["text"]["cta_warn_height_px"]):
                add("CTA_SIZE", "WARNING", f"CTA knapp ({best['height']:.0f}px)", "CTA vergrößern", height=best["height"])
            else:
                add("CTA_SIZE", "PASS", f"CTA-Höhe {best['height']:.0f}px", height=best["height"])

            cd = _contrast_delta(img, best["bbox"])
            if cd is None:
                add("CTA_CONTRAST", "NOT_CHECKABLE", "Kontrast nicht messbar", "")
            elif cd < float(rules["text"]["contrast_min_delta"]):
                add("CTA_CONTRAST", "FAIL", f"CTA-Kontrast niedrig (Δ={cd:.0f})", "Kontrast erhöhen", delta=cd)
            else:
                add("CTA_CONTRAST", "PASS", f"CTA-Kontrast Δ={cd:.0f}", delta=cd)

            x1, y1, x2, y2 = best["bbox"]
            # CTA sitzt bewusst in der unteren Branding-Leiste — nur Rand/Crop und Links/Rechts prüfen
            bottom_bar = float(rules["safe_area"].get("feed_bottom_bar_px", 140))
            in_bottom_bar = y1 >= height - bottom_bar - 40
            clipped = y2 > height + 2 or y1 < -2 or x1 < -2 or x2 > width + 2
            side_breach = x1 < margin or x2 > width - margin
            if clipped or side_breach:
                add("CTA_SAFE_AREA", "FAIL", "CTA verletzt Safe Area / Bildrand", "CTA einrücken", bbox=best["bbox"])
            elif need_strong_cta and y1 < height * 0.35 and not in_bottom_bar:
                add("CTA_SAFE_AREA", "WARNING", "CTA ungewöhnlich hoch auf Slide", "CTA unten platzieren", bbox=best["bbox"])
            else:
                add("CTA_SAFE_AREA", "PASS", "CTA in Safe Area", bbox=best["bbox"])
        else:
            if need_strong_cta:
                add(
                    "CTA_PRESENT",
                    "FAIL",
                    "Kein CTA-/Brand-Text auf CTA-Slide erkannt",
                    "CTA-Text laut GGG-Regel setzen",
                )
            else:
                add(
                    "CTA_PRESENT",
                    "WARNING",
                    "Kein starker CTA-Text auf dieser Slide (ggf. nur Cover)",
                    "Auf slide3 prüfen",
                )
            add("CTA_SIZE", "NOT_CHECKABLE", "Kein CTA-BBox", "")
            add("CTA_CONTRAST", "NOT_CHECKABLE", "Kein CTA-BBox", "")
            add("CTA_SAFE_AREA", "NOT_CHECKABLE", "Kein CTA-BBox", "")

        if handle_hits:
            add("BRANDING_HANDLE", "PASS", f"Handle erkannt: '{handle_hits[0]['text']}'")
        else:
            add(
                "BRANDING_HANDLE",
                "WARNING" if not need_strong_cta else "FAIL",
                "Handle @germangolfguide nicht erkannt",
                "Branding-Leiste prüfen",
            )

    # --- Logo ---
    logo = _detect_round_logo(img, rules, hub_root / "assets")
    if logo["present"]:
        add(
            "LOGO_PRESENT",
            "PASS",
            f"Logo-Hinweis (gold_px={logo['gold_pixels']}, score={logo['template_score']:.2f})",
            **{k: logo[k] for k in ("gold_pixels", "template_score", "bbox")},
        )
        bbox = logo.get("bbox")
        if bbox:
            x1, y1, x2, y2 = bbox
            edge = int(rules["logo"]["not_cropped_edge_margin_px"])
            if x1 <= edge or y1 <= edge or x2 >= width - edge:
                add("LOGO_NOT_CROPPED", "FAIL", "Logo am Bildrand abgeschnitten", "Logo einrücken", bbox=bbox)
            else:
                add("LOGO_NOT_CROPPED", "PASS", "Logo nicht am Rand abgeschnitten", bbox=bbox)

            safe = rules["safe_area"]["feed_top_right_logo_box"]
            if x1 < width * float(safe["x_min_ratio"]) * 0.9 or y2 > height * float(safe["y_max_ratio"]) * 1.2:
                add("LOGO_SAFE_AREA", "WARNING", "Logo außerhalb typischer Top-Right-Zone", "Position prüfen", bbox=bbox)
            else:
                add("LOGO_SAFE_AREA", "PASS", "Logo in Top-Right-Zone", bbox=bbox)

            lh = y2 - y1
            exp = float(rules["logo"]["round_expected_height_px"]["feed" if kind == "feed" else "story"])
            tol = float(rules["logo"]["round_height_tol_ratio"])
            if abs(lh - exp) / exp > tol:
                add("LOGO_SIZE", "WARNING", f"Logo-Höhe {lh:.0f}px (Soll ~{exp:.0f})", "Größe anpassen", height=lh)
            else:
                add("LOGO_SIZE", "PASS", f"Logo-Höhe {lh:.0f}px", height=lh)
            add("LOGO_POSITION", "PASS", "Logo oben rechts detektiert", bbox=bbox)
        else:
            add("LOGO_NOT_CROPPED", "NOT_CHECKABLE", "Logo ohne BBox", "")
            add("LOGO_SAFE_AREA", "NOT_CHECKABLE", "Logo ohne BBox", "")
            add("LOGO_SIZE", "NOT_CHECKABLE", "Logo ohne BBox", "")
            add("LOGO_POSITION", "NOT_CHECKABLE", "Logo ohne BBox", "")
    else:
        # If branding handle found, logo visual may still be present but undetectable → NOT_CHECKABLE not FAIL alone
        if any(r.rule_id == "BRANDING_HANDLE" and r.status == "PASS" for r in results):
            add(
                "LOGO_PRESENT",
                "NOT_CHECKABLE",
                "Logo-Detektor unsicher (Handle vorhanden, Münze nicht sicher erkannt)",
                "Visuell freigeben oder Detektor nachziehen",
                gold_pixels=logo["gold_pixels"],
                template_score=logo["template_score"],
            )
        else:
            add(
                "LOGO_PRESENT",
                "FAIL",
                "Kein Logo-Hinweis erkannt",
                "GGG-Münze oben rechts einsetzen",
                gold_pixels=logo["gold_pixels"],
                template_score=logo["template_score"],
            )
        for rid in ("LOGO_NOT_CROPPED", "LOGO_SAFE_AREA", "LOGO_SIZE", "LOGO_POSITION"):
            add(rid, "NOT_CHECKABLE", "Kein Logo-BBox", "")

    return _pack_slide(path, slide_name, results, ocr_items, {"width": width, "height": height, "logo": logo})


def _pack_slide(
    path: Path,
    slide_name: str,
    results: list[RuleResult],
    ocr_items: list[dict[str, Any]],
    meta: dict[str, Any],
) -> dict[str, Any]:
    fails = [r for r in results if r.status == "FAIL"]
    warns = [r for r in results if r.status == "WARNING"]
    nc = [r for r in results if r.status == "NOT_CHECKABLE"]
    if fails:
        status = "FAIL"
    elif nc and not any(r.status == "PASS" for r in results if r.rule_id.startswith("CLUB")):
        status = "INCOMPLETE_CHECK"
    elif warns:
        status = "PASS_WITH_WARNINGS"
    elif nc:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
    return {
        "slide": slide_name,
        "datei": str(path),
        "status": status,
        "regeln": [r.to_dict() for r in results],
        "fehler": [r.to_dict() for r in fails],
        "warnungen": [r.to_dict() for r in warns],
        "not_checkable": [r.to_dict() for r in nc],
        "erkannte_texte": [
            {"text": o["text"], "confidence": o["confidence"], "bbox": o["bbox"], "height": o["height"]}
            for o in ocr_items
        ],
        "meta": meta,
    }


def analyze_posting_visual(
    *,
    dgv: str,
    club_name: str | None,
    images_dir: Path,
    hub_root: Path,
    planned_at: str | None = None,
    posting_id: str | None = None,
    source: str | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict[str, Any]:
    rules = load_rules()
    folder = images_dir / str(dgv)
    slides_meta = []
    paths: list[tuple[str, Path]] = []
    for s in rules["slides"]["required_feed"]:
        paths.append((s, folder / f"club_{dgv}_{s}.png"))
    for s in rules["slides"]["required_story"]:
        paths.append((s, folder / f"club_{dgv}_{s}.png"))

    present = [p for _, p in paths if p.is_file()]
    slide_count_status = "PASS" if len(present) >= 4 else "FAIL"
    slide_results = []

    # duplicate detection among existing
    hashes: list[tuple[str, int]] = []
    for name, p in paths:
        if cancel_check and cancel_check():
            raise RuntimeError("cancelled")
        if not p.is_file():
            slide_results.append(
                _pack_slide(
                    p,
                    name,
                    [
                        RuleResult(
                            rule_id="IMG_EXISTS",
                            status="FAIL",
                            severity="critical",
                            reason=f"fehlt: {p.name}",
                            suggestion="Slide erzeugen",
                        ),
                        RuleResult(
                            rule_id="SLIDE_COUNT",
                            status="FAIL",
                            severity="critical",
                            reason="Pflicht-Slide fehlt",
                            suggestion="Pipeline laufen lassen",
                        ),
                    ],
                    [],
                    {},
                )
            )
            continue
        try:
            hashes.append((name, _phash(p)))
        except Exception:
            pass
        slide_results.append(
            analyze_slide(
                p,
                slide_name=name,
                expected_club=club_name,
                hub_root=hub_root,
                rules=rules,
                cancel_check=cancel_check,
            )
        )

    # inject duplicate rule onto slides
    dup_pairs = []
    max_h = int(rules["slides"]["duplicate_phash_max_hamming"])
    for i, (n1, h1) in enumerate(hashes):
        for n2, h2 in hashes[i + 1 :]:
            if _hamming(h1, h2) <= max_h:
                dup_pairs.append((n1, n2))
    if dup_pairs:
        for sr in slide_results:
            rr = RuleResult(
                rule_id="SLIDE_DUP",
                status="FAIL",
                severity="high",
                reason=f"Ähnliche/doppelte Slides: {dup_pairs}",
                suggestion="Duplikate ersetzen",
                evidence={"pairs": dup_pairs},
            ).to_dict()
            sr["regeln"].append(rr)
            sr["fehler"].append(rr)
            sr["status"] = "FAIL"
    else:
        for sr in slide_results:
            if sr.get("datei") and Path(sr["datei"]).is_file():
                sr["regeln"].append(
                    RuleResult(
                        rule_id="SLIDE_DUP",
                        status="PASS",
                        severity="high",
                        reason="Keine Duplikat-Slides erkannt",
                    ).to_dict()
                )

    # overall
    statuses = [s["status"] for s in slide_results]
    if slide_count_status == "FAIL" or "FAIL" in statuses:
        overall = "FAIL"
    elif "INCOMPLETE_CHECK" in statuses:
        overall = "INCOMPLETE_CHECK"
    elif "PASS_WITH_WARNINGS" in statuses:
        overall = "PASS_WITH_WARNINGS"
    else:
        overall = "PASS"

    return {
        "posting_id": posting_id or f"local:{dgv}",
        "club": club_name or "",
        "dgv": dgv,
        "geplanter_termin": planned_at,
        "quelle": source or "local_hub_images",
        "anzahl_slides": len(present),
        "gesamtstatus": overall,
        "slides": slide_results,
        "belegreferenz": str(folder),
        "rules_version": rules.get("version"),
        "engine": visual_engine_info(),
        "read_only": True,
        "mutations": False,
    }

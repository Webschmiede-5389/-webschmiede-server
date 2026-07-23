"""TourMeter: Spritpreise über Tankerkoenig (DE) abrufen."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


# Krefeld Zentrum (Default für MbP)
DEFAULT_LAT = 51.3387
DEFAULT_LNG = 6.5642
API = "https://creativecommons.tankerkoenig.de/json/list.php"


def _secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        from agency_secrets import secrets_path, _parse_file

        _, vals = _parse_file(secrets_path())
        out.update(vals)
    except Exception:
        pass
    for root in (Path("/root/app"), Path(__file__).resolve().parents[2]):
        for name in ("deploy.secrets.local",):
            path = root / name
            if root.name == "backend":
                path = root.parent.parent / name
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                out.setdefault(k.strip(), v.strip())
    for k in ("TANKERKOENIG_API_KEY",):
        if os.getenv(k):
            out[k] = os.getenv(k, "")
    return out


def api_key(secrets: dict | None = None) -> str:
    sec = secrets if secrets is not None else _secrets()
    return (sec.get("TANKERKOENIG_API_KEY") or "").strip()


def fetch_fuel_prices(
    *,
    lat: float = DEFAULT_LAT,
    lng: float = DEFAULT_LNG,
    radius_km: float = 20,
    fuel_type: str = "diesel",
    mode: str = "cheapest",
    secrets: dict | None = None,
) -> dict[str, Any]:
    """
    fuel_type: diesel | e5 | e10 | all
    mode: cheapest | avg5 | average
    """
    key = api_key(secrets)
    if not key:
        return {
            "ok": False,
            "error": (
                "TANKERKOENIG_API_KEY fehlt. Kostenloser Key: "
                "https://creativecommons.tankerkoenig.de/ → in deploy.secrets.local / Agency Setup."
            ),
            "code": "missing_key",
        }

    ft = (fuel_type or "diesel").lower().strip()
    if ft not in ("diesel", "e5", "e10", "all"):
        ft = "diesel"
    rad = max(1.0, min(25.0, float(radius_km)))
    params = {
        "lat": f"{lat:.5f}",
        "lng": f"{lng:.5f}",
        "rad": f"{rad:.1f}",
        "sort": "price",
        "type": ft,
        "apikey": key,
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "TourMeter/1.0 (Webschmiede)"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")[:400]
        return {"ok": False, "error": f"Tankerkoenig HTTP {e.code}: {raw}", "code": "http"}
    except Exception as e:
        return {"ok": False, "error": str(e), "code": "network"}

    if not data.get("ok"):
        return {
            "ok": False,
            "error": data.get("message") or data.get("errmsg") or "Tankerkoenig Fehler",
            "raw": data,
            "code": "api",
        }

    stations = data.get("stations") or []
    prices: list[float] = []
    samples: list[dict] = []
    for st in stations:
        # type=all → object with diesel/e5/e10; sonst price float
        price = st.get("price")
        if isinstance(price, dict):
            price = price.get(ft if ft != "all" else "diesel")
        if price is None or price is False:
            continue
        try:
            p = float(price)
        except (TypeError, ValueError):
            continue
        if p <= 0:
            continue
        prices.append(p)
        if len(samples) < 8:
            samples.append(
                {
                    "name": st.get("name") or "",
                    "brand": st.get("brand") or "",
                    "place": st.get("place") or "",
                    "price": round(p, 3),
                    "dist": st.get("dist"),
                }
            )

    if not prices:
        return {
            "ok": False,
            "error": "Keine Preise in diesem Umkreis gefunden.",
            "code": "empty",
            "stations_checked": len(stations),
        }

    prices_sorted = sorted(prices)
    cheapest = prices_sorted[0]
    avg_all = sum(prices) / len(prices)
    top5 = prices_sorted[:5]
    avg5 = sum(top5) / len(top5)

    mode_l = (mode or "cheapest").lower()
    if mode_l == "average":
        chosen = avg_all
        label = "Durchschnitt aller Stationen"
    elif mode_l == "avg5":
        chosen = avg5
        label = "Mittel der 5 günstigsten"
    else:
        chosen = cheapest
        label = "Günstigster Preis im Umkreis"

    return {
        "ok": True,
        "fuel_type": ft,
        "mode": mode_l,
        "mode_label": label,
        "price": round(chosen, 3),
        "cheapest": round(cheapest, 3),
        "avg5": round(avg5, 3),
        "average": round(avg_all, 3),
        "count": len(prices),
        "radius_km": rad,
        "lat": lat,
        "lng": lng,
        "samples": samples,
        "source": "tankerkoenig",
    }

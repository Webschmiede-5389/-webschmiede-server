# -*- coding: utf-8 -*-
"""SHY001 customer static: self-hosted images, no ephemeral CDNs in production HTML."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
IMG = STATIC / "img"

CUSTOMER_HTML = (
    "index.html",
    "order.html",
    "admin.html",
    "konto.html",
)

FORBIDDEN_IMG_HOSTS = ("files.catbox.moe", "litter.catbox.moe")


@pytest.mark.parametrize("name", CUSTOMER_HTML)
def test_no_ephemeral_image_hosts_in_customer_html(name: str):
    text = (STATIC / name).read_text(encoding="utf-8")
    for host in FORBIDDEN_IMG_HOSTS:
        assert host not in text, f"{name} must not reference {host}"


def test_index_uses_self_hosted_img_paths():
    text = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'src="/img/hero.jpg"' in text or "src='/img/hero.jpg'" in text
    assert "/img/hassan.jpg" in text


@pytest.mark.parametrize(
    "filename",
    [
        "hero.jpg",
        "hassan.jpg",
        "food-teller.jpg",
        "food-pasta.jpg",
        "food-gallery1.jpg",
        "food-gallery2.jpg",
        "food-gallery3.jpg",
        "food-gallery4.jpg",
        "food-lahmacun.jpg",
        "food-rolle.jpg",
        "logo.png",
    ],
)
def test_shy001_img_assets_present_in_repo(filename: str):
    path = IMG / filename
    assert path.is_file(), f"missing {path} — run scripts/sync_shy001_img_from_server.py"
    assert path.stat().st_size > 10_000, f"{filename} looks empty or truncated"


def test_index_img_src_files_exist():
    text = (STATIC / "index.html").read_text(encoding="utf-8")
    paths = set(re.findall(r'src="(/img/[^"]+)"', text))
    for rel in paths:
        assert (STATIC / rel.lstrip("/")).is_file(), rel

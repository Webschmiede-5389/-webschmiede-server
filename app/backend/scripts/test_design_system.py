#!/usr/bin/env python3
"""Automated tests for SCHRITT 2 Design System (no production deploy)."""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "app" / "backend"
STATIC = ROOT / "app" / "static"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))


class DesignSystemFilesTest(unittest.TestCase):
    def test_token_and_app_css_exist(self):
        for name in (
            "webschmiede-tokens.css",
            "webschmiede-base.css",
            "webschmiede-layout.css",
            "webschmiede-components.css",
            "webschmiede-utilities.css",
            "webschmiede-app.css",
            "webschmiede-ci.css",
            "webschmiede-ui.js",
        ):
            self.assertTrue((STATIC / "ci" / name).is_file(), name)

    def test_core_tokens_consistent(self):
        text = (STATIC / "ci" / "webschmiede-tokens.css").read_text(encoding="utf-8")
        self.assertIn("--ws-brand-primary: #FF6600;", text)
        self.assertIn("--ws-brand-primary-hover: #E55A00;", text)
        self.assertIn("--ws-surface-page: #F5F5F5;", text)
        self.assertNotIn("#C9A84C", text)
        self.assertNotIn("#E8600A", text)

    def test_brand_manifest(self):
        import json

        man = STATIC / "brand" / "webschmiede" / "manifest.json"
        self.assertTrue(man.is_file())
        data = json.loads(man.read_text(encoding="utf-8"))
        paths = [a.get("path") for a in data["assets"] if a.get("canonical")]
        for p in paths:
            rel = ROOT / "app" / "static" / p.lstrip("/").replace("/", os.sep)
            self.assertTrue(rel.is_file(), p)

    def test_no_w_placeholder_in_new_templates(self):
        for path in (BACKEND / "templates").rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"brand-mark[^>]*>\s*W\s*<")


class BrandConfigTest(unittest.TestCase):
    def test_agency_default(self):
        from brand_config import agency_internal

        b = agency_internal()
        self.assertEqual(b.primary_color, "#FF6600")
        self.assertEqual(b.brand_name, "WebSchmiede")

    def test_rejects_free_css(self):
        from brand_config import BrandConfigError, validate_brand_dict

        with self.assertRaises(BrandConfigError):
            validate_brand_dict({"custom_css": "body{color:red}"})

    def test_rejects_bad_hex(self):
        from brand_config import BrandConfigError, validate_brand_dict

        with self.assertRaises(BrandConfigError):
            validate_brand_dict({"primary_color": "orange"})


class RegistryAndLintTest(unittest.TestCase):
    def test_registry_example(self):
        from validate_platform_registry import main

        self.assertEqual(main([sys.argv[0], str(ROOT / "config" / "platform_registry.example.yaml")]), 0)

    def test_design_lint_strict_clean(self):
        from design_lint import main

        self.assertEqual(main(), 0)


class DesignSystemRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["APP_ENV"] = "local"
        # Avoid loading full main (heavy). Test blueprint in isolation.
        from flask import Flask
        from design_system import design_system_bp, design_system_enabled

        cls.enabled = design_system_enabled()
        cls.app = Flask(__name__, template_folder=str(BACKEND / "templates"))
        cls.app.register_blueprint(design_system_bp)
        cls.client = cls.app.test_client()

    def test_enabled_in_local(self):
        self.assertTrue(self.enabled)

    def test_showcase_renders(self):
        r = self.client.get("/design-system")
        self.assertEqual(r.status_code, 200)
        html = r.data.decode("utf-8")
        self.assertIn("WebSchmiede", html)
        self.assertIn("Digitale Handwerkskunst", html)
        self.assertIn("Design System Showcase", html)
        self.assertNotIn("#C9A84C", html)
        self.assertNotRegex(html, r"Yassine|Snack House|@gmail\.com")

    def test_appshell_renders(self):
        r = self.client.get("/design-system/appshell")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"ws-app-shell", r.data)

    def test_tokens_css_served(self):
        r = self.client.get("/ci/webschmiede-tokens.css")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"--ws-brand-primary", r.data)

    def test_production_blocks_pages(self):
        os.environ["APP_ENV"] = "production"
        from importlib import reload
        import design_system as ds

        reload(ds)
        from flask import Flask

        app = Flask(__name__, template_folder=str(BACKEND / "templates"))
        app.register_blueprint(ds.design_system_bp)
        c = app.test_client()
        self.assertEqual(c.get("/design-system").status_code, 404)
        # restore
        os.environ["APP_ENV"] = "local"
        reload(ds)


class MacroRenderTest(unittest.TestCase):
    def test_macros_render(self):
        from flask import Flask, render_template_string

        app = Flask(__name__, template_folder=str(BACKEND / "templates"))
        with app.app_context():
            html = render_template_string(
                '{% from "shared/ui/macros.html" import brand_lockup, button %}'
                "{{ brand_lockup('compact') }}{{ button('Go', 'primary') }}"
            )
        self.assertIn("WebSchmiede", html)
        self.assertIn("ws-btn--primary", html)
        self.assertIn("/brand/webschmiede/logo-mark.png", html)


if __name__ == "__main__":
    unittest.main()

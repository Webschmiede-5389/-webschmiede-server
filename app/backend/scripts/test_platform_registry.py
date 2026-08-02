"""Security tests for platform_registry — fail-closed, no unsafe links."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from platform_registry import (  # noqa: E402
    filter_entries,
    load_filtered,
    load_raw,
    validate_entry_url,
    validate_registry,
)


class PlatformRegistrySecurityTests(unittest.TestCase):
    def test_real_registry_validates(self):
        data = load_raw(ROOT / "config" / "platform_registry.yaml")
        errs = validate_registry(data, production=True)
        self.assertEqual(errs, [], errs)

    def test_javascript_url_rejected(self):
        self.assertIsNotNone(validate_entry_url("javascript:alert(1)", production=False))

    def test_credentials_in_url_rejected(self):
        self.assertIsNotNone(
            validate_entry_url("https://user:pass@digitalehandwerkskunst.de/x", production=True)
        )

    def test_query_token_rejected(self):
        self.assertIsNotNone(
            validate_entry_url(
                "https://digitalehandwerkskunst.de/x?token=abc",
                production=True,
            )
        )

    def test_localhost_forbidden_in_production(self):
        self.assertIsNotNone(validate_entry_url("http://127.0.0.1:8090/", production=True))
        self.assertIsNone(validate_entry_url("http://127.0.0.1:8090/", production=False))

    def test_private_ip_forbidden_in_production(self):
        self.assertIsNotNone(validate_entry_url("https://10.0.0.5/tool", production=True))

    def test_duplicate_id_fails(self):
        data = {
            "entries": [
                self._entry(id="a", slug="a"),
                self._entry(id="a", slug="b"),
            ]
        }
        errs = validate_registry(data, production=True)
        self.assertTrue(any("duplicate id" in e for e in errs))

    def test_duplicate_slug_fails(self):
        data = {
            "entries": [
                self._entry(id="a", slug="same"),
                self._entry(id="b", slug="same"),
            ]
        }
        errs = validate_registry(data, production=True)
        self.assertTrue(any("duplicate slug" in e for e in errs))

    def test_staging_hidden_from_production_viewer(self):
        entries = [
            self._entry(id="prod", slug="prod", environment="production"),
            self._entry(id="stg", slug="stg", environment="staging", base_url="/design-system"),
        ]
        visible = filter_entries(entries, roles=["agency_admin"], viewer_env="production")
        ids = {e["id"] for e in visible}
        self.assertIn("prod", ids)
        self.assertNotIn("stg", ids)

    def test_role_gate_hides_admin_tool(self):
        entries = [
            self._entry(id="admin", slug="admin", required_roles=["agency_admin"]),
            self._entry(id="basic", slug="basic", required_roles=["agency"]),
        ]
        visible = filter_entries(entries, roles=["agency"], viewer_env="production")
        ids = {e["id"] for e in visible}
        self.assertNotIn("admin", ids)
        self.assertIn("basic", ids)

    def test_agency_admin_sees_agency_tools(self):
        entries = [self._entry(id="basic", slug="basic", required_roles=["agency"])]
        visible = filter_entries(entries, roles=["agency_admin"], viewer_env="production")
        self.assertEqual(len(visible), 1)

    def test_broken_card_does_not_raise(self):
        entries = [
            {"id": "bad"},  # incomplete
            self._entry(id="ok", slug="ok"),
        ]
        visible = filter_entries(entries, roles=["agency"], viewer_env="production")
        self.assertTrue(any(e.get("id") == "ok" for e in visible))

    def test_manipulated_registry_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.yaml"
            path.write_text("entries: not-a-list\n", encoding="utf-8")
            entries, errors = load_filtered(path=path, roles=["agency"], viewer_env="production")
            self.assertEqual(entries, [])
            self.assertTrue(errors)

    def test_missing_url_skipped(self):
        e = self._entry(id="x", slug="x")
        e["base_url"] = ""
        visible = filter_entries([e], roles=["agency"], viewer_env="production")
        self.assertEqual(visible, [])

    def _entry(self, **overrides):
        base = {
            "id": "x",
            "slug": "x",
            "display_name": "X",
            "short_description": "desc",
            "category": "Zentrale",
            "icon": "tools",
            "environment": "production",
            "service_type": "dashboard",
            "internal_or_external": "internal",
            "base_url": "https://digitalehandwerkskunst.de/agency",
            "open_mode": "same_tab",
            "required_roles": ["agency"],
            "tenant_visibility": "agency",
            "status": "ACTIVE_PRODUCTION",
            "sort_order": 1,
            "branding_mode": "AGENCY_INTERNAL",
            "owner": "Christian",
            "active": True,
        }
        base.update(overrides)
        return base


if __name__ == "__main__":
    raise SystemExit(unittest.main())

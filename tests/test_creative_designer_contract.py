"""Contract tests; run: PYTHONPATH=app/backend python -m unittest discover -s tests -p 'test_creative_designer_contract.py'"""
import unittest
from creative_designer_contract import CreativeJobError, validate_job


class CreativeContractTests(unittest.TestCase):
    def setUp(self):
        self.organic = dict(kunde_id="TEST_A", job_id="job_000001", content_mode="ORGANIC_SOCIAL",
                            formats=["FEED", "STORY"], briefing="Test organic",
                            content_pillar="Tipps", editorial_goal="Community")
        self.paid = dict(kunde_id="TEST_A", job_id="job_000002", content_mode="PAID_PERFORMANCE",
                         formats=["FEED", "STORY"], briefing="Test paid",
                         conversion_event="Lead", offer="Demo", landing_page="https://example.org",
                         target_kpi="CPL")

    def test_organic_valid(self):
        self.assertEqual(validate_job(self.organic, authorized_tenant="TEST_A")["status"], "VALIDATED_NOT_DISPATCHED")

    def test_paid_valid(self):
        self.assertEqual(validate_job(self.paid, authorized_tenant="TEST_A")["content_mode"], "PAID_PERFORMANCE")

    def test_cross_tenant_denied(self):
        with self.assertRaisesRegex(CreativeJobError, "tenant_not_authorized"):
            validate_job(self.organic, authorized_tenant="TEST_B")

    def test_no_authenticated_tenant_denied(self):
        with self.assertRaises(CreativeJobError):
            validate_job(self.organic, authorized_tenant=None)

    def test_agency_fallback_denied(self):
        with self.assertRaises(CreativeJobError):
            validate_job({**self.organic, "kunde_id": "AGENCY"}, authorized_tenant="AGENCY")

    def test_missing_mode_denied(self):
        with self.assertRaises(CreativeJobError):
            validate_job({k:v for k,v in self.organic.items() if k != "content_mode"}, authorized_tenant="TEST_A")

    def test_paid_missing_conversion_denied(self):
        with self.assertRaises(CreativeJobError):
            validate_job({k:v for k,v in self.paid.items() if k != "conversion_event"}, authorized_tenant="TEST_A")

    def test_organic_missing_pillar_denied(self):
        with self.assertRaises(CreativeJobError):
            validate_job({k:v for k,v in self.organic.items() if k != "content_pillar"}, authorized_tenant="TEST_A")

    def test_publication_denied(self):
        with self.assertRaises(CreativeJobError):
            validate_job({**self.organic, "publish": True}, authorized_tenant="TEST_A")

    def test_duplicate_formats_denied(self):
        with self.assertRaises(CreativeJobError):
            validate_job({**self.organic, "formats": ["FEED", "FEED"]}, authorized_tenant="TEST_A")


if __name__ == "__main__":
    unittest.main()

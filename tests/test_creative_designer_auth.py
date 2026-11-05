import unittest
from creative_designer_auth import authorized_creative_tenant


class CreativeAuthTests(unittest.TestCase):
    def test_matching_customer(self):
        self.assertEqual(authorized_creative_tenant(session={'user_id': 7, 'kind': 'kunde_admin'}, user={'id': 7, 'role': 'kunde_admin', 'kunde_id': 'TEST_A'}, requested_tenant='TEST_A'), 'TEST_A')

    def test_cross_tenant(self):
        self.assertIsNone(authorized_creative_tenant(session={'user_id': 7, 'kind': 'kunde_admin'}, user={'id': 7, 'role': 'kunde_admin', 'kunde_id': 'TEST_A'}, requested_tenant='TEST_B'))

    def test_missing_identity(self):
        self.assertIsNone(authorized_creative_tenant(session=None, user=None, requested_tenant='TEST_A'))

    def test_staff_not_implicitly_delegated(self):
        self.assertIsNone(authorized_creative_tenant(session={'user_id': 7, 'kind': 'agency'}, user={'id': 7, 'role': 'agency', 'kunde_id': 'TEST_A'}, requested_tenant='TEST_A'))

    def test_session_user_mismatch(self):
        self.assertIsNone(authorized_creative_tenant(session={'user_id': 8, 'kind': 'kunde_admin'}, user={'id': 7, 'role': 'kunde_admin', 'kunde_id': 'TEST_A'}, requested_tenant='TEST_A'))


if __name__ == '__main__':
    unittest.main()

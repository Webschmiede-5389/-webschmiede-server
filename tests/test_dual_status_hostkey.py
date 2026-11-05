"""Host-key regression tests for dual_infra.probe_via_ssh (no network)."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "backend" / "dual_infra.py"
spec = importlib.util.spec_from_file_location("dual_infra_hostkey_test", MODULE_PATH)
dual_infra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dual_infra)


class FakeSSHClient:
    instances = []

    def __init__(self):
        self.policy = None
        self.system_keys_loaded = False
        self.explicit_keys_path = None
        self.connected = False
        self.closed = False
        self.__class__.instances.append(self)

    def load_system_host_keys(self):
        self.system_keys_loaded = True

    def load_host_keys(self, path):
        if path == "/missing/pins":
            raise FileNotFoundError(path)
        self.explicit_keys_path = path

    def set_missing_host_key_policy(self, policy):
        self.policy = policy

    def connect(self, *args, **kwargs):
        self.connected = True
        if not isinstance(self.policy, FakeRejectPolicy):
            raise AssertionError("unsafe host-key policy")
        # Simulate Paramiko rejecting a host not in trusted known_hosts.
        raise FakeBadHostKey("unknown host key")

    def close(self):
        self.closed = True


class FakeRejectPolicy:
    pass


class FakeBadHostKey(Exception):
    pass


class HostKeyTests(unittest.TestCase):
    def setUp(self):
        FakeSSHClient.instances.clear()
        self.paramiko = types.SimpleNamespace(SSHClient=FakeSSHClient, RejectPolicy=FakeRejectPolicy)

    def probe(self, env):
        with patch.dict(sys.modules, {"paramiko": self.paramiko}):
            with patch.dict("os.environ", env, clear=True):
                with patch.object(dual_infra, "_read_secrets", return_value={"WEB_HOST": "web.example", "WEB_PASSWORD": "fake"}):
                    return dual_infra.probe_via_ssh("web")

    def test_unknown_host_key_fails_closed(self):
        result = self.probe({})
        client = FakeSSHClient.instances[-1]
        self.assertFalse(result["ok"])
        self.assertTrue(client.system_keys_loaded)
        self.assertIsInstance(client.policy, FakeRejectPolicy)
        self.assertTrue(client.connected)
        self.assertTrue(client.closed)

    def test_explicit_pinned_host_file_is_loaded(self):
        result = self.probe({"DUAL_SSH_KNOWN_HOSTS": "/safe/pins"})
        client = FakeSSHClient.instances[-1]
        self.assertFalse(result["ok"])
        self.assertEqual(client.explicit_keys_path, "/safe/pins")

    def test_missing_explicit_host_file_stops_before_connect(self):
        result = self.probe({"DUAL_SSH_KNOWN_HOSTS": "/missing/pins"})
        client = FakeSSHClient.instances[-1]
        self.assertFalse(result["ok"])
        self.assertFalse(client.connected)
        self.assertTrue(client.closed)


if __name__ == "__main__":
    unittest.main()

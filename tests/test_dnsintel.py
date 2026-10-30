import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mega_checker.dnsintel import DomainInspector


class DNSInspectorTests(unittest.TestCase):
    def _inspect_mx(self, answers):
        fake_resolver = Mock()
        fake_resolver.resolve.return_value = answers
        inspector = DomainInspector()
        with patch("mega_checker.dnsintel.dns.resolver.Resolver", return_value=fake_resolver):
            with patch.object(inspector, "_resolve_txt", return_value=([], "absent")):
                return inspector._inspect_with_dnspython("example.invalid")

    def test_null_mx_is_not_reported_as_mail_host(self):
        result = self._inspect_mx([
            SimpleNamespace(exchange=".", preference=0)
        ])
        self.assertEqual(result["mx_status"], "null_mx")
        self.assertEqual(result["mx_hosts"], [])

    def test_null_mx_mixed_with_regular_mx_is_flagged(self):
        result = self._inspect_mx([
            SimpleNamespace(exchange=".", preference=0),
            SimpleNamespace(exchange="mx.example.invalid.", preference=10),
        ])
        self.assertEqual(result["mx_status"], "invalid_mx_configuration")
        self.assertEqual(result["mx_hosts"], ["mx.example.invalid"])


if __name__ == "__main__":
    unittest.main()

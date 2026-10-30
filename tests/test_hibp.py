import hashlib
import io
import unittest
from unittest.mock import patch, Mock
from urllib.error import HTTPError
from mega_checker.hibp import HIBPError, check_breached_email, check_password_k_anonymity

class HIBPTests(unittest.TestCase):
    def test_email_lookup_empty_body_is_not_breached(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b"[]"
        with patch("mega_checker.hibp.urllib.request.urlopen", return_value=response) as opened:
            result = check_breached_email("user@example.com", api_key="test-key")
        self.assertEqual(result["status"], "not_breached")
        request = opened.call_args.args[0]
        self.assertTrue(any(k.lower() == "hibp-api-key" for k in request.headers))
        self.assertTrue(request.full_url.startswith("https://haveibeenpwned.com/api/v3/"))

    def test_email_lookup_404_is_not_breached_and_closes_body(self):
        body = io.BytesIO(b"not found")
        error = HTTPError("https://example.invalid", 404, "not found", {}, body)
        with patch("mega_checker.hibp.urllib.request.urlopen", side_effect=error):
            result = check_breached_email("user@example.com", api_key="test-key")
        self.assertEqual(result["status"], "not_breached")
        self.assertTrue(body.closed)

    def test_password_range_http_error_closes_body(self):
        body = io.BytesIO(b"not found")
        error = HTTPError("https://example.invalid/range", 503, "unavailable", {}, body)
        with patch("mega_checker.hibp.urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(HIBPError, "HTTP 503"):
                check_password_k_anonymity("Synthetic-Password-Only")
        self.assertTrue(body.closed)

    def test_password_range_only_sends_prefix(self):
        password = "Password123!"
        digest = hashlib.sha1(password.encode()).hexdigest().upper()
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = f"{digest[5:]}:7\nOTHERHASH:1\n".encode("ascii")
        with patch("mega_checker.hibp.urllib.request.urlopen", return_value=response) as opened:
            result = check_password_k_anonymity(password)
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url.rsplit("/", 1)[-1], digest[:5])
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["count"], 7)

if __name__ == "__main__":
    unittest.main()

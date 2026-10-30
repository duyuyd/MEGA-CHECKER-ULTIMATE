"""Optional real dkimpy integration tests using a synthetic test-only keypair."""
from __future__ import annotations

import base64
import unittest
from pathlib import Path
from unittest.mock import Mock

try:
    import dkim as dkimpy
except ImportError:  # Core project remains install-free; CI installs this extra.
    dkimpy = None

from mega_checker.dkim import verify_dkim_message

FIXTURES = Path(__file__).parent / "fixtures"
PRIVATE_KEY = (FIXTURES / "dkim_test_private.pem").read_bytes()
PUBLIC_KEY_B64 = (FIXTURES / "dkim_test_public_b64.txt").read_text(encoding="ascii").strip()


@unittest.skipIf(dkimpy is None, "optional dkimpy package not installed")
class DKIMPyCryptographicIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.raw = (
            b"From: sender@example.com\r\n"
            b"To: recipient@example.net\r\n"
            b"Subject: Signed test message\r\n"
            b"Date: Fri, 30 Oct 2026 12:00:00 +0700\r\n"
            b"Message-ID: <dkim-test@example.com>\r\n"
            b"MIME-Version: 1.0\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"This is a synthetic DKIM verification fixture.\r\n"
        )
        signature = dkimpy.sign(
            self.raw,
            selector=b"unit-test-2026",
            domain=b"example.com",
            privkey=PRIVATE_KEY,
            include_headers=[b"from", b"to", b"subject", b"date", b"message-id"],
            canonicalize=(b"relaxed", b"relaxed"),
        )
        self.signed = signature + self.raw

        self.inspector = Mock()
        resolver = Mock()
        resolver.nameservers = ["127.0.0.1"]
        self.inspector._create_resolver.return_value = (resolver, "synthetic-fixture")
        self.inspector.timeout = 4.0
        self.inspector._resolve_txt.return_value = (
            [f"v=DKIM1; k=rsa; p={PUBLIC_KEY_B64}"], "answer"
        )

    def test_valid_message_passes_real_rsa_signature_and_body_hash(self):
        result = verify_dkim_message(self.signed, self.inspector)
        self.assertEqual(result["overall_status"], "pass")
        self.assertEqual(result["pass_count"], 1)
        self.assertEqual(result["signatures"][0]["status"], "pass")

    def test_tampered_body_fails_body_hash_validation(self):
        tampered = self.signed.replace(
            b"synthetic DKIM verification fixture",
            b"modified DKIM verification fixture",
        )
        result = verify_dkim_message(tampered, self.inspector)
        self.assertEqual(result["overall_status"], "fail")
        self.assertEqual(result["signatures"][0]["status"], "fail")

    def test_tampered_signed_header_fails_signature_validation(self):
        tampered = self.signed.replace(
            b"Subject: Signed test message",
            b"Subject: Changed test message",
        )
        result = verify_dkim_message(tampered, self.inspector)
        self.assertEqual(result["overall_status"], "fail")
        self.assertEqual(result["signatures"][0]["status"], "fail")


if __name__ == "__main__":
    unittest.main()

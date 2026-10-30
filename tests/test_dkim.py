import unittest
from unittest.mock import Mock, patch

from mega_checker.dkim import (
    _dkim_key_record_state,
    lookup_dkim_signatures,
    normalize_selector,
    parse_dkim_signature_headers,
    read_clipboard_header_text,
)


class DKIMHeaderTests(unittest.TestCase):
    def test_parse_folded_dkim_signature(self):
        raw = (
            b"From: sender@example.com\r\n"
            b"DKIM-Signature: v=1; a=rsa-sha256; d=Example.COM;\r\n"
            b"\ts=mail.2026; c=relaxed/relaxed; h=from:to; bh=abc; b=secret\r\n"
            b"Subject: demo\r\n\r\nbody\r\n"
        )
        result = parse_dkim_signature_headers(raw)
        self.assertEqual(result, [{
            "domain": "example.com", "selector": "mail.2026", "source": "DKIM-Signature#1"
        }])
        self.assertNotIn("secret", repr(result))

    def test_parse_multiple_signatures_and_dedupe(self):
        raw = (
            "DKIM-Signature: v=1; d=example.com; s=one; b=abc\r\n"
            "DKIM-Signature: v=1; d=example.net; s=two; b=def\r\n"
            "DKIM-Signature: v=1; d=EXAMPLE.COM; s=ONE; b=ghi\r\n\r\n"
        )
        result = parse_dkim_signature_headers(raw)
        self.assertEqual([(x["domain"], x["selector"]) for x in result], [
            ("example.com", "one"), ("example.net", "two")
        ])

    def test_invalid_or_missing_signature_headers_are_ignored(self):
        raw = "From: a@example.com\r\nDKIM-Signature: v=1; d=example.com; b=abc\r\n\r\n"
        self.assertEqual(parse_dkim_signature_headers(raw), [])

    def test_selector_validation(self):
        self.assertEqual(normalize_selector("A.b-2_3"), "a.b-2_3")
        for value in ("", ".bad", "bad.", "bad..name", "has space", "x/../y"):
            self.assertEqual(normalize_selector(value), "")

    def test_key_record_requires_p_tag_and_valid_version(self):
        self.assertEqual(_dkim_key_record_state("v=DKIM1; k=rsa; p=ABC"), "present")
        self.assertEqual(_dkim_key_record_state("k=rsa; p=ABC"), "present")
        self.assertEqual(_dkim_key_record_state("v=DKIM1; p="), "revoked")
        self.assertIsNone(_dkim_key_record_state("v=spf1; p=ABC"))
        self.assertIsNone(_dkim_key_record_state("v=DKIM2; p=ABC"))

    def test_lookup_uses_signing_domain_and_selector_from_header(self):
        inspector = Mock()
        resolver = Mock()
        resolver.nameservers = ["1.1.1.1"]
        inspector._create_resolver.return_value = (resolver, "test_resolver")
        inspector._resolve_txt.return_value = (["v=DKIM1; k=rsa; p=PUBLICKEY"], "answer")
        result = lookup_dkim_signatures(inspector, [{
            "domain": "signer.example.net", "selector": "s2026", "source": "DKIM-Signature#1"
        }])
        inspector._resolve_txt.assert_called_once_with(resolver, "s2026._domainkey.signer.example.net")
        self.assertEqual(result["dkim_status"], "present")
        self.assertEqual(result["results"][0]["status"], "present")

    def test_lookup_distinguishes_absent_from_timeout(self):
        inspector = Mock()
        resolver = Mock(); resolver.nameservers = ["1.1.1.1"]
        inspector._create_resolver.return_value = (resolver, "test_resolver")
        inspector._resolve_txt.return_value = ([], "timeout")
        result = lookup_dkim_signatures(inspector, [{"domain":"example.com", "selector":"mail"}])
        self.assertEqual(result["dkim_status"], "unknown")
        inspector._resolve_txt.return_value = ([], "nxdomain")
        result = lookup_dkim_signatures(inspector, [{"domain":"example.com", "selector":"mail"}])
        self.assertEqual(result["dkim_status"], "not_found_for_supplied_selectors")

    def test_lookup_reports_revoked_key(self):
        inspector = Mock()
        resolver = Mock(); resolver.nameservers = ["1.1.1.1"]
        inspector._create_resolver.return_value = (resolver, "test_resolver")
        inspector._resolve_txt.return_value = (["v=DKIM1; p="], "answer")
        result = lookup_dkim_signatures(inspector, [{"domain":"example.com", "selector":"old"}])
        self.assertEqual(result["dkim_status"], "revoked")

    @patch("mega_checker.dkim.shutil.which", return_value="termux-clipboard-get")
    @patch("mega_checker.dkim.subprocess.run")
    def test_clipboard_reader_returns_local_bytes(self, run, which):
        run.return_value = Mock(returncode=0, stdout=b"DKIM-Signature: d=example.com; s=mail; b=secret\r\n\r\n")
        raw = read_clipboard_header_text()
        self.assertIn(b"DKIM-Signature", raw)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["termux-clipboard-get"])

    @patch("mega_checker.dkim.shutil.which", return_value=None)
    def test_clipboard_reader_gives_termux_api_guidance(self, which):
        with self.assertRaises(FileNotFoundError) as ctx:
            read_clipboard_header_text()
        self.assertIn("--headers-file", str(ctx.exception))

    @patch("mega_checker.dkim.shutil.which", return_value="termux-clipboard-get")
    @patch("mega_checker.dkim.subprocess.run")
    def test_clipboard_reader_rejects_empty_clipboard(self, run, which):
        run.return_value = Mock(returncode=0, stdout=b"  \n")
        with self.assertRaises(ValueError):
            read_clipboard_header_text()


    def test_common_selector_absence_is_labelled_heuristic(self):
        inspector = Mock()
        resolver = Mock(); resolver.nameservers = ["1.1.1.1"]
        inspector._create_resolver.return_value = (resolver, "test_resolver")
        inspector._resolve_txt.return_value = ([], "nxdomain")
        result = lookup_dkim_signatures(inspector, [{
            "domain": "example.com", "selector": "selector1", "source": "common-selector-heuristic"
        }])
        self.assertEqual(result["dkim_status"], "not_found_in_tested_selector_hints")

    def test_gmail_provider_hint_negative_is_still_heuristic(self):
        inspector = Mock()
        resolver = Mock(); resolver.nameservers = ["1.1.1.1"]
        inspector._create_resolver.return_value = (resolver, "test_resolver")
        inspector._resolve_txt.return_value = ([], "nxdomain")
        result = lookup_dkim_signatures(inspector, [{
            "domain": "gmail.com", "selector": "20251104",
            "source": "gmail-provider-observed-hint"
        }])
        self.assertEqual(result["dkim_status"], "not_found_in_tested_selector_hints")


if __name__ == "__main__":
    unittest.main()

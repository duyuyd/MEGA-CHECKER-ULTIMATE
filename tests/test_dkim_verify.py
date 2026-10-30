import sys
import types
import unittest
from unittest.mock import Mock, patch
from mega_checker.dkim import verify_dkim_message

SAMPLE = (b"From: sender@example.com\r\nTo: receiver@example.net\r\n"
          b"Subject: test\r\nDKIM-Signature: v=1; a=rsa-sha256; d=example.com; s=mail; c=relaxed/relaxed; h=from:to:subject; bh=abc; b=xyz\r\n\r\nbody\r\n")

class FakeDKIM:
    def __init__(self, message, minkey=1024, timeout=5): self.message=message
    def verify(self, idx=0, dnsfunc=None):
        key=dnsfunc(b"mail._domainkey.example.com", timeout=5)
        return bool(key) and key.startswith(b"v=DKIM1") and b"p=UFVCTElD" in key

class DKIMVerifyAdapterTests(unittest.TestCase):
    def setUp(self):
        self.inspector=Mock(); resolver=Mock(); resolver.nameservers=["1.1.1.1"]
        self.inspector._create_resolver.return_value=(resolver,"test-resolver")
        self.inspector.timeout=4.0
        self.inspector._resolve_txt.return_value=(["v=DKIM1; k=rsa; p=UFVCTElD"],"answer")
        self.module=types.SimpleNamespace(DKIM=FakeDKIM)
        self.patcher=patch.dict(sys.modules,{"dkim":self.module}); self.patcher.start()
        self.addCleanup(self.patcher.stop)
    def test_valid_callback_and_status(self):
        r=verify_dkim_message(SAMPLE,self.inspector)
        self.assertEqual(r["overall_status"],"pass")
        self.assertEqual(r["pass_count"],1)
    def test_missing_key_is_perm_error(self):
        self.inspector._resolve_txt.return_value=([],"nxdomain")
        r=verify_dkim_message(SAMPLE,self.inspector)
        self.assertEqual(r["overall_status"],"perm_error")
    def test_dns_timeout_is_temp_error(self):
        self.inspector._resolve_txt.return_value=([],"timeout")
        r=verify_dkim_message(SAMPLE,self.inspector)
        self.assertEqual(r["overall_status"],"temp_error")
    def test_present_key_but_bad_crypto_is_fail(self):
        class Bad(FakeDKIM):
            def verify(self,idx=0,dnsfunc=None): dnsfunc(b"mail._domainkey.example.com"); return False
        self.module.DKIM=Bad
        r=verify_dkim_message(SAMPLE,self.inspector)
        self.assertEqual(r["overall_status"],"fail")

    def test_body_hash_validation_exception_is_fail(self):
        class ValidationError(Exception): pass
        class BadBody(FakeDKIM):
            def verify(self,idx=0,dnsfunc=None):
                dnsfunc(b"mail._domainkey.example.com")
                raise ValidationError("body hash mismatch")
        self.module.DKIM=BadBody
        r=verify_dkim_message(SAMPLE,self.inspector)
        self.assertEqual(r["overall_status"], "fail")
        self.assertEqual(r["signatures"][0]["reason"], "body_hash_or_cryptographic_validation_failed")

    def test_invalid_public_key_record_is_perm_error(self):
        self.inspector._resolve_txt.return_value=( ["v=DKIM1; k=rsa; p=not-base64!"], "answer" )
        r=verify_dkim_message(SAMPLE,self.inspector)
        self.assertEqual(r["overall_status"], "perm_error")
        self.assertEqual(r["signatures"][0]["reason"], "invalid_public_key_record")

    def test_public_identity_is_not_returned(self):
        raw = SAMPLE.replace(b"s=mail;", b"s=mail; i=private-user@example.com;")
        r=verify_dkim_message(raw,self.inspector)
        self.assertNotIn("private-user", repr(r))

    def test_ed25519_backend_missing_is_distinct(self):
        class NaClNotFoundError(Exception): pass
        class Ed25519(FakeDKIM):
            def verify(self,idx=0,dnsfunc=None):
                dnsfunc(b"mail._domainkey.example.com")
                raise NaClNotFoundError("install pynacl")
        self.module.DKIM=Ed25519
        r=verify_dkim_message(SAMPLE,self.inspector)
        self.assertEqual(r["overall_status"], "unsupported_algorithm_backend")
    def test_revoked_key(self):
        self.inspector._resolve_txt.return_value=(["v=DKIM1; p="],"answer")
        r=verify_dkim_message(SAMPLE,self.inspector)
        self.assertEqual(r["overall_status"],"revoked")
    def test_no_signature(self):
        r=verify_dkim_message(b"From: x@example.com\r\n\r\nbody",self.inspector)
        self.assertEqual(r["overall_status"],"no_signature")

    def test_invalid_signature_header_is_not_reported_as_missing(self):
        raw=b"From: x@example.com\r\nDKIM-Signature: v=1; a=rsa-sha256; b=bad\r\n\r\nbody"
        r=verify_dkim_message(raw,self.inspector)
        self.assertEqual(r["overall_status"], "invalid_signature_header")
    def test_headers_only_rejected(self):
        with self.assertRaises(ValueError): verify_dkim_message(b"DKIM-Signature: d=example.com; s=mail\r\n",self.inspector)
    def test_public_key_not_in_output(self):
        r=verify_dkim_message(SAMPLE,self.inspector)
        self.assertNotIn("PUBLIC",repr(r))

if __name__ == "__main__": unittest.main()
